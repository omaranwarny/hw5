"""Human approval desk (terminal), until the React dashboard exists. Goes through the MCP server too.

    python approve.py --list
    python approve.py --approve 1 --by "Omar"
    python approve.py --reject 3 --by "Omar" --note "wait for cash"
"""
from __future__ import annotations

import argparse
import asyncio
import json

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

import config


def _data(result):
    for attr in ("structured_content", "data"):
        v = getattr(result, attr, None)
        if v:
            return v
    content = getattr(result, "content", None) or []
    return json.loads(content[0].text) if content else result


async def call(tool: str, args: dict):
    log = config.ROOT / "output" / "mcp_server.log"
    transport = PythonStdioTransport(config.MCP_SERVER, cwd=str(config.ROOT), python_cmd=config.PYTHON, log_file=log)
    async with Client(transport) as c:
        return _data(await c.call_tool(tool, args))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Approve or reject payment requests (human only)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--approve", type=int)
    ap.add_argument("--reject", type=int)
    ap.add_argument("--by", help="your name (required to decide)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.approve or a.reject:
        if not a.by:
            ap.error("--by <your name> is required")
        res = asyncio.run(call("decide_approval", {"approval_id": a.approve or a.reject,
                                                    "decision": "approve" if a.approve else "reject",
                                                    "approver": a.by, "note": a.note}))
    else:
        res = asyncio.run(call("list_approvals", {"status": "all"}))
    print(json.dumps(res, indent=2, default=str))
