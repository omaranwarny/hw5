"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

- Every agent is a PydanticAI Agent on gpt-6-luna (Portkey) with its own prompt (prompts/<name>.md).
- Shop facts and actions come ONLY from the MCP server (mcp_server/server.py over campus_customs_new.db),
  attached as an MCP toolset. Each agent sees only the MCP tools its role needs (filtered toolset).
- Full connectivity: every agent has delegate(to, task) and can ask ANY other agent. Delegation depth,
  a per-ticket delegation cap, and one shared usage budget per ticket stop loops and runaway token use.
- Every agent-loop step is appended to output/audit_trail.json (audit.py).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.usage import UsageLimits

import config
from audit import AgentAudit
from models import AgentName, AgentReport, TicketOutcome

AGENTS: tuple[str, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

# ---------------------------------------------------------------------------
# Which MCP tools each role may use (least privilege). decide_approval is HUMAN ONLY: no agent gets it.
# ---------------------------------------------------------------------------
COMMON = {"get_today", "get_ticket", "list_open_tickets", "add_ticket_note"}
ROLE_TOOLS: dict[str, set[str]] = {
    "boss": COMMON | {"check_stock", "get_invoice_status", "get_lease_due", "get_pricing", "quote_price",
                      "get_cash_balance", "list_approvals", "update_ticket_status", "record_price_decision"},
    "inventory": COMMON | {"check_stock", "list_vendors", "get_invoice_status", "get_pricing",
                           "create_purchase_order", "fulfill_from_stock", "update_ticket_status"},
    "accounting": COMMON | {"get_cash_balance", "list_open_invoices", "get_invoice_status", "get_lease_due",
                            "get_pricing", "quote_price", "request_payment", "list_approvals", "list_vendors",
                            "update_ticket_status"},
    "facilities": COMMON | {"get_lease_due", "get_cash_balance", "list_approvals", "update_ticket_status"},
    "customer_service": COMMON | {"check_stock", "get_pricing", "quote_price", "draft_customer_message",
                                  "update_ticket_status"},
}
HUMAN_ONLY = {"decide_approval"}
AUTHOR_TOOLS = {"add_ticket_note", "update_ticket_status", "fulfill_from_stock", "create_purchase_order",
                "draft_customer_message", "record_price_decision", "request_payment"}


# ---------------------------------------------------------------------------
# Deps: who is running, how deep, and the shared per-ticket budget
# ---------------------------------------------------------------------------
@dataclass
class Budget:
    delegations: int = 0


@dataclass
class TeamDeps:
    agent: str
    ticket_id: int | None
    session_id: str
    depth: int = 0
    delegated_by: str | None = None
    budget: Budget = field(default_factory=Budget)

    def child(self, to: str) -> "TeamDeps":
        return TeamDeps(agent=to, ticket_id=self.ticket_id, session_id=self.session_id,
                        depth=self.depth + 1, delegated_by=self.agent, budget=self.budget)


LIMITS = UsageLimits(request_limit=config.MAX_REQUESTS_PER_TICKET,
                     tool_calls_limit=config.MAX_TOOL_CALLS_PER_TICKET,
                     total_tokens_limit=config.MAX_TOKENS_PER_TICKET)


# ---------------------------------------------------------------------------
# MCP server (one process, shared by all agents)
# ---------------------------------------------------------------------------
async def _guard_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, tool_args: dict[str, Any]):
    """Runs before every MCP tool call: blocks human-only tools and stamps the REAL agent name as author,
    so an agent can't pretend to be the boss when closing tickets or setting prices."""
    if name in HUMAN_ONLY:
        return {"ok": False, "error": f"{name} is for humans only. Use request_payment to queue it for approval."}
    if name not in ROLE_TOOLS.get(ctx.deps.agent, set()):
        return {"ok": False, "error": f"{ctx.deps.agent} isn't allowed to use {name}."}
    if name in AUTHOR_TOOLS:
        tool_args = {**tool_args, "author": ctx.deps.agent}
    return await call_tool(name, tool_args)


@lru_cache(maxsize=1)
def mcp_server() -> MCPToolset:
    """One MCP server process (stdio) shared by every agent. PydanticAI 2.x: MCPToolset over a FastMCP Client."""
    log = config.ROOT / "output" / "mcp_server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    transport = PythonStdioTransport(config.MCP_SERVER, cwd=str(config.ROOT), python_cmd=config.PYTHON,
                                     log_file=log)
    # Timeouts belong on the FastMCP Client when a pre-built Client is passed to MCPToolset.
    client = Client(transport, init_timeout=30, timeout=60)
    return MCPToolset(client, id="campus-customs-ops", process_tool_call=_guard_tool_call)


def _prompt(name: str) -> str:
    return (config.PROMPTS / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Build the five agents
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def team() -> dict[str, Agent]:
    server = mcp_server()
    agents: dict[str, Agent] = {}
    for name in AGENTS:
        allowed = ROLE_TOOLS[name]
        toolset = server.filtered(lambda ctx, tool_def, allowed=allowed: tool_def.name in allowed)
        agent: Agent = Agent(
            config.make_model(),
            name=name,
            deps_type=TeamDeps,
            output_type=TicketOutcome if name == "boss" else AgentReport,
            instructions=_prompt(name),
            toolsets=[toolset],
            retries=2,
        )

        @agent.instructions
        def situation(ctx: RunContext[TeamDeps]) -> str:
            d = ctx.deps
            others = ", ".join(a for a in AGENTS if a != d.agent)
            return (
                f"\n## Right now\n- You are **{d.agent}**. Ticket: {d.ticket_id}. "
                f"Delegation depth {d.depth}/{config.MAX_DELEGATION_DEPTH}"
                + (f" (asked by {d.delegated_by})" if d.delegated_by else "") + ".\n"
                f"- You can delegate to: {others}. Team delegations used: "
                f"{d.budget.delegations}/{config.MAX_DELEGATIONS_PER_TICKET}.\n"
                "- Tools that write record you as the author automatically. Only database facts; never invent numbers."
            )

        _add_delegate(agent)
        agents[name] = agent
    return agents


def _add_delegate(agent: Agent) -> None:
    @agent.tool
    async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> dict:
        """Ask another Campus Customs agent to do part of the work (full connectivity: any agent can ask any
        other). Give a precise, self-contained task: ticket id, SKU/size/qty or invoice/lease id, and what you
        need back. Returns that agent's report."""
        d = ctx.deps
        if to == d.agent:
            return {"error": "You can't delegate to yourself."}
        if d.depth >= config.MAX_DELEGATION_DEPTH:
            return {"error": f"Delegation depth limit ({config.MAX_DELEGATION_DEPTH}) reached. "
                             "Do it with your own tools or report what's missing."}
        if d.budget.delegations >= config.MAX_DELEGATIONS_PER_TICKET:
            return {"error": f"Team delegation limit ({config.MAX_DELEGATIONS_PER_TICKET}) reached for this "
                             "ticket. Wrap up with what you know."}
        d.budget.delegations += 1
        try:
            report = await run_agent(to, task, d.child(to), usage=ctx.usage)
        except UsageLimitExceeded as e:
            return {"error": f"Token/step budget for this ticket is used up ({e}). Wrap up now."}
        return report.model_dump()


# ---------------------------------------------------------------------------
# Agent loop (with audit), and a ticket run
# ---------------------------------------------------------------------------
async def run_agent(name: str, task: str, deps: TeamDeps, usage=None):
    """Run one agent's loop step by step, appending each step to output/audit_trail.json."""
    agent = team()[name]
    audit = AgentAudit(deps.session_id, deps.ticket_id, name, deps.depth, deps.delegated_by, task)
    run = None
    try:
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=LIMITS) as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    audit.on_response(node.model_response)
                elif Agent.is_model_request_node(node):
                    audit.on_request(node.request)
        out = run.result.output
    except UsageLimitExceeded as e:
        audit.finish(f"stopped: budget ({str(e)[:140]})", usage=_usage(run))
        raise
    except Exception as e:
        audit.finish(f"error: {type(e).__name__}: {str(e)[:160]}", usage=_usage(run))
        raise
    audit.finish("completed", output=out, usage=_usage(run))
    return out


def _usage(run):
    if run is None:
        return None
    try:
        return run.usage  # a property in PydanticAI 2.x
    except Exception:
        return None


async def run_ticket(ticket_id: int) -> TicketOutcome:
    """The Boss takes one ticket end to end, delegating as needed. One MCP process for the whole run."""
    session = uuid.uuid4().hex[:8]
    deps = TeamDeps(agent="boss", ticket_id=int(ticket_id), session_id=session)
    async with mcp_server():
        return await run_agent("boss", f"Work ticket {ticket_id} end to end. Start with get_today and "
                                       f"get_ticket({ticket_id}).", deps)
