# Campus Customs Operations MCP Server

**What it's for:** the single door between the shop's business systems and the AI agent team. Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) reads and changes shop data **only** through these tools. The agents never open SQLite themselves. Every answer comes from the database: nothing is invented, and missing records come back as `"found": false` / `"ok": false` with the reason.

**Database:** `../data/campus_customs_new.db`, the **working copy** (override with `CC_DB_PATH`). The original `data/campus_customs.db` is never touched. Reset by copying it over the working copy. "Today" is always `desk.date_today` (2026-08-31).

The server adds two tables to the **working copy only** (created on first use):

- **`approvals`:** the human-approval queue for payments.
- **`board_drafts`:** purchase orders, customer messages and price quotes. They stay on the board and are never sent.

## Tools (20)

**Read**

| Tool | Tables | Purpose |
|---|---|---|
| `get_today()` | desk | The shop's date |
| `list_open_tickets()` | tickets | Tickets not yet resolved or rejected |
| `get_ticket(ticket_id)` | tickets, board_drafts, approvals | One ticket, plus its drafts and approvals |
| `check_stock(sku, size, qty_needed)` | inventory | On hand, shortfall, location, other sizes |
| `list_vendors(specialty?)` | vendors, invoices | Specialty, lead_days, open invoices, `will_ship` |
| `get_invoice_status(invoice_id)` | invoices, vendors, payments | Due date, days past due, `vendor_will_ship` |
| `list_open_invoices(vendor_id?)` | invoices, vendors | Unpaid invoices with days past due |
| `get_lease_due(lease_id)` | leases, cash_accounts, payments | Rent, due date, days until due, whether cash covers it |
| `get_pricing(sku)` | pricing | Cost, list price, margin, discount policy |
| `quote_price(sku, qty, discount_pct)` | pricing | Discount math and whether policy allows it |
| `get_cash_balance()` | cash_accounts, approvals, payments | Checking balance, pending approvals, balance if all are approved |
| `list_approvals(status)` | approvals | The approval queue |

**Write (agents)**

| Tool | Tables written | Guardrail |
|---|---|---|
| `add_ticket_note(ticket_id, author, note)` | tickets.notes | Dated, signed note |
| `update_ticket_status(ticket_id, status, author, reason)` | tickets | Only `boss` may resolve or reject. Can't resolve while approvals are pending. |
| `fulfill_from_stock(ticket_id, sku, size, qty, author)` | inventory, tickets.notes | Refuses if stock would go negative |
| `create_purchase_order(ticket_id, vendor_id, sku, size, qty, author)` | board_drafts | Draft only. Cost from pricing, ETA from lead_days. Blocked while the vendor has an open invoice. |
| `draft_customer_message(ticket_id, to, subject, body, author)` | board_drafts | Draft only, never emailed |
| `record_price_decision(ticket_id, sku, qty, discount_pct, author, rationale)` | board_drafts, tickets.notes | Boss only. Refuses anything outside policy (10+ units, ≤25% off, ≥40% margin). |
| `request_payment(kind, ref_id, ticket_id, reason, author)` | approvals | Queues a payment for a human. Amount and payee come from the database. No duplicates. |

**Human only (dashboard; never given to an agent)**

| Tool | Tables written | Guardrail |
|---|---|---|
| `decide_approval(approval_id, decision, approver, note)` | cash_accounts, payments, invoices, leases, board_drafts, approvals | Needs a named human (agent names are refused). **Refuses if checking would go negative.** A purchase order is refused while its vendor still has an open invoice. Paying records `payments.approved_by` and marks the invoice paid or moves the lease's `next_due` forward one month. |

## Run

```bash
pip install -r ../requirements.txt
python server.py           # stdio (Claude Code via ../.mcp.json, and the agent backend)
python server.py --http    # http://127.0.0.1:8001/mcp
```
