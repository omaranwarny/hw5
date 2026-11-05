"""Pydantic / PydanticAI data types for the Campus Customs agent team."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_approval", "waiting_customer", "resolved", "rejected"]


class AgentReport(BaseModel):
    """What a specialist (inventory / accounting / facilities / customer_service) hands back."""

    agent: AgentName
    ticket_id: int | None = None
    summary: str = Field(description="2-4 sentences: what you found and did")
    facts: list[str] = Field(default_factory=list, description="Key numbers from tools, e.g. 'tee S on hand 0'")
    actions_taken: list[str] = Field(default_factory=list, description="Writes you made: notes, drafts, requests")
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests you created (pending human)")
    draft_ids: list[int] = Field(default_factory=list, description="Board drafts you created")
    blocked_on: list[str] = Field(default_factory=list, description="What is stopping progress")
    next_steps: list[str] = Field(default_factory=list)


class TicketOutcome(BaseModel):
    """The Boss's final result for one ticket."""

    ticket_id: int
    final_status: TicketStatus
    decision: str = Field(description="2-4 sentences: the call you made and why")
    actions_taken: list[str] = Field(default_factory=list, description="Everything the team did, in order")
    approvals_waiting: list[int] = Field(default_factory=list, description="Approval ids a human must decide")
    draft_ids: list[int] = Field(default_factory=list)
    human_next_steps: list[str] = Field(default_factory=list,
                                        description="e.g. 'Approve #1 (invoice 501, $840) before #3'")


# ---------------------------------------------------------------------------
# Audit trail (output/audit_trail.json, append-only)
# ---------------------------------------------------------------------------
class AuditToolCall(BaseModel):
    name: str
    args: dict = Field(default_factory=dict)
    result: str = "(pending)"
    ok: bool = True


class AuditEntry(BaseModel):
    """One agent-loop step of one agent. Many per ticket; the file is never wiped."""

    session_id: str = Field(description="Same for the whole ticket run (all agents)")
    ticket_id: int | None
    agent: AgentName
    depth: int = Field(description="0 = boss; 1 = delegated by boss; 2 = delegated by a specialist")
    delegated_by: AgentName | None = None
    run_id: str = Field(description="One agent's run")
    step: int
    timestamp: str
    model: str
    task: str = Field(description="What this agent was asked (first 300 chars)")
    thoughts: list[str] = Field(default_factory=list)
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    retries: list[str] = Field(default_factory=list)
    output: str | None = Field(default=None, description="Final output preview (last step)")
    stop_reason: str | None = None
    usage: dict[str, int] | None = Field(default=None, description="Ticket-wide usage so far (last step)")
