"""Run the agent team on tickets from the terminal.

    cd hw5/backend
    python run_tickets.py --ticket 101        # one ticket
    python run_tickets.py --all               # every open ticket, oldest first, one after another
    python run_tickets.py --all --reset       # copy the original DB over the working copy first

Every agent step is appended to ../output/audit_trail.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sqlite3

import config
from team import run_ticket


def reset_db() -> None:
    shutil.copyfile(config.ORIGINAL_DB, config.WORKING_DB)
    print(f"[reset] {config.WORKING_DB.name} <- {config.ORIGINAL_DB.name}")


def open_ticket_ids() -> list[int]:
    c = sqlite3.connect(f"file:{config.WORKING_DB}?mode=ro", uri=True)
    try:
        return [r[0] for r in c.execute(
            "SELECT id FROM tickets WHERE status NOT IN ('resolved','rejected') ORDER BY created_at")]
    finally:
        c.close()


async def main(ids: list[int]) -> None:
    for tid in ids:
        print(f"\n=== Ticket {tid} (model {config.MODEL_NAME}) ===")
        try:
            out = await run_ticket(tid)
            print(json.dumps(out.model_dump(), indent=2))
        except Exception as e:  # keep going with the next ticket
            print(f"[ticket {tid}] stopped: {type(e).__name__}: {e}")
    print(f"\n[audit] appended to {config.AUDIT_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Campus Customs agent team")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticket", type=int, help="ticket id to work")
    g.add_argument("--all", action="store_true", help="work every open ticket")
    ap.add_argument("--reset", action="store_true", help="reset the working DB to the original first")
    a = ap.parse_args()
    if a.reset:
        reset_db()
    asyncio.run(main([a.ticket] if a.ticket else open_ticket_ids()))
