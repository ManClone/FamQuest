import re
import unittest

from fastmcp.server.auth.providers.github import GitHubProvider
from routing import CENTRAL_MCP_PATH_PATTERN, MCP_PATH_PATTERN


class SharedOriginTests(unittest.TestCase):
    def test_central_oauth_stays_with_web_application(self):
        for path in ["/mcp", "/mcp/", "/mcp/session"]:
            self.assertIsNotNone(re.fullmatch(CENTRAL_MCP_PATH_PATTERN, path))
        for path in ["/authorize", "/token", "/register", "/revoke", "/login",
                     "/.well-known/oauth-protected-resource/mcp",
                     "/.well-known/oauth-authorization-server", "/mcpx"]:
            self.assertIsNone(re.fullmatch(CENTRAL_MCP_PATH_PATTERN, path))

    def test_all_oauth_and_mcp_routes_reach_mcp_but_app_routes_do_not(self):
        provider = GitHubProvider(
            client_id="test-client",
            client_secret="test-only-secret",
            base_url="https://famquest.example.org",
            jwt_signing_key="s" * 40,
        )
        paths = [route.path for route in provider.get_routes(mcp_path="/mcp")]
        self.assertIn("/auth/callback", paths)
        for path in paths + [
            "/mcp",
            "/mcp/",
            "/.well-known/oauth-protected-resource/mcp",
        ]:
            with self.subTest(path=path):
                self.assertIsNotNone(re.fullmatch(MCP_PATH_PATTERN, path))
        for path in [
            "/",
            "/parents/profile",
            "/api/auth/login",
            "/api/tasks",
            "/assets/app.js",
            "/household",
            "/mcpx",
            "/authorize-extra",
        ]:
            with self.subTest(path=path):
                self.assertIsNone(re.fullmatch(MCP_PATH_PATTERN, path))
