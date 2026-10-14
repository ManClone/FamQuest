"""Small ASGI tests for the MCP authentication boundary."""
import asyncio
import os
import unittest

os.environ.setdefault("FAMQUEST_MCP_TOKEN", "test-only-token-0123456789-abcdef")
os.environ.setdefault('FAMQUEST_PARENT_TOKEN', 'test-parent-credential-long-enough-12345')
from server import BearerAuth


class AuthTests(unittest.TestCase):
    def test_missing_token_rejected(self):
        called = []
        messages = []

        async def inner(scope, receive, send):
            called.append(True)

        async def send(message):
            messages.append(message)

        scope = {"type": "http", "headers": [], "path": "/mcp"}
        asyncio.run(BearerAuth(inner)(scope, None, send))
        self.assertFalse(called)
        self.assertEqual(messages[0]["status"], 401)

    def test_valid_token_passes(self):
        called = []

        async def inner(scope, receive, send):
            called.append(True)

        async def send(message):
            pass

        token = os.environ["FAMQUEST_MCP_TOKEN"].encode()
        scope = {"type": "http", "headers": [(b"authorization", b"Bearer " + token)]}
        asyncio.run(BearerAuth(inner)(scope, None, send))
        self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
