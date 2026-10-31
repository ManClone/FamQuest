# FamQuest OAuth 2.0 / PKCE implementation checklist

Status: design and acceptance criteria only; NOT a working OAuth provider.

## Authorization server

- Use FamQuest's own login and central `famquest_auth` identities; no Auth0.
- Register OAuth clients with exact redirect URI allowlists; disallow wildcard and open redirects.
- Authorization Code flow with PKCE S256 only; reject `plain`, missing challenge, mismatched verifier, and reused codes.
- Require `state` handling by clients; validate authorization requests and consent where applicable.
- Short-lived single-use authorization codes bound to client, redirect URI, user and PKCE challenge.
- Issue short-lived access tokens with audience, issuer, subject, expiry and explicit scopes; rotate and revoke refresh tokens with reuse detection.
- Store only hashes of opaque secrets/codes/tokens where possible; redact them from logs.
- Protect login, authorization, token and revocation endpoints against CSRF, brute force and replay; enforce HTTPS.

## Tenant routing and authorization

- Resolve identity and active membership from `famquest_auth` on every security-sensitive request.
- Bind the authorized tenant to the server-side session/token; never trust a request-supplied database name or tenant identifier.
- For multiple active memberships, require an explicit authorized tenant selection instead of guessing.
- Superadmin has no implicit access to tenant data.
- Route API and MCP requests through the same authorization boundary; verify scope and tenant on every operation.
- Use distinct least-privilege PostgreSQL credentials for each family database.

## Release gates

1. Integration tests: PKCE success/failure, code replay, redirect mismatch, expired/revoked tokens and tenant switching.
2. Isolation tests: Grasser, Sertl and Henning cannot read or mutate each other's resources, including via MCP.
3. Rehearse account migration on restored test backup; preserve IDs and verify record counts and rollback.
4. Verify tenant provisioning and offboarding including uploads, backups and credential revocation.
5. Only after passing CI and manual staging validation plan a separately approved QNAP rollout.
