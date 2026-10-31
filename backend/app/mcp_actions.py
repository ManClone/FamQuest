"""Reserve before mutations; uncertain outcomes never execute a second time.

Records and response bodies live in the selected family database, not the
central user registry. Authentication and parent confirmation precede replay.
"""

import hashlib
import re
from datetime import UTC, datetime

from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.logs import logger
from app.models import McpAction

MAX_BODY = 2 * 1024 * 1024


def error(code, status):
    return JSONResponse({"code": code}, status_code=status, headers={"Cache-Control": "no-store"})


def reserve(session_factory, principal, key, fingerprint, validate_actor):
    with session_factory(principal) as db:
        validate_actor(db, principal)
        db.add(
            McpAction(
                identity_id=principal.identity_id,
                request_key=key,
                actor_user_id=principal.family_user_id,
                fingerprint=fingerprint,
            )
        )
        try:
            db.commit()
            return None
        except IntegrityError:
            db.rollback()
            record = db.get(McpAction, (principal.identity_id, key))
            if record is None:
                raise
            if record.fingerprint != fingerprint:
                return error("mcp.request_key_reused", 409)
            if record.status_code is None:
                return error("mcp.outcome_unknown_check_state", 409)
            return Response(
                content=record.response_body,
                status_code=record.status_code,
                media_type=record.content_type,
                headers={"Cache-Control": "no-store"},
            )


def finish(session_factory, principal, key, status, body, content_type):
    with session_factory(principal) as db:
        record = db.get(McpAction, (principal.identity_id, key))
        record.status_code = status
        record.response_body = body
        record.content_type = content_type
        record.finished_at = datetime.now(UTC)
        db.commit()


async def execute(request, call_next, session_factory, principal, validate_actor):
    key = request.headers.get("x-mcp-request-key", "")
    if re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key) is None:
        return error("mcp.request_key_required", 422)
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            return error("mcp.request_too_large", 413)
    # Starlette's Request.body caches input for the downstream middleware/router.
    request._body = body
    fingerprint = hashlib.sha256(
        request.method.encode()
        + b"\0"
        + request.url.path.encode()
        + b"?"
        + request.scope["query_string"]
        + b"\0"
        + request.headers.get("content-type", "").encode()
        + b"\0"
        + body
    ).hexdigest()
    previous = await run_in_threadpool(
        reserve, session_factory, principal, key, fingerprint, validate_actor
    )
    if previous is not None:
        return previous
    # A crash/error from this point leaves the durable reservation uncertain.
    response = await call_next(request)
    result = b""
    async for chunk in response.body_iterator:
        result += chunk
        if len(result) > MAX_BODY:
            return error("mcp.outcome_unknown_check_state", 503)
    content_type = response.headers.get("content-type", "application/json")
    try:
        await run_in_threadpool(
            finish, session_factory, principal, key, response.status_code, result, content_type
        )
    except Exception:
        logger.exception("MCP action outcome could not be persisted")
        return error("mcp.outcome_unknown_check_state", 503)
    return Response(
        content=result, status_code=response.status_code, headers=dict(response.headers)
    )
