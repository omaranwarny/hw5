"""The backend's own MCP client: dashboard routes read and approve through the MCP server, like the agents."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

import config

_client: Client | None = None
_lock = asyncio.Lock()


def _make() -> Client:
    log = config.ROOT / "output" / "mcp_server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    transport = PythonStdioTransport(config.MCP_SERVER, cwd=str(config.ROOT), python_cmd=config.PYTHON,
                                     log_file=log, keep_alive=True)
    return Client(transport, init_timeout=30, timeout=60)


def _data(result: Any) -> Any:
    for attr in ("structured_content", "data"):
        v = getattr(result, attr, None)
        if v:
            return v.get("result", v) if isinstance(v, dict) and set(v) == {"result"} else v
    content = getattr(result, "content", None) or []
    return json.loads(content[0].text) if content else result


async def call(tool: str, args: dict | None = None) -> Any:
    """Call one MCP tool. One shared client; calls are serialized so SQLite never sees two writers."""
    global _client
    async with _lock:
        if _client is None:
            _client = _make()
        async with _client:
            return _data(await _client.call_tool(tool, args or {}))
