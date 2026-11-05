"""Append-only audit trail -> output/audit_trail.json (one entry per agent-loop step)."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime

from pydantic_ai.messages import (ModelRequest, ModelResponse, RetryPromptPart, TextPart, ThinkingPart,
                                  ToolCallPart, ToolReturnPart)

from config import AUDIT_PATH, MODEL_NAME
from models import AuditEntry, AuditToolCall

_lock = threading.Lock()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def short(x: object, n: int = 220) -> str:
    s = " ".join(str(x).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def summarize(content: object) -> tuple[str, bool]:
    d = content.model_dump() if hasattr(content, "model_dump") else content
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except (json.JSONDecodeError, TypeError):
            return short(d), True
    if isinstance(d, dict):
        if d.get("ok") is False or d.get("found") is False or "error" in d or "refused" in d:
            return "REFUSED/ERROR: " + short(d.get("error") or d.get("refused") or d), False
        if "summary" in d and "agent" in d:                          # AgentReport from a delegate
            return f"{d['agent']} report: {short(d['summary'], 180)}", True
        return short(json.dumps(d, default=str)), True
    return short(d), True


def append(entry: AuditEntry) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        try:
            data = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:   # never destroy history
            AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.broken-{int(time.time())}.json"))
            data = []
        data.append(entry.model_dump())
        tmp = AUDIT_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(AUDIT_PATH)


class AgentAudit:
    """Records one agent run, appending an entry per model step (response + its tool results)."""

    def __init__(self, session_id: str, ticket_id: int | None, agent: str, depth: int,
                 delegated_by: str | None, task: str):
        self.base = dict(session_id=session_id, ticket_id=ticket_id, agent=agent, depth=depth,
                         delegated_by=delegated_by, run_id=uuid.uuid4().hex[:8], model=MODEL_NAME,
                         task=short(task, 300))
        self.step = 0
        self.pending: AuditEntry | None = None
        self.ids: list[str] = []

    def on_response(self, resp: ModelResponse) -> None:
        self._flush()
        self.step += 1
        thoughts, calls, ids = [], [], []
        for p in resp.parts:
            if isinstance(p, (TextPart, ThinkingPart)) and p.content.strip():
                thoughts.append(short(p.content, 500))
            elif isinstance(p, ToolCallPart):
                args = {k: (short(v, 160) if isinstance(v, str) else v) for k, v in p.args_as_dict().items()}
                calls.append(AuditToolCall(name=p.tool_name, args=args))
                ids.append(p.tool_call_id)
        self.pending = AuditEntry(step=self.step, timestamp=now(), thoughts=thoughts, tool_calls=calls, **self.base)
        self.ids = ids

    def on_request(self, req: ModelRequest) -> None:
        if not self.pending:
            return
        for p in req.parts:
            if isinstance(p, ToolReturnPart) and p.tool_call_id in self.ids:
                c = self.pending.tool_calls[self.ids.index(p.tool_call_id)]
                c.result, c.ok = summarize(p.content)
            elif isinstance(p, RetryPromptPart):
                self.pending.retries.append(short(p.content if isinstance(p.content, str) else p.content, 240))
                if p.tool_call_id in self.ids:
                    c = self.pending.tool_calls[self.ids.index(p.tool_call_id)]
                    c.result, c.ok = "retry requested", False
        self._flush()

    def finish(self, stop_reason: str, output: object = None, usage: object = None) -> None:
        e = self.pending or AuditEntry(step=self.step + 1, timestamp=now(), **self.base)
        for c in e.tool_calls:
            if c.result == "(pending)":
                c.result = "final output delivered" if stop_reason == "completed" else "not completed"
        e.stop_reason = stop_reason
        if output is not None:
            e.output = short(output.model_dump_json() if hasattr(output, "model_dump_json") else output, 4000)
        if usage is not None:
            e.usage = {k: int(getattr(usage, k)) for k in ("requests", "tool_calls", "input_tokens", "output_tokens")
                       if isinstance(getattr(usage, k, None), int)}
        append(e)
        self.pending = None

    def _flush(self) -> None:
        if self.pending and self.pending.tool_calls:
            append(self.pending)
            self.pending = None
