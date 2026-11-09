"""FamQuest authorization server for pre-registered public MCP clients.

Dynamic registration is opt-in. No remote metadata URLs are fetched. All
redirect URIs are exact matches, tokens target this installation's MCP URL,
and authorization requires an active parent browser session plus consent.
"""

import html
import json
import secrets
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth_registry import OAuthClient, Tenant
from app.browser_sessions import COOKIE_NAME, authenticate_browser
from app.oauth_codes import issue_code
from app.oauth_tokens import exchange_code, revoke_token, rotate_refresh
from app.security import RateLimiter

SCOPE = "famquest:parent"
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class ParentConsentDenied(PermissionError):
    pass


def oauth_error(code: str, status: int = 400):
    return JSONResponse({"error": code}, status_code=status, headers=HEADERS)


async def bounded_body(request: Request) -> bytes:
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > 8192:
            raise ValueError("Request too large")
    return body


async def form(request: Request) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
    ):
        raise ValueError("Form required")
    values = parse_qs(
        (await bounded_body(request)).decode("utf-8"),
        keep_blank_values=True,
        strict_parsing=True,
        max_num_fields=20,
    )
    if any(len(items) != 1 for items in values.values()):
        raise ValueError("Duplicate parameters")
    return {key: items[0] for key, items in values.items()}


def redirect(uri: str, **values):
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True) + list(values.items())
    return RedirectResponse(
        urlunsplit(parts._replace(query=urlencode(query))), status_code=303, headers=HEADERS
    )


def install_oauth_routes(app, registry, settings, *, validate_family=None):
    origin = settings.public_url.rstrip("/")
    resource = origin + "/mcp"
    registration_limit = RateLimiter(max_failures=20, window_seconds=900)
    token_limit = RateLimiter(max_failures=20, window_seconds=60)

    @app.get("/.well-known/oauth-authorization-server")
    def metadata():
        result = {
            "issuer": origin,
            "authorization_endpoint": origin + "/authorize",
            "token_endpoint": origin + "/token",
            "revocation_endpoint": origin + "/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [SCOPE],
            "authorization_response_iss_parameter_supported": True,
        }
        if settings.oauth_dynamic_registration:
            result["registration_endpoint"] = origin + "/register"
        return result

    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    def protected_resource():
        return {
            "resource": resource,
            "authorization_servers": [origin],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
        }

    @app.post("/register", status_code=201)
    async def register(request: Request):
        if not settings.oauth_dynamic_registration:
            return oauth_error("registration_not_supported", 404)
        key = f"register:{request.client.host if request.client else 'unknown'}"
        if registration_limit.is_blocked(key):
            return oauth_error("temporarily_unavailable", 429)
        registration_limit.record_failure(key)
        try:
            data = json.loads(await bounded_body(request))
            if not isinstance(data, dict):
                raise ValueError("Invalid metadata")
            uris = data.get("redirect_uris")
            if not isinstance(uris, list) or len(uris) != 1 or not isinstance(uris[0], str):
                return oauth_error("invalid_redirect_uri")
            uri = uris[0]
            parsed = urlsplit(uri)
            # Force port validation as urlsplit itself accepts malformed ports.
            _ = parsed.port
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.fragment
                or "*" in uri
                or "\\" in uri
                or len(uri) > 2048
                or any(c.isspace() for c in uri)
            ):
                return oauth_error("invalid_redirect_uri")
            if (
                data.get("token_endpoint_auth_method", "none") != "none"
                or set(data.get("grant_types", ["authorization_code", "refresh_token"]))
                - {"authorization_code", "refresh_token"}
                or data.get("response_types", ["code"]) != ["code"]
                or data.get("scope", SCOPE) != SCOPE
            ):
                return oauth_error("invalid_client_metadata")
        except (ValueError, TypeError, UnicodeError):
            return oauth_error("invalid_client_metadata")
        client_id = secrets.token_urlsafe(24)
        with registry.session() as db:
            db.add(OAuthClient(id=client_id, redirect_uri=uri, enabled=True))
            db.commit()
        return JSONResponse(
            {
                "client_id": client_id,
                "redirect_uris": [uri],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": SCOPE,
            },
            status_code=201,
            headers=HEADERS,
        )

    def authorize_request(db, values):
        client = db.get(OAuthClient, values.get("client_id", ""))
        if (
            client is None
            or not client.enabled
            or client.redirect_uri != values.get("redirect_uri")
            or values.get("response_type") != "code"
            or values.get("code_challenge_method") != "S256"
            or values.get("resource") != resource
            or values.get("scope", SCOPE) != SCOPE
            or not values.get("state")
            or len(values["state"]) > 2048
        ):
            raise ValueError("Invalid authorization request")
        import re

        if re.fullmatch(r"[A-Za-z0-9_-]{43}", values.get("code_challenge", "")) is None:
            raise ValueError("Invalid challenge")
        return client

    def browser(db, request, *, csrf=None, writing=False):
        session, principal = authenticate_browser(
            db, request.cookies.get(COOKIE_NAME), csrf_token=csrf, writing=writing
        )
        if principal.role not in {"admin", "parent"}:
            raise ParentConsentDenied("Parent required")
        if validate_family is not None:
            validate_family(db, session, principal)
        return session, principal

    @app.get("/authorize")
    def consent(request: Request):
        values = dict(request.query_params)
        if len(request.query_params.multi_items()) != len(values):
            return oauth_error("invalid_request")
        with registry.session() as db:
            try:
                client = authorize_request(db, values)
            except (ValueError, TypeError):
                return oauth_error("invalid_request")
            try:
                session, principal = browser(db, request)
            except ParentConsentDenied:
                return oauth_error("access_denied", 403)
            except PermissionError:
                return RedirectResponse(
                    "/login?" + urlencode({"next": "/authorize?" + urlencode(values)}),
                    status_code=303,
                    headers=HEADERS,
                )
            family = db.get(Tenant, principal.tenant_id)
            fields = {**values, "csrf_token": session.csrf_token}
            hidden = "".join(
                f'<input type="hidden" name="{html.escape(key, quote=True)}" '
                f'value="{html.escape(value, quote=True)}">'
                for key, value in fields.items()
            )
            host = html.escape(urlsplit(client.redirect_uri).netloc)
            # Chromium applies form-action to the POST's redirect chain too.
            # Permit only this registered client's origin; exact callback matching
            # remains enforced by authorize_request and the code exchange.
            callback = urlsplit(client.redirect_uri)
            callback_origin = callback.scheme + "://" + quote(callback.netloc, safe=".-:[]")
            name = html.escape(family.name)
            page = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FamQuest verbinden</title>
<style>body{{font:18px system-ui;max-width:38rem;margin:3rem auto;padding:1rem;
background:#fff7ed;color:#1e293b}}
button{{font:inherit;padding:.8rem 1rem;margin:.4rem;border-radius:.7rem;cursor:pointer}}</style>
<h1>FamQuest verbinden</h1><p>Verbindung für Familie <strong>{name}</strong>.</p>
<p>Ziel der Verbindung: <strong>{host}</strong></p>
<p>Der Assistent darf die freigegebenen Familienfunktionen nutzen.
Geld, Bankzugänge und Kontoverwaltung bleiben ausgeschlossen.
Elternfreigaben bleiben erforderlich.</p>
<form method="post" action="/authorize">{hidden}
<button name="decision" value="allow">Verbindung erlauben</button>
<button name="decision" value="deny">Abbrechen</button></form></html>"""
            return HTMLResponse(
                page,
                headers={
                    **HEADERS,
                    "Content-Security-Policy": (
                        "default-src 'none'; style-src 'unsafe-inline'; "
                        f"form-action 'self' {callback_origin}; "
                        "frame-ancestors 'none'; base-uri 'none'"
                    ),
                },
            )

    @app.post("/authorize")
    async def authorize(request: Request):
        try:
            values = await form(request)
        except (ValueError, UnicodeError):
            return oauth_error("invalid_request")
        with registry.session() as db:
            try:
                client = authorize_request(db, values)
                _, principal = browser(db, request, csrf=values.get("csrf_token"), writing=True)
            except (ValueError, TypeError):
                return oauth_error("invalid_request")
            except PermissionError:
                return oauth_error("access_denied", 403)
            if values.get("decision") == "deny":
                return redirect(
                    client.redirect_uri, error="access_denied", state=values["state"], iss=origin
                )
            if values.get("decision") != "allow":
                return oauth_error("invalid_request")
            code = issue_code(
                db,
                client_id=client.id,
                redirect_uri=client.redirect_uri,
                identity_id=principal.identity_id,
                tenant_id=principal.tenant_id,
                code_challenge=values["code_challenge"],
            )
            db.commit()
            return redirect(client.redirect_uri, code=code, state=values["state"], iss=origin)

    @app.post("/token")
    async def token(request: Request):
        key = f"token:{request.client.host if request.client else 'unknown'}"
        if token_limit.is_blocked(key):
            return oauth_error("temporarily_unavailable", 429)
        try:
            values = await form(request)
            if values.get("resource") != resource:
                return oauth_error("invalid_target")
            if not values.get("client_id") or request.headers.get("authorization"):
                return oauth_error("invalid_client", 401)
            with registry.session() as db:
                if values.get("grant_type") == "authorization_code":
                    pair = exchange_code(
                        db,
                        code=values.get("code", ""),
                        client_id=values["client_id"],
                        redirect_uri=values.get("redirect_uri", ""),
                        verifier=values.get("code_verifier", ""),
                        audience=resource,
                    )
                elif values.get("grant_type") == "refresh_token":
                    pair = rotate_refresh(
                        db,
                        values.get("refresh_token", ""),
                        client_id=values["client_id"],
                        audience=resource,
                    )
                else:
                    return oauth_error("unsupported_grant_type")
        except (ValueError, UnicodeError):
            return oauth_error("invalid_request")
        except PermissionError:
            token_limit.record_failure(key)
            return oauth_error("invalid_grant")
        return JSONResponse(
            {
                "access_token": pair.access_token,
                "refresh_token": pair.refresh_token,
                "token_type": "Bearer",
                "expires_in": pair.expires_in,
                "scope": SCOPE,
            },
            headers=HEADERS,
        )

    @app.post("/revoke")
    async def revoke(request: Request):
        try:
            values = await form(request)
            if not values.get("client_id") or not values.get("token"):
                return oauth_error("invalid_request")
            with registry.session() as db:
                revoke_token(db, values["token"], client_id=values["client_id"])
        except (ValueError, UnicodeError):
            return oauth_error("invalid_request")
        return JSONResponse({}, headers=HEADERS)
