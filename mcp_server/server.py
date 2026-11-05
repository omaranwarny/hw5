"""Campus Customs operations MCP server (FastMCP).

Every agent in HW5 reaches the shop's business systems ONLY through these tools.
Database: ../data/campus_customs_new.db  (the working copy; campus_customs.db stays untouched).
Rules baked in: "today" is desk.date_today, not the computer's clock; every answer comes from
the database, and anything missing is reported as missing, never guessed.

Tables added to the WORKING COPY only (created on first use): approvals (human-approval queue)
and board_drafts (purchase orders, customer messages, price quotes that stay on the board).

Run (stdio):  python server.py
Run (HTTP):   python server.py --http      ->  http://127.0.0.1:8001/mcp
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = Path(os.getenv("CC_DB_PATH", ROOT / "data" / "campus_customs_new.db")).resolve()

mcp = FastMCP("campus-customs-ops")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rows(sql: str, params: tuple = ()) -> list[dict]:
    """Read-only query (mode=ro). Read tools use this, so they can never change the database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Working database not found at {DB_PATH}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _today() -> str:
    """The shop's 'today' (desk.date_today). Rule: use this, not the real date."""
    rows = _rows("SELECT date_today FROM desk LIMIT 1")
    if not rows:
        raise ValueError("desk.date_today is missing, so 'today' is unknown.")
    return rows[0]["date_today"]


def _days_between(start: str, end: str) -> int:
    """Whole days from start to end (ISO dates); negative if end is before start."""
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


# ---------------------------------------------------------------------------
# Tool logic (plain functions, easy to test)
# ---------------------------------------------------------------------------
def check_stock_logic(sku: str, size: str, qty_needed: int = 1) -> dict:
    sku_n, size_n = sku.strip().upper(), size.strip().upper()
    rows = _rows("SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size", (sku_n,))
    if not rows:
        known = [r["sku"] for r in _rows("SELECT DISTINCT sku FROM inventory ORDER BY sku")]
        return {"found": False, "error": f"No inventory rows for SKU '{sku_n}'.", "known_skus": known}
    row = next((r for r in rows if r["size"] == size_n), None)
    all_sizes = {r["size"]: r["qty"] for r in rows}
    if row is None:
        return {"found": False, "sku": sku_n, "name": rows[0]["name"],
                "error": f"SKU {sku_n} has no size '{size_n}' in inventory.", "sizes_on_hand": all_sizes}
    need = max(int(qty_needed), 0)
    shortfall = max(need - row["qty"], 0)
    return {
        "found": True,
        "sku": row["sku"], "name": row["name"], "size": row["size"], "location": row["location"],
        "qty_on_hand": row["qty"],
        "qty_needed": need,
        "can_fill_from_stock": shortfall == 0,
        "shortfall": shortfall,
        "sizes_on_hand": all_sizes,
        "as_of": _today(),
    }


def get_invoice_status_logic(invoice_id: int) -> dict:
    today = _today()
    inv = _rows(
        "SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description, "
        "v.name AS vendor_name, v.specialty, v.lead_days "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (int(invoice_id),))
    if not inv:
        return {"found": False, "error": f"No invoice with id {invoice_id}."}
    i = inv[0]
    days_past_due = _days_between(i["due_date"], today)
    open_for_vendor = _rows(
        "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (i["vendor_id"],))
    paid_rows = _rows("SELECT id, amount, paid_at, approved_by FROM payments WHERE kind = 'invoice' AND ref_id = ?",
                      (i["id"],))
    blocked = len(open_for_vendor) > 0
    return {
        "found": True,
        "invoice_id": i["id"], "description": i["description"], "amount": i["amount"],
        "due_date": i["due_date"], "status": i["status"],
        "today": today,
        "overdue": i["status"] == "open" and days_past_due > 0,
        "days_past_due": max(days_past_due, 0),
        "vendor": {"id": i["vendor_id"], "name": i["vendor_name"], "specialty": i["specialty"],
                   "lead_days": i["lead_days"]},
        "vendor_open_invoices": open_for_vendor,
        "vendor_open_total": round(sum(r["amount"] for r in open_for_vendor), 2),
        # Shop rule: a vendor will not ship new product while it has an open unpaid invoice.
        "vendor_will_ship": not blocked,
        "ship_block_reason": (f"{i['vendor_name']} has {len(open_for_vendor)} open unpaid invoice(s); "
                              "it won't ship new product until they are paid.") if blocked else None,
        "payments_recorded": paid_rows,
    }


def get_lease_due_logic(lease_id: int) -> dict:
    today = _today()
    lease = _rows("SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
                  (int(lease_id),))
    if not lease:
        return {"found": False, "error": f"No lease with id {lease_id}."}
    l = lease[0]
    days_until = _days_between(today, l["next_due"])
    cash = _rows("SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'")
    balance = cash[0]["balance"] if cash else None
    paid_rows = _rows("SELECT id, amount, paid_at, approved_by FROM payments WHERE kind = 'rent' AND ref_id = ?",
                      (l["id"],))
    return {
        "found": True,
        "lease_id": l["id"], "space_name": l["space_name"], "landlord": l["landlord"],
        "monthly_rent": l["monthly_rent"], "next_due": l["next_due"], "notes": l["notes"],
        "today": today,
        "days_until_due": days_until,
        "overdue": days_until < 0,
        "checking_balance": balance,
        "checking_as_of": cash[0]["date"] if cash else None,
        "can_cover_from_checking": balance is not None and balance >= l["monthly_rent"],
        "balance_after_rent": None if balance is None else round(balance - l["monthly_rent"], 2),
        "payments_recorded": paid_rows,
        "note": "Paying rent needs human approval; this tool only reports.",
    }


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------
@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Stock on hand for one SKU and size, compared with how many a ticket needs.

    Returns qty_on_hand, shortfall (how many are missing), can_fill_from_stock, the shelf
    location, and the counts for every other size of that SKU. Reads: inventory (+ desk for the date).
    Example: check_stock("CC-HOOD-NAVY", "M", 20) for a 20-hoodie order.
    """
    return check_stock_logic(sku, size, qty_needed)


@mcp.tool
def get_invoice_status(invoice_id: int) -> dict:
    """One vendor invoice: amount, due date, open/paid, days past due (using desk.date_today),
    the vendor's name, specialty and lead_days, and whether that vendor will ship new product
    (a vendor won't ship while it has ANY open unpaid invoice). Reads: invoices, vendors, payments, desk.
    """
    return get_invoice_status_logic(invoice_id)


@mcp.tool
def get_lease_due(lease_id: int) -> dict:
    """Rent for one lease: monthly_rent, next_due, days until due (from desk.date_today), whether
    it's overdue, the checking balance, and whether checking can cover it without going negative.
    Read-only. Paying rent is a separate, human-approved step. Reads: leases, cash_accounts, payments, desk.
    """
    return get_lease_due_logic(lease_id)


# ===========================================================================
# Problem 5: more tools for the agent team
# ===========================================================================
import json  # noqa: E402

MIN_MARGIN_PCT = 40.0          # shop policy: a discounted price must keep >= 40% gross margin
MAX_DISCOUNT_PCT = 25.0        # shop policy: never more than 25% off list
BULK_MIN_QTY = 10              # discounts are only for orders of 10+ units
TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "waiting_customer", "resolved", "rejected")
AGENTS = ("boss", "inventory", "accounting", "facilities", "customer_service")


def _write():
    """Read-write connection for the write tools (one transaction per call)."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found at {DB_PATH}.")
    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_board_tables() -> None:
    """Approval queue + board drafts live only in the working copy (reset = copy the original again)."""
    conn = _write()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,                 -- 'invoice' | 'rent' | 'purchase_order'
            ref_id INTEGER NOT NULL,            -- invoices.id | leases.id | board_drafts.id (PO)
            amount REAL NOT NULL,
            payee TEXT NOT NULL,
            ticket_id INTEGER,
            reason TEXT NOT NULL,
            requested_by TEXT NOT NULL,         -- agent name
            status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
            created_at TEXT NOT NULL,
            decided_by TEXT,
            decided_at TEXT,
            decision_note TEXT,
            payment_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS board_drafts (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            kind TEXT NOT NULL,                 -- 'purchase_order' | 'customer_message' | 'price_quote'
            author TEXT NOT NULL,               -- agent name
            status TEXT NOT NULL,               -- draft | blocked_vendor_hold | pending_approval | approved | final
            payload TEXT NOT NULL,              -- JSON
            created_at TEXT NOT NULL
        );
        """)
        conn.commit()
    finally:
        conn.close()


def _agent_ok(name: str) -> str:
    n = (name or "").strip().lower().replace(" ", "_")
    if n not in AGENTS:
        raise ValueError(f"Unknown agent '{name}'. Use one of {AGENTS}.")
    return n


def _note_line(author: str, text: str) -> str:
    return f"[{_today()} {author}] {' '.join(text.split())[:600]}"


# ---------- reads ----------
def get_today_logic() -> dict:
    d = _rows("SELECT date_today, notes FROM desk LIMIT 1")[0]
    return {"date_today": d["date_today"], "desk_notes": d["notes"]}


def list_open_tickets_logic() -> dict:
    rows = _rows("SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
                 "FROM tickets WHERE status NOT IN ('resolved','rejected') ORDER BY created_at")
    return {"today": _today(), "count": len(rows), "tickets": rows}


def list_tickets_logic(status: str = "all") -> dict:
    _ensure_board_tables()
    rows = _rows("SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
                 "FROM tickets ORDER BY created_at")
    if status != "all":
        rows = [r for r in rows if r["status"] == status]
    for r in rows:
        r["state"] = "resolved" if r["status"] in ("resolved", "rejected") else "open"
        r["pending_approvals"] = _rows("SELECT COUNT(*) AS n FROM approvals WHERE ticket_id = ? AND status = 'pending'",
                                       (r["id"],))[0]["n"]
        r["drafts"] = _rows("SELECT COUNT(*) AS n FROM board_drafts WHERE ticket_id = ?", (r["id"],))[0]["n"]
    return {"today": _today(), "count": len(rows), "tickets": rows}


def get_ticket_logic(ticket_id: int) -> dict:
    t = _rows("SELECT * FROM tickets WHERE id = ?", (int(ticket_id),))
    if not t:
        return {"found": False, "error": f"No ticket with id {ticket_id}."}
    _ensure_board_tables()
    drafts = _rows("SELECT id, kind, author, status, payload, created_at FROM board_drafts WHERE ticket_id = ? ORDER BY id",
                   (int(ticket_id),))
    for d in drafts:
        d["payload"] = json.loads(d["payload"])
    approvals = _rows("SELECT id, kind, ref_id, amount, payee, status, requested_by, decided_by FROM approvals "
                      "WHERE ticket_id = ? ORDER BY id", (int(ticket_id),))
    return {"found": True, "today": _today(), "ticket": t[0], "board_drafts": drafts, "approvals": approvals}


def list_vendors_logic(specialty: str | None = None) -> dict:
    rows = _rows("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
    if specialty:
        rows = [r for r in rows if specialty.lower() in r["specialty"].lower()]
    for r in rows:
        open_inv = _rows("SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'", (r["id"],))
        r["open_invoices"] = open_inv
        r["will_ship"] = not open_inv
    return {"today": _today(), "vendors": rows}


def get_pricing_logic(sku: str) -> dict:
    sku_n = sku.strip().upper()
    p = _rows("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku_n,))
    if not p:
        return {"found": False, "error": f"No pricing for SKU '{sku_n}'.",
                "known_skus": [r["sku"] for r in _rows("SELECT sku FROM pricing ORDER BY sku")]}
    r = p[0]
    margin = r["list_price"] - r["unit_cost"]
    return {"found": True, "sku": r["sku"], "unit_cost": r["unit_cost"], "list_price": r["list_price"],
            "margin_per_unit": round(margin, 2), "margin_pct_at_list": round(100 * margin / r["list_price"], 1),
            "policy": {"min_margin_pct": MIN_MARGIN_PCT, "max_discount_pct": MAX_DISCOUNT_PCT,
                       "bulk_min_qty": BULK_MIN_QTY}}


def quote_price_logic(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    p = get_pricing_logic(sku)
    if not p["found"]:
        return p
    qty, disc = int(qty), float(discount_pct)
    unit = round(p["list_price"] * (1 - disc / 100), 2)
    margin_pct = round(100 * (unit - p["unit_cost"]) / unit, 1) if unit > 0 else -100.0
    problems = []
    if disc < 0 or disc > MAX_DISCOUNT_PCT:
        problems.append(f"discount must be 0-{MAX_DISCOUNT_PCT}%")
    if disc > 0 and qty < BULK_MIN_QTY:
        problems.append(f"discounts need at least {BULK_MIN_QTY} units")
    if margin_pct < MIN_MARGIN_PCT:
        problems.append(f"margin {margin_pct}% is below the {MIN_MARGIN_PCT}% floor")
    floor_price = round(p["unit_cost"] / (1 - MIN_MARGIN_PCT / 100), 2)
    deepest = round(min(MAX_DISCOUNT_PCT, 100 * (1 - floor_price / p["list_price"])), 1)
    return {"found": True, "sku": p["sku"], "qty": qty, "discount_pct": disc, "unit_price": unit,
            "total": round(unit * qty, 2), "total_at_list": round(p["list_price"] * qty, 2),
            "unit_cost": p["unit_cost"], "total_cost": round(p["unit_cost"] * qty, 2),
            "gross_profit": round((unit - p["unit_cost"]) * qty, 2), "margin_pct": margin_pct,
            "allowed": not problems, "problems": problems,
            "deepest_allowed_discount_pct": deepest if qty >= BULK_MIN_QTY else 0.0}


def get_cash_balance_logic() -> dict:
    _ensure_board_tables()
    acct = _rows("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    pending = _rows("SELECT id, kind, ref_id, amount, payee, ticket_id FROM approvals WHERE status = 'pending' ORDER BY id")
    paid = _rows("SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS n FROM payments")[0]
    checking = next((a["balance"] for a in acct if a["name"] == "checking"), None)
    pending_total = round(sum(p["amount"] for p in pending), 2)
    return {"today": _today(), "accounts": acct, "checking_balance": checking,
            "pending_approvals": pending, "pending_total": pending_total,
            "checking_after_all_pending": None if checking is None else round(checking - pending_total, 2),
            "payments_made_total": paid["total"], "payments_made_count": paid["n"],
            "rule": "Cash only goes out. A payment that would make the balance negative is refused."}


def list_open_invoices_logic(vendor_id: int | None = None) -> dict:
    today = _today()
    sql = ("SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.status, i.description "
           "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'")
    params: tuple = ()
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"; params = (int(vendor_id),)
    rows = _rows(sql + " ORDER BY i.due_date", params)
    for r in rows:
        r["days_past_due"] = max(_days_between(r["due_date"], today), 0)
        r["overdue"] = _days_between(r["due_date"], today) > 0
    return {"today": today, "count": len(rows), "total": round(sum(r["amount"] for r in rows), 2), "invoices": rows}


# ---------- writes (agents) ----------
def add_ticket_note_logic(ticket_id: int, author: str, note: str) -> dict:
    author = _agent_ok(author)
    conn = _write()
    try:
        t = conn.execute("SELECT notes FROM tickets WHERE id = ?", (int(ticket_id),)).fetchone()
        if t is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        notes = ((t["notes"] or "") + "\n" + _note_line(author, note)).strip()
        conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, int(ticket_id)))
        conn.commit()
        return {"ok": True, "ticket_id": int(ticket_id), "notes": notes}
    finally:
        conn.close()


def update_ticket_status_logic(ticket_id: int, status: str, author: str, reason: str) -> dict:
    author = _agent_ok(author)
    status = status.strip().lower()
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": f"Status must be one of {TICKET_STATUSES}."}
    if status in ("resolved", "rejected") and author != "boss":
        return {"ok": False, "error": "Only the boss can close a ticket (resolved/rejected)."}
    _ensure_board_tables()
    pend = _rows("SELECT id FROM approvals WHERE ticket_id = ? AND status = 'pending'", (int(ticket_id),))
    if status == "resolved" and pend:
        return {"ok": False, "error": f"Ticket {ticket_id} still has pending approvals {[p['id'] for p in pend]}; "
                                      "it can't be resolved until a human decides them. Use 'waiting_approval'."}
    conn = _write()
    try:
        t = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (int(ticket_id),)).fetchone()
        if t is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        notes = ((t["notes"] or "") + "\n" + _note_line(author, f"Status {t['status']} -> {status}: {reason}")).strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, int(ticket_id)))
        conn.commit()
        return {"ok": True, "ticket_id": int(ticket_id), "old_status": t["status"], "new_status": status}
    finally:
        conn.close()


def fulfill_from_stock_logic(ticket_id: int, sku: str, size: str, qty: int, author: str) -> dict:
    author = _agent_ok(author)
    sku_n, size_n, qty = sku.strip().upper(), size.strip().upper(), int(qty)
    if qty <= 0:
        return {"ok": False, "error": "qty must be positive."}
    conn = _write()
    try:
        row = conn.execute("SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku_n, size_n)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No inventory row for {sku_n} {size_n}."}
        if row["qty"] < qty:
            return {"ok": False, "error": f"Only {row['qty']} of {sku_n} {size_n} on hand; can't take {qty}. "
                                          "Stock never goes negative."}
        conn.execute("UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku_n, size_n))
        t = conn.execute("SELECT notes FROM tickets WHERE id = ?", (int(ticket_id),)).fetchone()
        if t is not None:
            notes = ((t["notes"] or "") + "\n" + _note_line(author, f"Pulled {qty} x {sku_n} {size_n} from stock.")).strip()
            conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, int(ticket_id)))
        conn.commit()
        return {"ok": True, "sku": sku_n, "size": size_n, "taken": qty, "qty_left": row["qty"] - qty}
    finally:
        conn.close()


def _add_draft(ticket_id: int | None, kind: str, author: str, status: str, payload: dict) -> int:
    _ensure_board_tables()
    conn = _write()
    try:
        cur = conn.execute("INSERT INTO board_drafts (ticket_id, kind, author, status, payload, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (ticket_id, kind, author, status, json.dumps(payload), _today()))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def create_purchase_order_logic(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, author: str) -> dict:
    author = _agent_ok(author)
    sku_n, size_n, qty = sku.strip().upper(), size.strip().upper(), int(qty)
    v = _rows("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (int(vendor_id),))
    if not v:
        return {"ok": False, "error": f"No vendor with id {vendor_id}."}
    if not _rows("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku_n, size_n)):
        return {"ok": False, "error": f"{sku_n} {size_n} is not a stocked item."}
    price = _rows("SELECT unit_cost FROM pricing WHERE sku = ?", (sku_n,))
    if not price or qty <= 0:
        return {"ok": False, "error": "Need a priced SKU and a positive qty."}
    v = v[0]
    open_inv = _rows("SELECT id, amount FROM invoices WHERE vendor_id = ? AND status = 'open'", (v["id"],))
    today = _today()
    eta = (date.fromisoformat(today) + timedelta(days=v["lead_days"])).isoformat()
    cost = round(price[0]["unit_cost"] * qty, 2)
    status = "blocked_vendor_hold" if open_inv else "draft"
    payload = {"vendor_id": v["id"], "vendor": v["name"], "sku": sku_n, "size": size_n, "qty": qty,
               "unit_cost": price[0]["unit_cost"], "total_cost": cost, "lead_days": v["lead_days"],
               "eta_if_approved_today": eta,
               "blocked_by_invoices": [i["id"] for i in open_inv]}
    draft_id = _add_draft(int(ticket_id), "purchase_order", author, status, payload)
    return {"ok": True, "draft_id": draft_id, "status": status, **payload,
            "next_step": ("Vendor won't ship until invoices " + str(payload["blocked_by_invoices"]) +
                          " are paid. Ask accounting to request approval for those first.") if open_inv else
                         "Ask accounting to request_payment(kind='purchase_order', ref_id=draft_id) for human approval.",
            "note": "Draft only. Nothing is sent to the vendor."}


def draft_customer_message_logic(ticket_id: int, to: str, subject: str, body: str, author: str) -> dict:
    author = _agent_ok(author)
    if not _rows("SELECT 1 FROM tickets WHERE id = ?", (int(ticket_id),)):
        return {"ok": False, "error": f"No ticket with id {ticket_id}."}
    payload = {"to": to.strip()[:120], "subject": subject.strip()[:160], "body": body.strip()[:3000]}
    draft_id = _add_draft(int(ticket_id), "customer_message", author, "draft", payload)
    return {"ok": True, "draft_id": draft_id, "status": "draft", **payload,
            "note": "Saved on the board as a draft. Nothing was emailed."}


def record_price_decision_logic(ticket_id: int, sku: str, qty: int, discount_pct: float, author: str,
                                rationale: str) -> dict:
    author = _agent_ok(author)
    if author != "boss":
        return {"ok": False, "error": "Only the boss makes the final call on price overrides."}
    q = quote_price_logic(sku, qty, discount_pct)
    if not q.get("found"):
        return {"ok": False, "error": q.get("error")}
    if not q["allowed"]:
        return {"ok": False, "error": "Quote breaks shop pricing policy: " + "; ".join(q["problems"]),
                "deepest_allowed_discount_pct": q["deepest_allowed_discount_pct"]}
    draft_id = _add_draft(int(ticket_id), "price_quote", author, "final", {**q, "rationale": rationale[:600]})
    add_ticket_note_logic(ticket_id, author,
                          f"Price decision: {q['qty']} x {q['sku']} at ${q['unit_price']:.2f} "
                          f"({q['discount_pct']}% off, total ${q['total']:.2f}, margin {q['margin_pct']}%).")
    return {"ok": True, "draft_id": draft_id, **q}


def request_payment_logic(kind: str, ref_id: int, ticket_id: int, reason: str, author: str) -> dict:
    """Puts a payment in the HUMAN approval queue. Amount and payee always come from the database."""
    author = _agent_ok(author)
    kind = kind.strip().lower()
    _ensure_board_tables()
    if kind == "invoice":
        r = _rows("SELECT i.amount, i.status, v.name AS payee FROM invoices i JOIN vendors v ON v.id=i.vendor_id "
                  "WHERE i.id = ?", (int(ref_id),))
        if not r:
            return {"ok": False, "error": f"No invoice {ref_id}."}
        if r[0]["status"] != "open":
            return {"ok": False, "error": f"Invoice {ref_id} is already {r[0]['status']}."}
        amount, payee = r[0]["amount"], r[0]["payee"]
    elif kind == "rent":
        r = _rows("SELECT monthly_rent, landlord FROM leases WHERE id = ?", (int(ref_id),))
        if not r:
            return {"ok": False, "error": f"No lease {ref_id}."}
        amount, payee = r[0]["monthly_rent"], r[0]["landlord"]
    elif kind == "purchase_order":
        r = _rows("SELECT payload, status FROM board_drafts WHERE id = ? AND kind = 'purchase_order'", (int(ref_id),))
        if not r:
            return {"ok": False, "error": f"No purchase-order draft {ref_id}."}
        po = json.loads(r[0]["payload"])
        amount, payee = po["total_cost"], po["vendor"]
    else:
        return {"ok": False, "error": "kind must be 'invoice', 'rent' or 'purchase_order'."}
    dup = _rows("SELECT id FROM approvals WHERE kind = ? AND ref_id = ? AND status = 'pending'", (kind, int(ref_id)))
    if dup:
        return {"ok": False, "error": f"Already waiting for approval (approval {dup[0]['id']}).", "approval_id": dup[0]["id"]}
    cash = get_cash_balance_logic()
    conn = _write()
    try:
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, amount, payee, ticket_id, reason, requested_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (kind, int(ref_id), amount, payee, int(ticket_id), reason[:600], author, _today()))
        if kind == "purchase_order":
            # Re-check the vendor hold live: blocked only while that vendor still has an open invoice.
            blocked = conn.execute("SELECT 1 FROM invoices WHERE vendor_id = ? AND status = 'open'",
                                   (po["vendor_id"],)).fetchone()
            conn.execute("UPDATE board_drafts SET status = ? WHERE id = ?",
                         ("blocked_vendor_hold" if blocked else "pending_approval", int(ref_id)))
        conn.commit()
        aid = int(cur.lastrowid)
    finally:
        conn.close()
    after = None if cash["checking_balance"] is None else round(cash["checking_after_all_pending"] - amount, 2)
    return {"ok": True, "approval_id": aid, "status": "pending", "kind": kind, "ref_id": int(ref_id),
            "amount": amount, "payee": payee,
            "checking_balance": cash["checking_balance"],
            "checking_if_all_pending_approved": after,
            "warning": "If every pending approval is approved, checking would go negative; a human must choose."
                       if after is not None and after < 0 else None,
            "note": "Nothing is paid until a human approves it on the dashboard."}


# ---------- HUMAN ONLY ----------
def decide_approval_logic(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """The ONLY money-moving path. Called by the human dashboard, never given to an agent."""
    approver = (approver or "").strip()
    if not approver or approver.lower() in AGENTS:
        return {"ok": False, "error": "A named human approver is required (agents can't approve)."}
    decision = decision.strip().lower()
    if decision not in ("approve", "reject"):
        return {"ok": False, "error": "decision must be 'approve' or 'reject'."}
    _ensure_board_tables()
    conn = _write()
    try:
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (int(approval_id),)).fetchone()
        if a is None:
            return {"ok": False, "error": f"No approval {approval_id}."}
        if a["status"] != "pending":
            return {"ok": False, "error": f"Approval {approval_id} is already {a['status']}."}
        today = _today()
        if decision == "reject":
            conn.execute("UPDATE approvals SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
                         (approver, today, note[:300], int(approval_id)))
            conn.commit()
            return {"ok": True, "approval_id": int(approval_id), "status": "rejected", "paid": False}
        if a["kind"] == "purchase_order":
            po = json.loads(conn.execute("SELECT payload FROM board_drafts WHERE id = ?", (a["ref_id"],)).fetchone()[0])
            still_open = conn.execute("SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'",
                                      (po["vendor_id"],)).fetchall()
            if still_open:
                return {"ok": False, "error": f"{po['vendor']} still has open invoices {[r[0] for r in still_open]}; "
                                              "pay those before approving this purchase order."}
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
        if acct is None:
            return {"ok": False, "error": "No checking account."}
        if acct["balance"] < a["amount"]:
            return {"ok": False, "refused": True,
                    "error": f"Not enough cash: checking ${acct['balance']:.2f} < ${a['amount']:.2f}. "
                             "No negative balances. Payment refused."}
        conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = 'checking'",
                     (a["amount"], today))
        cur = conn.execute("INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                           "VALUES (?, ?, ?, 'checking', ?, ?)", (a["kind"], a["ref_id"], a["amount"], today, approver))
        pay_id = int(cur.lastrowid)
        if a["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
        elif a["kind"] == "rent":
            nd = conn.execute("SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],)).fetchone()[0]
            y, m, d = (int(x) for x in nd.split("-"))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            conn.execute("UPDATE leases SET next_due = ?, notes = ? WHERE id = ?",
                         (f"{y:04d}-{m:02d}-{d:02d}", f"Rent for {nd} paid {today} (approved by {approver}).", a["ref_id"]))
        elif a["kind"] == "purchase_order":
            conn.execute("UPDATE board_drafts SET status = 'approved' WHERE id = ?", (a["ref_id"],))
        conn.execute("UPDATE approvals SET status='approved', decided_by=?, decided_at=?, decision_note=?, payment_id=? "
                     "WHERE id = ?", (approver, today, note[:300], pay_id, int(approval_id)))
        new_bal = conn.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
        conn.commit()
        return {"ok": True, "approval_id": int(approval_id), "status": "approved", "paid": True,
                "payment_id": pay_id, "amount": a["amount"], "payee": a["payee"], "checking_balance": new_bal}
    finally:
        conn.close()


def list_approvals_logic(status: str = "pending") -> dict:
    _ensure_board_tables()
    rows = _rows("SELECT * FROM approvals WHERE (? = 'all' OR status = ?) ORDER BY id", (status, status))
    return {"count": len(rows), "approvals": rows}


# ---------- MCP registration ----------
@mcp.tool
def get_today() -> dict:
    """The shop's 'today' (desk.date_today) and desk notes. Use this date for anything due or overdue. Reads: desk."""
    return get_today_logic()


@mcp.tool
def list_open_tickets() -> dict:
    """All tickets that aren't resolved or rejected, oldest first. Reads: tickets, desk."""
    return list_open_tickets_logic()


@mcp.tool
def list_tickets(status: str = "all") -> dict:
    """Every ticket (or one status) with state 'open'/'resolved', pending approval count and draft count.
    Used by the dashboard board. Reads: tickets, approvals, board_drafts."""
    return list_tickets_logic(status)


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with every field (sku/size/qty, lease_id, invoice_id, status, notes) plus its board drafts
    and approval requests. Reads: tickets, board_drafts, approvals, desk."""
    return get_ticket_logic(ticket_id)


@mcp.tool
def list_vendors(specialty: str | None = None) -> dict:
    """Vendors with specialty and lead_days, plus open invoices and whether each will ship right now
    (no shipping while an invoice is open). Optional specialty filter, e.g. 'apparel'. Reads: vendors, invoices."""
    return list_vendors_logic(specialty)


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Unit cost, list price, margin per unit and margin % for one SKU, plus the shop's discount policy
    (min 40% margin, max 25% off, discounts only for 10+ units). Reads: pricing."""
    return get_pricing_logic(sku)


@mcp.tool
def quote_price(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    """Price a quantity at a discount: unit price, total, cost, gross profit, margin %, whether shop policy
    allows it, and the deepest discount allowed. Changes nothing. Reads: pricing."""
    return quote_price_logic(sku, qty, discount_pct)


@mcp.tool
def get_cash_balance() -> dict:
    """Checking balance, pending approval requests and what checking would be if all were approved,
    and payments made so far. Reads: cash_accounts, approvals, payments."""
    return get_cash_balance_logic()


@mcp.tool
def list_open_invoices(vendor_id: int | None = None) -> dict:
    """Open (unpaid) invoices with vendor name, amount, due date and days past due (from desk.date_today).
    Optional vendor filter. Reads: invoices, vendors, desk."""
    return list_open_invoices_logic(vendor_id)


@mcp.tool
def add_ticket_note(ticket_id: int, author: str, note: str) -> dict:
    """Append a dated note to a ticket (author = your agent name). Writes: tickets.notes."""
    return add_ticket_note_logic(ticket_id, author, note)


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, author: str, reason: str) -> dict:
    """Change a ticket's status: open, in_progress, waiting_approval, waiting_customer, resolved, rejected.
    Only 'boss' may resolve or reject, and a ticket with pending approvals can't be resolved. Writes: tickets."""
    return update_ticket_status_logic(ticket_id, status, author, reason)


@mcp.tool
def fulfill_from_stock(ticket_id: int, sku: str, size: str, qty: int, author: str) -> dict:
    """Take units off the shelf for a ticket. Refuses if there isn't enough (stock never goes negative).
    Writes: inventory.qty, tickets.notes."""
    return fulfill_from_stock_logic(ticket_id, sku, size, qty, author)


@mcp.tool
def create_purchase_order(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, author: str) -> dict:
    """Draft a restock purchase order on the board (never sent). Cost from pricing.unit_cost, ETA from
    vendors.lead_days. Marked 'blocked_vendor_hold' if that vendor has an open invoice.
    Reads: vendors, pricing, inventory, invoices. Writes: board_drafts."""
    return create_purchase_order_logic(ticket_id, vendor_id, sku, size, qty, author)


@mcp.tool
def draft_customer_message(ticket_id: int, to: str, subject: str, body: str, author: str) -> dict:
    """Save a message for a customer as a DRAFT on the board. Nothing is emailed. Writes: board_drafts."""
    return draft_customer_message_logic(ticket_id, to, subject, body, author)


@mcp.tool
def record_price_decision(ticket_id: int, sku: str, qty: int, discount_pct: float, author: str, rationale: str) -> dict:
    """BOSS ONLY: record the final price for a price-override ticket. Refused if it breaks shop pricing policy.
    Reads: pricing. Writes: board_drafts (price_quote), tickets.notes."""
    return record_price_decision_logic(ticket_id, sku, qty, discount_pct, author, rationale)


@mcp.tool
def request_payment(kind: str, ref_id: int, ticket_id: int, reason: str, author: str) -> dict:
    """Ask a HUMAN to approve a payment. kind = 'invoice' (ref_id = invoices.id), 'rent' (leases.id) or
    'purchase_order' (board_drafts.id). Amount and payee come from the database. Nothing is paid here.
    Reads: invoices, vendors, leases, board_drafts, cash_accounts. Writes: approvals."""
    return request_payment_logic(kind, ref_id, ticket_id, reason, author)


@mcp.tool
def list_approvals(status: str = "pending") -> dict:
    """Approval requests by status ('pending', 'approved', 'rejected' or 'all'). Reads: approvals."""
    return list_approvals_logic(status)


@mcp.tool
def decide_approval(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY (dashboard). Never given to agents. 'approve' pays from checking (refused if the balance
    would go negative), inserts into payments with approved_by, and marks the invoice paid, moves the lease's
    next_due a month ahead, or approves the PO. 'reject' just closes the request.
    Writes: cash_accounts, payments, invoices, leases, board_drafts, approvals."""
    return decide_approval_logic(approval_id, decision, approver, note)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Campus Customs operations MCP server")
    ap.add_argument("--http", action="store_true", help="serve over HTTP at http://127.0.0.1:8001/mcp")
    args = ap.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()
