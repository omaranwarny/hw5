"""Campus Customs Ops API (FastAPI) for the React dashboard.

Run from hw5/backend/:
    uvicorn main:app --reload --port 8000

Shop data always goes through the MCP server (mcp_client.py); agents run via team.py.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import traceback
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import mcp_client
from team import run_ticket

app = FastAPI(title="Campus Customs Ops API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# One ticket run at a time: tickets share one checking account, so runs must see each other's approvals.
RUN_LOCK = asyncio.Lock()
RUNS: dict[int, dict] = {}      # ticket_id -> {status, started_at, finished_at, outcome|error}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def mcp(tool: str, args: dict | None = None):
    try:
        return await mcp_client.call(tool, args)
    except Exception as e:  # the MCP server is down or the DB is missing
        raise HTTPException(status_code=503, detail=f"MCP server error ({tool}): {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict:
    today = await mcp("get_today")
    return {"ok": True, "model": config.MODEL_NAME, "shop_date": today["date_today"],
            "database": config.WORKING_DB.name, "running": RUN_LOCK.locked()}


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
@app.get("/api/tickets")
async def tickets() -> dict:
    """All tickets with status and state ('open' / 'resolved'), plus any run in progress."""
    data = await mcp("list_tickets", {"status": "all"})
    for t in data["tickets"]:
        t["run"] = RUNS.get(t["id"])
    return data


@app.get("/api/tickets/{ticket_id}")
async def ticket(ticket_id: int) -> dict:
    """One ticket with its notes, board drafts (POs, customer messages, quotes) and approvals."""
    data = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(status_code=404, detail=data.get("error", "Ticket not found"))
    data["run"] = RUNS.get(ticket_id)
    return data


async def _run_in_background(ticket_id: int) -> None:
    async with RUN_LOCK:
        RUNS[ticket_id] = {"status": "running", "started_at": _now()}
        try:
            outcome = await run_ticket(ticket_id)
            RUNS[ticket_id] = {**RUNS[ticket_id], "status": "done", "finished_at": _now(),
                               "outcome": outcome.model_dump()}
        except Exception as e:
            RUNS[ticket_id] = {**RUNS[ticket_id], "status": "error", "finished_at": _now(),
                               "error": f"{type(e).__name__}: {str(e)[:300]}"}
            traceback.print_exc()


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run(ticket_id: int) -> dict:
    """Start the agent team on one ticket (Boss first). Returns immediately; poll /api/events and
    /api/tickets/{id} to watch it. Only one run at a time."""
    data = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(status_code=404, detail=data.get("error", "Ticket not found"))
    if RUN_LOCK.locked():
        raise HTTPException(status_code=409, detail="The team is already working a ticket. Try again when it finishes.")
    RUNS[ticket_id] = {"status": "queued", "started_at": _now()}
    asyncio.create_task(_run_in_background(ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "status": "started"}


@app.get("/api/runs")
def runs() -> dict:
    return {"running": RUN_LOCK.locked(), "runs": RUNS}


# ---------------------------------------------------------------------------
# Agent events (from the append-only audit trail)
# ---------------------------------------------------------------------------
@app.get("/api/events")
def events(since: int = Query(0, ge=0, description="return entries with index >= since"),
           ticket_id: int | None = None, limit: int = Query(200, ge=1, le=1000)) -> dict:
    """Recent agent-loop steps: which agent, what it said (thoughts/output), which tools it used and what they
    returned. Use `next_since` to fetch only new events on the next refresh."""
    trail = _load_trail()
    out = []
    for i, e in enumerate(trail):
        if i < since or (ticket_id is not None and e.get("ticket_id") != ticket_id):
            continue
        out.append({
            "index": i, "timestamp": e.get("timestamp"), "session_id": e.get("session_id"),
            "ticket_id": e.get("ticket_id"), "agent": e.get("agent"), "depth": e.get("depth"),
            "delegated_by": e.get("delegated_by"), "step": e.get("step"), "task": e.get("task"),
            "said": e.get("thoughts") or [], "tools": e.get("tool_calls") or [],
            "output": e.get("output"), "stop_reason": e.get("stop_reason"), "usage": e.get("usage"),
        })
    out = out[-limit:]
    return {"count": len(out), "total": len(trail), "next_since": len(trail), "events": out}


def _load_trail() -> list[dict]:
    try:
        return json.loads(config.AUDIT_PATH.read_text(encoding="utf-8")) if config.AUDIT_PATH.exists() else []
    except json.JSONDecodeError:
        return []


def _parse_output(text: str | None) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Older audit entries were cut short; recover the readable fields.
        out: dict = {}
        for key in ("summary", "decision", "final_status"):
            m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)', text)
            if m:
                out[key] = m.group(1).replace('\\"', '"')
        return out or {"summary": text[:400]}


@app.get("/api/tickets/{ticket_id}/summary")
def ticket_summary(ticket_id: int, session_id: str | None = None) -> dict:
    """What each agent did on a ticket's latest run (or a given session): steps, tools used, who asked it,
    and its own final summary. Built from the audit trail."""
    trail = [e for e in _load_trail() if e.get("ticket_id") == ticket_id]
    if not trail:
        return {"ticket_id": ticket_id, "session_id": None, "agents": [], "sessions": []}
    sessions = list(dict.fromkeys(e["session_id"] for e in trail))
    sid = session_id or sessions[-1]
    agents: dict[str, dict] = {}
    for e in trail:
        if e["session_id"] != sid:
            continue
        a = agents.setdefault(e["agent"], {"agent": e["agent"], "runs": 0, "steps": 0, "tools": {},
                                           "asked_by": [], "summary": None, "facts": [], "actions": [],
                                           "approval_ids": [], "draft_ids": [], "refused": 0})
        a["steps"] += 1
        if e.get("delegated_by") and e["delegated_by"] not in a["asked_by"]:
            a["asked_by"].append(e["delegated_by"])
        for t in e.get("tool_calls") or []:
            if t["name"] == "final_result":
                continue
            a["tools"][t["name"]] = a["tools"].get(t["name"], 0) + 1
            if not t.get("ok", True):
                a["refused"] += 1
        if e.get("stop_reason"):
            a["runs"] += 1
            out = _parse_output(e.get("output"))
            a["summary"] = out.get("summary") or out.get("decision") or a["summary"]
            a["facts"] += out.get("facts", [])
            a["actions"] += out.get("actions_taken", [])
            a["approval_ids"] += out.get("approval_ids", []) + out.get("approvals_waiting", [])
            a["draft_ids"] += out.get("draft_ids", [])
            if e["agent"] == "boss":
                a["final_status"] = out.get("final_status")
                a["human_next_steps"] = out.get("human_next_steps", [])
            if e["stop_reason"] != "completed":
                a["summary"] = f"Stopped: {e['stop_reason']}"
    order = ["boss", "inventory", "accounting", "facilities", "customer_service"]
    usage = next((e.get("usage") for e in reversed(trail) if e["session_id"] == sid and e.get("usage")), None)
    return {"ticket_id": ticket_id, "session_id": sid, "sessions": sessions, "usage": usage,
            "agents": sorted(agents.values(), key=lambda x: order.index(x["agent"]) if x["agent"] in order else 9)}


# ---------------------------------------------------------------------------
# Money: approvals (HUMAN ONLY) and cash
# ---------------------------------------------------------------------------
class Decision(BaseModel):
    approver: str = Field(min_length=2, max_length=60, description="The human approving or rejecting")
    note: str = Field(default="", max_length=300)


@app.get("/api/approvals")
async def approvals(status: str = Query("all", pattern="^(all|pending|approved|rejected)$")) -> dict:
    """Payment / purchase-order requests the agents prepared."""
    return await mcp("list_approvals", {"status": status})


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: Decision) -> dict:
    """A human approved it: this is the ONLY route that moves money. Through MCP decide_approval it pays from
    checking (refused if the balance would go negative), writes payments.approved_by, and marks the invoice
    paid / moves the lease due date / approves the PO."""
    res = await mcp("decide_approval", {"approval_id": approval_id, "decision": "approve",
                                        "approver": body.approver.strip(), "note": body.note})
    if not res.get("ok"):
        raise HTTPException(status_code=409 if res.get("refused") else 400, detail=res.get("error"))
    return res


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: Decision) -> dict:
    """A human rejected it: nothing is paid."""
    res = await mcp("decide_approval", {"approval_id": approval_id, "decision": "reject",
                                        "approver": body.approver.strip(), "note": body.note})
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.get("/api/cash")
async def cash() -> dict:
    """Current checking balance (cash_accounts), pending approvals, and payments made."""
    return await mcp("get_cash_balance")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------
@app.post("/api/reset")
async def reset() -> dict:
    """Copy data/campus_customs.db over data/campus_customs_new.db (original values) for a fresh run.
    The audit trail is NOT wiped (append-only); a 'reset' marker is recorded in the response only."""
    if RUN_LOCK.locked():
        raise HTTPException(status_code=409, detail="Can't reset while the team is working a ticket.")
    if not config.ORIGINAL_DB.exists():
        raise HTTPException(status_code=500, detail="Original database data/campus_customs.db is missing.")
    async with mcp_client._lock:   # no MCP call mid-copy
        shutil.copyfile(config.ORIGINAL_DB, config.WORKING_DB)
    RUNS.clear()
    after = await mcp("get_cash_balance")
    return {"ok": True, "reset_at": _now(), "checking_balance": after["checking_balance"],
            "message": f"{config.WORKING_DB.name} restored from {config.ORIGINAL_DB.name}."}
