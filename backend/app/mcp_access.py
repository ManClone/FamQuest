"""Explicit MCP service boundary; browser cookies are never reused."""

import re
from copy import deepcopy

READ = (
    r"/api/(maintenance/consistency|rewards/members)",
    r"/api/(members|profile|today|tasks|tasks/week|approvals|chore-approvals/confirmed)",
    r"/api/members/[0-9]+/(points|progress|praise|penalties)",
    r"/api/(chores|chores/weekly-preview|chores/weekly-confirmed)",
    r"/api/(routines|todos|rewards|redemptions)",
    r"/api/(calendar/week|calendar/upcoming|meals/week|meals/settings|dishes)",
    r"/api/shopping/(list|items)",
)
WRITE = (
    r"/api/(?:approvals|chore-approvals)/[0-9]+",
    r"/api/chore-approvals/[0-9]+/confirmed",
    r"/api/members/[0-9]+/(?:praise|points)",
    r"/api/members/[0-9]+/praise/[0-9]+/revoke",
    r"/api/members/[0-9]+/penalties/[0-9]+/reverse",
    r"/api/members/[0-9]+/points/[0-9]+/reverse",
    r"/api/redemptions/[0-9]+/cancel",
    r"/api/tasks(?:/[0-9]+|/schedule)?",
    r"/api/routines(?:/[0-9]+(?:/days|/steps)?)?",
    r"/api/chores(?:/[0-9]+(?:/done)?|/rooms(?:/[0-9]+)?|/weekly-confirmed)?",
    r"/api/todos(?:/[0-9]+(?:/done)?)?",
    r"/api/rewards(?:/[0-9]+)?",
    r"/api/meals/(?:settings|[0-9-]+/[a-z]+)",
    r"/api/dishes/[0-9]+",
    r"/api/shopping/(?:list(?:/[0-9]+(?:/checked)?|/checked)?|items/[0-9]+)",
)


def allowed(method: str, path: str) -> bool:
    if method == "GET" and path == "/api/internal/mcp/schema":
        return True
    patterns = READ if method == "GET" else WRITE if method in {"POST", "PUT", "DELETE"} else ()
    return any(re.fullmatch(pattern, path) for pattern in patterns)


def tool_schema(spec: dict) -> dict:
    result = deepcopy(spec)
    result["paths"] = {}
    for path, operations in spec["paths"].items():
        # Validate path templates against the same boundary as real requests.
        sample = re.sub(r"\{[^}]+\}", "1", path)
        if "/meals/{date}/{meal}" in path:
            sample = "/api/meals/2026-10-16/dinner"
        kept = {}
        for method, operation in operations.items():
            if not allowed(method.upper(), sample) or "/internal/" in path:
                continue
            operation = deepcopy(operation)
            if method != "get":
                operation.setdefault("parameters", []).append(
                    {
                        "name": "X-MCP-Request-Key",
                        "in": "header",
                        "required": True,
                        "description": "UUID action key; reuse for retries.",
                        "schema": {"type": "string", "minLength": 16, "maxLength": 128},
                    }
                )
            if method != "get" and ("approvals/" in path or path.endswith(("/revoke", "/reverse"))):
                operation.setdefault("parameters", []).append(
                    {
                        "name": "X-MCP-Parent-Confirmed",
                        "in": "header",
                        "required": True,
                        "description": "True ONLY after explicit parent confirmation.",
                        "schema": {"type": "string", "enum": ["true"]},
                    }
                )
                operation["description"] = (
                    "Never decide automatically. Ask the parent to confirm the exact approval "
                    "and decision before calling this tool. " + operation.get("description", "")
                )
            kept[method] = operation
        if kept:
            result["paths"][path] = kept
    return result
