"""Cloudflare path match for sharing one origin with the FamQuest web application.

Put this route BEFORE the application's catch-all. Do not strip paths.
Python and Cloudflare's Go regex engine both accept this expression.
"""

MCP_PATH_PATTERN = (
    r"^/(mcp(/.*)?|\.well-known/oauth-(authorization-server|protected-resource)(/.*)?"
    r"|authorize|token|register|revoke|consent|auth/callback)$"
)

# Central mode: OAuth and all discovery routes go to the integrated web app.
# Only MCP protocol traffic goes to the resource-server container.
CENTRAL_MCP_PATH_PATTERN = r"^/mcp(/.*)?$"
