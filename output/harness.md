# Campus Customs Multi-Agent Operations: Harness

*Class project set at Campus Customs. Not affiliated with the shop.*

---

# Part A: System overview

Three pieces talk to each other. All shop facts and actions go through **one MCP server**. **Humans approve every payment.**

```
React desk (frontend/, Vite :5173)  ──HTTP──▶  FastAPI (backend/main.py :8000)
                                                  │  ├─ mcp_client.py ─┐
                                                  │  └─ team.py: Boss · Inventory · Accounting · Facilities · Customer Service
                                                  │        (PydanticAI agents, gpt-6-luna via Portkey, MCPToolset) ─┐
                                                  ▼                                                                   ▼
                                       MCP server (mcp_server/server.py, FastMCP, stdio)  ──▶  data/campus_customs_new.db
                                       output/audit_trail.json ◀── every agent-loop step (append-only)
```

## 1. Tables (`data/campus_customs_new.db`, working copy; `campus_customs.db` stays untouched)

| Table | Holds | Used by |
|---|---|---|
| `desk` | `date_today` = the shop's "today" (2026-08-31) | every due/overdue calculation |
| `tickets` | the board: type, requester, sku/size/qty, lease_id, invoice_id, status, notes | Boss routing and closing tickets |
| `inventory` | qty per SKU **and size**, location | Inventory (shortfalls, pulling stock) |
| `pricing` | unit_cost, list_price | Accounting (margins, discount quotes, PO cost) |
| `vendors` | specialty, **lead_days** | Inventory (who restocks, ETA) |
| `invoices` | vendor bills, due_date, status | Accounting. Any open invoice ⇒ that vendor won't ship |
| `leases` | rent amount, next_due | Facilities |
| `cash_accounts` | checking balance | Accounting. Only `decide_approval` changes it |
| `payments` | every payment, with `approved_by` (a human) | proof of human approval |
| **`approvals`** *(added)* | payment requests: kind, ref, amount, payee, requested_by, status, decided_by | the human approval queue |
| **`board_drafts`** *(added)* | purchase orders, customer messages, price quotes (JSON) | "drafts stay on the board": nothing is sent |

## 2. MCP tools (21, in `mcp_server/server.py`)

| Group | Tools (tables) |
|---|---|
| **Read** | `get_today` (desk) · `list_tickets` / `list_open_tickets` / `get_ticket` (tickets, board_drafts, approvals) · `check_stock` (inventory) · `list_vendors` (vendors, invoices) · `get_invoice_status` / `list_open_invoices` (invoices, vendors, payments) · `get_lease_due` (leases, cash_accounts, payments) · `get_pricing` / `quote_price` (pricing) · `get_cash_balance` (cash_accounts, approvals, payments) · `list_approvals` (approvals) |
| **Write, agents** | `add_ticket_note`, `update_ticket_status` (tickets; only Boss resolves; no resolving with pending approvals) · `fulfill_from_stock` (inventory; never negative) · `create_purchase_order` (→ board_drafts; blocked while the vendor has an open invoice) · `draft_customer_message` (→ board_drafts) · `record_price_decision` (→ board_drafts; Boss only; ≥10 units, ≤25% off, ≥40% margin) · `request_payment` (→ approvals; amount and payee from the DB) |
| **Human only** | `decide_approval` (→ cash_accounts, payments, invoices, leases, board_drafts, approvals): pays only if checking covers it; refuses agent names as approver |

## 3. The five agents (`backend/prompts/<agent>.md`, `backend/team.py`)

| Agent | Job | Its MCP tools (besides common¹) |
|---|---|---|
| **Boss** | Reads each ticket, routes work, makes final calls (price, priorities, status) | check_stock, get_invoice_status, get_lease_due, get_pricing, quote_price, get_cash_balance, list_approvals, update_ticket_status, **record_price_decision** |
| **Inventory** | Stock by SKU and size, shortfalls, vendor and lead time, draft POs | check_stock, list_vendors, get_invoice_status, get_pricing, **create_purchase_order**, fulfill_from_stock, update_ticket_status |
| **Accounting** | Cash, invoices, margins, **payment requests for human approval** | get_cash_balance, list_open_invoices, get_invoice_status, get_lease_due, get_pricing, quote_price, **request_payment**, list_approvals, list_vendors, update_ticket_status |
| **Facilities** | Lease, landlord, rent | get_lease_due, get_cash_balance, list_approvals, update_ticket_status |
| **Customer Service** | Customer drafts (never sent) | check_stock, get_pricing, quote_price, **draft_customer_message**, update_ticket_status |

¹ common = get_today, get_ticket, list_open_tickets, add_ticket_note. **Full connectivity:** every agent has `delegate(to, task)` to any other agent.

Types are in `backend/models.py`: `AgentReport`, `TicketOutcome`, `AuditEntry`, `AuditToolCall`.

## 4. API routes (`backend/main.py`)

`GET /api/health` · `GET /api/tickets` · `GET /api/tickets/{id}` · `GET /api/tickets/{id}/summary` · `POST /api/tickets/{id}/run` · `GET /api/runs` · `GET /api/events?since=` · `GET /api/approvals` · `POST /api/approvals/{id}/approve` (**the only route that moves money**) · `POST /api/approvals/{id}/reject` · `GET /api/cash` · `POST /api/reset`. One line each in the Problem 7 section below.

## 5. Dashboard (`frontend/`)

**"The Back Office on Broadway"** (details in `output/design.md`):

- **Ticket spike:** tickets as paper stubs, with the action button *Start team / Run again / Close out* and a red RESOLVED stamp.
- **Five color-coded agent seats** with live lamps.
- **Live transcript:** speech bubbles, routing slips for each delegation, a receipt for each tool call, and red receipts for refusals.
- **"Who did what":** the Boss's decision plus a card per agent.
- **Cork board:** the drafts pinned up.
- **Cash register:** a rolling odometer, plus **paper checks you sign** to approve.
- **Polling:** every 1.5 s while running and every 4 s when idle.
- Run with `npm run dev`. It calls `http://localhost:8000`.

## 6. Safety rules (summary; full list in Problem 5 below)

- **Money:**
  - Agents only *request*. `decide_approval` is human-only: hidden from every agent, blocked again in the tool guard, and agent names are refused as approver.
  - No negative balances.
  - Amount and payee always come from the database.
  - A PO can't be paid while its vendor has an open invoice.
- **Customers and vendors:** nothing is sent. Messages and POs are drafts. Prompts forbid sharing internal debts, cash or margins.
- **Integrity:**
  - Least-privilege tool filters per role.
  - The real agent name is stamped as `author`, so no agent can impersonate the Boss.
  - Read tools are read-only. Stock can't go negative. A ticket can't be resolved with pending approvals.
  - Pricing policy is enforced in code.
- **Cost:**
  - **One model only (gpt-6-luna).**
  - Per ticket run: ≤30 model requests, ≤50 tool calls, ≤200k tokens.
  - Delegation depth ≤2 and ≤6 delegations, with the usage budget shared across the whole team.
  - Compact tool results, and one run at a time.
- **Audit:** every agent-loop step is appended to `output/audit_trail.json` and never wiped.

## 7. Specs and how to run

| | |
|---|---|
| Model | `gpt-6-luna` only, via Portkey, **Responses API** (`OpenAIResponsesModel`) |
| Per-ticket budget | 30 requests · 50 tool calls · 200,000 tokens · depth 2 · 6 delegations · 2 output retries |
| Backend | `cd backend && uvicorn main:app --reload --port 8000` |
| Frontend | `cd frontend && npm install && npm run dev` (http://localhost:5173) |
| CLI | `python run_tickets.py --ticket 101` / `--all --reset` · `python approve.py --list` |
| Reset | dashboard **⟲ Reset day**, `POST /api/reset`, or `cp data/campus_customs.db data/campus_customs_new.db` |

## 8. Results of the clean run (Problem 9)

| Ticket | Final | Agents | Cash |
|---|---|---|---|
| 101 tee | resolved (3 runs) | Boss, Inventory, Accounting, Customer Service | −$840 (invoice 501) −$8 (PO) |
| 102 rent | resolved (2 runs) | Boss, Facilities, Accounting | −$2,400 |
| 103 bulk hoodies | resolved (1 run) | Boss, Inventory, Accounting, Customer Service | $0 (25% quote, $870) |

Checking: **$3,400.00 → $152.00**, which matches `cash_accounts`. The full run took 75 model calls and about 253k tokens across 6 sessions.

Details are in `desk_tickets.html` (Actual and Cash tabs), `resolved_tickets.json`, and `resolved_board.html`.

---

# Part B: Details by problem

## Problem 2: The database

**Files** (in `hw5/data/`, never committed):

| File | Role |
|---|---|
| `campus_customs.db` | **Original. Never modified.** Copy it again to reset. |
| `campus_customs_new.db` | **Working copy.** The MCP server and backend read and write this one. |

Both started byte-identical (same SHA-256). The shop's "today" is **`desk.date_today` = 2026-08-31**.

**Reset:** `cp data/campus_customs.db data/campus_customs_new.db`

### Tables, fields, and why they matter to the agents

| Table (rows) | Fields | Why it matters |
|---|---|---|
| **`desk`** (1) | `date_today`, `notes` | The shop's clock. **Every** "is it overdue / how many days until due" decision uses `date_today` (2026-08-31), not the real date. Boss reads it first. |
| **`tickets`** (3) | `id`, `type` (customer_order / rent_notice / price_override), `requester`, `subject`, `sku`, `size`, `qty`, `lease_id` → leases, `invoice_id` → invoices, `status` (open), `notes`, `created_at` | **The work board.** Boss reads each ticket and routes it by `type`. The linked fields (`sku`/`size`/`qty`, `lease_id`, `invoice_id`) tell each agent where to look. `status` and `notes` record the outcome. |
| **`inventory`** (10) | `sku`, `name`, `size`, `qty`, `location`. Primary key (`sku`, `size`). | **Inventory agent's** main table. Stock per SKU **and size**, used to spot shortfalls (for example tee S = 0, mug = 0). |
| **`pricing`** (4) | `sku`, `unit_cost`, `list_price` | **Accounting's** margin math (list − cost) and the cost of purchase orders. Sets the floor for any discount. |
| **`vendors`** (3) | `id`, `name`, `specialty`, `lead_days` | **Inventory** picks the right vendor by `specialty` (apparel → Bulldog Print Co). **`lead_days`** gives restock dates (rule: lead times come from this table). |
| **`invoices`** (1) | `id`, `vendor_id` → vendors, `amount`, `due_date`, `status` (open), `description` | **Accounting**: bills the shop owes. **Rule: a vendor won't ship while it has an open unpaid invoice.** So Inventory must check here before any reorder. |
| **`leases`** (1) | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | **Facilities**: rent amount and due date for the Chapel Street shop |
| **`cash_accounts`** (1) | `name` (checking), `balance`, `date` | **Accounting**: the only money available. **Rule: the pay tool must refuse if it would go negative.** Cash only goes out. |
| **`payments`** (0) | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | **Accounting** writes here **only after a human approves** (rule). `approved_by` is the proof, and `ref_id` points to the invoice or lease paid. Empty at the start. |

### Current state (2026-08-31)

| Stock | S | M | L | XL | OS |
|---|---|---|---|---|---|
| CC-TEE-WHITE Classic Bulldog Tee | **0** | 5 | 3 | 2 | |
| CC-HOOD-NAVY Basic Hoodie Big Yale | 4 | **8** | 14 | 6 | |
| CC-HAT-BLUE Yale Cap | | | | | 40 |
| CC-MUG-CREST Crest Mug | | | | | **0** |

| Pricing | Unit cost | List | Margin |
|---|---|---|---|
| Tee | $8.00 | $28.00 | $20.00 (71%) |
| Hoodie | $22.00 | $58.00 | $36.00 (62%) |
| Cap | $6.00 | $22.00 | $16.00 |
| Mug | $3.50 | $14.00 | $10.50 |

Vendors: **Bulldog Print Co** (apparel reprint, 5-day lead), Elm City Gifts (mugs and small goods, 3 days), QuickShip CT (local courier, 1 day).
Cash: **checking $3,400.00**.

### The three open tickets and how they link

**Ticket 101: `customer_order` from Tauhid Zaman, "Bulldog tee", CC-TEE-WHITE size S × 1, `invoice_id` 501**

- `inventory`: tee **S has 0**, so the order can't be filled from stock.
- The restock vendor is **Bulldog Print Co** (apparel, `lead_days` 5).
- `invoice_id 501`: Bulldog Print Co, **$840.00, due 2026-08-28, still open**, so it's **3 days overdue**. By the shop rule, **Bulldog won't ship anything until 501 is paid.**
- **Chain:** Inventory finds the shortfall → Accounting pays invoice 501 (**needs human approval**; cash 3,400 → 2,560) → Inventory/Accounting prepares a reprint PO (tee S, $8/unit) → earliest arrival **2026-09-05** (today + 5 days) → Customer Service drafts a message to Tauhid with that date.

**Ticket 102: `rent_notice` from Elm City Properties, "Rent due", `lease_id` 1**

- `leases`: Chapel Street shop, **$2,400.00 due 2026-09-02**, so **2 days** away, not overdue yet.
- **Chain:** Facilities confirms the lease and amount → Accounting prepares the rent payment for **human approval** → pays it from checking.

**Ticket 103: `price_override` from Yale AI Club, "Bulk hoodie discount", CC-HOOD-NAVY size M × 20**

- `inventory`: hoodie **M has 8**, so the **shortfall is 12**.
- `pricing`: $22 cost / $58 list → $36 margin per unit. 20 at list = $1,160, cost $440.
- The restock vendor is also **Bulldog Print Co**, also **blocked by invoice 501**.
- **Chain:** Inventory finds the shortfall and vendor → Accounting checks how deep a discount can go and still keep a healthy margin → **Boss makes the final call** on the discount → Customer Service drafts the reply.

### Cross-ticket constraints (why this needs a team, not one script)

- **Cash is tight.** $3,400 − invoice 501 ($840) − rent ($2,400) = **$160 left**. Restocking 12 hoodies costs 12 × $22 = **$264**, which doesn't fit after both bills (plus the tee reprint). The team must **prioritize**: rent (lease obligation, due in 2 days) and invoice 501 (overdue, and it unblocks every apparel restock) come first. The hoodie restock waits or gets scaled down, and the pay tool **must refuse** anything that would go negative.
- **One vendor blocks two tickets.** Invoice 501 gates both 101 (tee) and 103 (hoodies). Paying it once unblocks both. That's a good reason for Inventory to delegate to Accounting.
- **No purchase-orders table.** The database has no PO table, so restock orders and customer messages will be **drafts kept on the board** (ticket notes or a drafts store added later). Nothing is sent to real vendors or customers (rule).
- **Human-in-the-loop:** both payments ($840 and $2,400) need an approver, recorded in `payments.approved_by`. Agents can prepare them but never pay on their own.

---

## Problem 3: MCP server (`mcp_server/server.py`, FastMCP)

**Database:** `data/campus_customs_new.db` (the working copy). All three tools are **read-only** (`mode=ro`), use `desk.date_today` as "today", and return `"found": false` plus the valid options instead of guessing.

| Tool | Tables it reads | Ticket it unlocks | Why it's the right tool for that ticket |
|---|---|---|---|
| **`check_stock(sku, size, qty_needed)`** | `inventory` (+ `desk` for the date) | **103**: Yale AI Club wants **20** CC-HOOD-NAVY in **M** at a discount (also used for 101's tee S) | Ticket 103 can't be priced or promised until we know how many of the 20 come from the shelf. `check_stock("CC-HOOD-NAVY","M",20)` returns **8 on hand, shortfall 12**, so the Boss knows a 12-unit restock is needed before agreeing to any bulk deal. For 101 it confirms tee S = **0**, so the order can't ship from stock. |
| **`get_invoice_status(invoice_id)`** | `invoices` + `vendors` (+ `payments`, `desk`) | **101**: Tauhid's tee is linked to `invoice_id` **501** | Ticket 101's tee must be reprinted by **Bulldog Print Co**, and invoice 501 ($840, due 08-28) decides whether they'll ship. The tool returns **3 days past due, `vendor_will_ship: false`**, and the vendor's **5-day lead time**, which is exactly what tells the agents to get 501 approved and paid first, and that the earliest restock is 09-05. (It also explains why 103's hoodie restock is blocked: same vendor.) |
| **`get_lease_due(lease_id)`** | `leases` + `cash_accounts` (+ `payments`, `desk`) | **102**: Elm City Properties' rent notice for `lease_id` **1** | Ticket 102 is a "rent due" email, and Facilities and Accounting need the real amount, the date, and whether cash can cover it before asking a human to approve. The tool returns **$2,400.00 due 2026-09-02 (2 days, not overdue)**, checking **$3,400**, and **`can_cover_from_checking: true`, balance after rent $1,000**. That's the facts for the approval request, without paying anything. |

**Tested against `campus_customs_new.db`:**

- `check_stock("CC-TEE-WHITE","S",1)` → on hand 0, shortfall 1.
- `check_stock("CC-HOOD-NAVY","m",20)` → on hand 8, shortfall 12 (lowercase size accepted).
- Unknown SKUs or sizes → `found: false` + the real SKU and size lists.
- `get_invoice_status(501)` → overdue 3 days, `vendor_will_ship: false`. Invoice 999 → not found.
- `get_lease_due(1)` → 2 days until due, can cover, $1,000 after.

**Convention for later write tools:** `payments.kind` will be `'invoice'` (with `ref_id` = invoice id) or `'rent'` (with `ref_id` = lease id). The tools above already read those rows, so once something is paid they'll show it under `payments_recorded`.

---

## Problem 4: Connecting the MCP server to the vibe coder

- **Connection file:** `.mcp.json` at the `hw5` root, in Claude Code's project format:

  ```json
  { "mcpServers": { "campus-customs-ops": { "type": "stdio",
      "command": ".venv/bin/python", "args": ["mcp_server/server.py"] } } }
  ```

  Claude Code starts the server over **stdio** from the project folder, using the project's virtual environment (where `fastmcp` is installed). `/mcp` showed **campus-customs-ops ✔ connected, 3 tools**. A second server from the parent `AI Class/.mcp.json` (`yale-som-courses`) was **not enabled**, to keep this project's agent limited to shop tools.
- **Smoke test:** in Claude Code, each tool was called once through MCP. The evidence is in `output/mcp_smoke.json` (prompt, tool, raw tool output).

| Prompt | Tool | Key output | Matches `campus_customs_new.db` |
|---|---|---|---|
| check CC-HOOD-NAVY size M for 20 units (ticket 103) | `check_stock` | `qty_on_hand 8`, `shortfall 12`, Aisle A | `inventory` row (CC-HOOD-NAVY, M) qty 8 ✅ |
| get_invoice_status for invoice 501 (ticket 101) | `get_invoice_status` | $840, due 2026-08-28, `days_past_due 3`, `vendor_will_ship false`, lead_days 5 | `invoices` 501 + `vendors` 1 ✅ |
| get_lease_due for lease 1 (ticket 102) | `get_lease_due` | $2,400 due 2026-09-02, `days_until_due 2`, checking $3,400, $1,000 after | `leases` 1 + `cash_accounts` checking ✅ |

Each output was checked field by field against the database with a read-only script. All three match, and all use the shop date 2026-08-31 (`desk.date_today`), not the computer's date.

---

## Problem 5: The agent team and the grown MCP server

### Layout

```
backend/
  config.py        # model (gpt-6-luna only, via Portkey), paths, budgets
  models.py        # AgentReport, TicketOutcome, AuditEntry, AuditToolCall
  team.py          # the 5 agents, MCP toolset + per-role filters, delegate(), agent loop
  audit.py         # append-only output/audit_trail.json writer
  run_tickets.py   # CLI: --ticket 101 | --all [--reset]
  approve.py       # human approval desk (CLI) -> MCP decide_approval
  prompts/boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
mcp_server/server.py   # the ONLY way agents touch campus_customs_new.db
```

**How it connects:** `team.py` starts **one** MCP server process (`MCPServerStdio` → `mcp_server/server.py`) and gives each agent a **filtered** view of it. There's no second shop-tools layer: every stock, price, cash, invoice, lease, ticket and draft fact comes from an MCP tool. The model is fixed in code as `MODEL_NAME = "gpt-6-luna"`, called through Portkey with `PORTKEY_API_KEY`, and is the only model name anywhere in the project. Agents call it through the **OpenAI Responses API** (`OpenAIResponsesModel`, `/v1/responses`), because Portkey/Azure rejects function tools with reasoning on `/v1/chat/completions` for this model. `CC_OPENAI_API=chat` is a fallback that uses chat completions with reasoning off.

### The agents

| Agent | Role | MCP tools it can use | Output type |
|---|---|---|---|
| **Boss** | Reads each ticket, routes work, makes final calls (price decisions, ticket status, priorities when cash is tight) | common¹ + check_stock, get_invoice_status, get_lease_due, get_pricing, quote_price, get_cash_balance, list_approvals, update_ticket_status, **record_price_decision** | `TicketOutcome` |
| **Inventory** | Stock by SKU and size, shortfalls, which vendor restocks, lead times, draft POs, pulls stock for confirmed orders | common + check_stock, list_vendors, get_invoice_status, get_pricing, **create_purchase_order**, **fulfill_from_stock**, update_ticket_status | `AgentReport` |
| **Accounting** | Cash, invoices, margins and discount options, **payment requests for human approval** | common + get_cash_balance, list_open_invoices, get_invoice_status, get_lease_due, get_pricing, quote_price, **request_payment**, list_approvals, list_vendors, update_ticket_status | `AgentReport` |
| **Facilities** | The shop space: lease, landlord, rent amount and due date. Hands payment to accounting. | common + get_lease_due, get_cash_balance, list_approvals, update_ticket_status | `AgentReport` |
| **Customer Service** | Drafts customer messages (never sent) | common + check_stock, get_pricing, quote_price, **draft_customer_message**, update_ticket_status | `AgentReport` |

¹ common = `get_today`, `get_ticket`, `list_open_tickets`, `add_ticket_note`

**Full connectivity:** every agent has a `delegate(to, task)` tool and can ask **any** other agent (not itself). The sub-agent runs its own loop and returns its report. Typical flows:

- **101:** Boss → Inventory (tee S = 0, vendor on hold) → Accounting (request invoice 501) → Customer Service (delay message)
- **102:** Boss → Facilities (lease facts) → Accounting (request rent)
- **103:** Boss → Inventory + Accounting (stock and discount options) → Boss decides → Customer Service (quote)

**Agent loop:** `run_agent()` steps through each agent with `agent.iter(...)`. Each model response, plus the tool results that come back, is one step and is appended to the audit trail. The Boss's run for a ticket contains every delegated run.

### Every MCP tool and the tables it uses

| Tool | Tables | Who can call it |
|---|---|---|
| `get_today` | desk | all |
| `list_open_tickets` | tickets | all |
| `get_ticket` | tickets, board_drafts, approvals | all |
| `add_ticket_note` | tickets (notes) | all |
| `check_stock` | inventory | boss, inventory, customer_service |
| `list_vendors` | vendors, invoices | inventory, accounting |
| `get_invoice_status` | invoices, vendors, payments | boss, inventory, accounting |
| `list_open_invoices` | invoices, vendors | accounting |
| `get_lease_due` | leases, cash_accounts, payments | boss, accounting, facilities |
| `get_pricing` | pricing | boss, inventory, accounting, customer_service |
| `quote_price` | pricing | boss, accounting, customer_service |
| `get_cash_balance` | cash_accounts, approvals, payments | boss, accounting, facilities |
| `list_approvals` | approvals | boss, accounting, facilities |
| `update_ticket_status` | tickets | all (only boss can resolve or reject) |
| `fulfill_from_stock` | inventory, tickets | inventory |
| `create_purchase_order` | vendors, pricing, inventory, invoices → **board_drafts** | inventory |
| `draft_customer_message` | tickets → **board_drafts** | customer_service |
| `record_price_decision` | pricing → **board_drafts**, tickets | boss |
| `request_payment` | invoices, vendors, leases, board_drafts, cash_accounts → **approvals** | accounting |
| `decide_approval` | approvals → **cash_accounts, payments, invoices, leases, board_drafts** | **human only** (dashboard / `approve.py`) |

New tables (working copy only): **`approvals`** (id, kind, ref_id, amount, payee, ticket_id, reason, requested_by, status, decided_by/at, payment_id) and **`board_drafts`** (id, ticket_id, kind, author, status, payload JSON, created_at).

### Audit trail (`output/audit_trail.json`)

Append-only. Each step is written with read → append → atomic replace, under a lock, and an unreadable file is set aside rather than overwritten. One **`AuditEntry` per agent-loop step**:

- `session_id` (the whole ticket run), `ticket_id`, `agent`, `depth`, `delegated_by`, `run_id`, `step`
- `timestamp`, `model` (always gpt-6-luna), `task`
- `thoughts`
- `tool_calls[]`: name, short args, one-line result, ok/refused
- `retries[]`
- On the last step: `output` preview, `stop_reason` (`completed` / `stopped: budget` / `error`), and ticket-wide `usage` (requests, tool calls, tokens)

These answer "who did what, with which data, and why it stopped".

### Safety: guardrails for real customers and real money

**Money**

- **Agents can't pay.** Payments only enter an `approvals` queue (`request_payment`). The one money-moving tool, `decide_approval`, is **human-only**: it's not in any agent's tool list, it's blocked again in `_guard_tool_call`, and it refuses agent names as approver. Each payment records `approved_by`.
- **No negative balances.** `decide_approval` refuses any payment larger than the checking balance. `request_payment` warns when all pending approvals together would overdraw the account.
- **The amount and payee come from the database**, never from the model, so an agent can't inflate a payment or send it to the wrong party.
- **Vendor holds are enforced:** a purchase order can't be approved while that vendor has an open invoice.
- **Prices:** discounts are allowed only for 10+ units, at most 25% off, with at least 40% margin (enforced in `quote_price` and `record_price_decision`). Only the Boss sets prices.

**Customers and outside parties**

- **Nothing is sent.** Customer messages and purchase orders are `board_drafts` for a human to review. There's no email or vendor-call tool at all.
- Prompts forbid sharing internal matters (debts, cash, margins, other customers) with customers.

**Integrity**

- **Least privilege:** each agent sees only its role's MCP tools (filtered toolset), and calls outside the role are refused.
- **No impersonation:** `_guard_tool_call` stamps the **real** agent name as `author`, so only the actual Boss can resolve tickets or set prices.
- **Facts only:** read tools are read-only (`mode=ro`), every answer is from the database, and "not found" is explicit. Stock can't go negative, and tickets can't be resolved while approvals are pending.
- **Reset-safe:** agents only change `campus_customs_new.db`. The original stays untouched.
- **Audit everything:** every step is appended to `audit_trail.json`, which is never wiped.

**Token and cost limits** (`config.py`, shared across the whole team for one ticket via `usage=ctx.usage`)

| Limit | Value |
|---|---|
| Model requests per ticket (all agents together) | **30** |
| Tool calls per ticket | **50** |
| Tokens per ticket | **200,000** |
| Delegation depth | **2** (boss → specialist → specialist) |
| Delegations per ticket | **6** |
| Output retries per agent | 2 |
| One model only | `gpt-6-luna` |

Other cost controls:

- Tickets run one at a time, with no chat history carried between tickets.
- Tool results are compact JSON.
- Prompts tell agents to delegate one clear task per teammate and to do simple lookups themselves.

---

## Problem 6: Ticket plans (`output/desk_tickets.html`)

A double-click page with tabs **101 / 102 / 103 / Cash / Reflection**. Each ticket tab has an **Expected** section (filled) and an **Actual** section (empty until the run). Expected routing is deliberately narrow:

| Ticket | Boss calls first | Expected chain | Not involved |
|---|---|---|---|
| 101 tee S | **Inventory** (is it on the shelf?) | Boss→Inventory→Accounting (approve invoice 501) · Boss→Customer Service (delay draft) | Facilities |
| 102 rent | **Facilities** (owns the lease) | Boss→Facilities→Accounting (approve rent) | Inventory, Customer Service |
| 103 bulk hoodies | **Inventory** (can we supply 20?) | Boss→Inventory (8 on hand, 12 short, PO blocked) · Boss→Accounting (discount options + cash) · Boss decides · Boss→Customer Service (quote draft) | Facilities. No PO payment (cash $160 after 101+102), no stock pulled before the customer accepts |

---

## Problem 7: Backend routes (`backend/main.py`, FastAPI)

Run from `backend/` with `uvicorn main:app --reload --port 8000`. Shop data goes through the **MCP server** (`backend/mcp_client.py`, a FastMCP client). Agents run through `team.py`.

- `GET /api/health`: backend up, the model (gpt-6-luna), and the shop date.
- `GET /api/tickets`: every ticket with its status and state (open / resolved), pending approvals, drafts, and run progress (MCP `list_tickets`).
- `GET /api/tickets/{id}`: one ticket with its notes, board drafts (POs, customer messages, price quotes) and approvals (MCP `get_ticket`).
- `POST /api/tickets/{id}/run`: starts the agent team (Boss first) on that ticket in the background. Returns 202, or 409 if a run is already going.
- `GET /api/runs`: which ticket runs are going, finished or failed, with the Boss's outcome.
- `GET /api/events?since=N&ticket_id=&limit=`: recent agent steps from `audit_trail.json` (agent, depth, who delegated, what it said, tools used and their results). Use `next_since` for refresh.
- `GET /api/approvals?status=`: payment and purchase-order requests the agents prepared (MCP `list_approvals`).
- `POST /api/approvals/{id}/approve` `{approver, note}`: **the only route that moves money.** A human approves and MCP `decide_approval` pays from checking, refuses negative balances, writes `payments.approved_by`, and marks the invoice paid, moves the lease due date, or approves the PO.
- `POST /api/approvals/{id}/reject` `{approver, note}`: a human rejects, and nothing is paid.
- `GET /api/cash`: the current checking balance from `cash_accounts`, pending approvals, and payments made (MCP `get_cash_balance`).
- `POST /api/reset`: copies `campus_customs.db` over `campus_customs_new.db` for a fresh run. Refused while a run is going. The audit trail is not wiped.

**Design notes:**

- **One run at a time** (a lock). All tickets share one checking account, so each run must see the approvals the earlier ones queued.
- Runs happen in the background, so the dashboard stays responsive and watches progress through `/api/events`.
- MCP calls from the backend are serialized, so SQLite never has two writers at once.
- CORS allows the local Vite dev server.

---

## Problem 8: Dashboard (`frontend/`, React + Vite + TypeScript)

- **Talks to:** `http://localhost:8000` (`VITE_API_URL` can override). The backend's CORS allows any `localhost` port, including Vite's `5173`.
- **New route:** `GET /api/tickets/{id}/summary`: per-agent summary of a ticket's latest run (steps, tools used, who asked it, its own summary, Boss decision and next steps), built from the audit trail.
- **Resolve flow:**
  1. **Start team:** agents prepare everything. Payments go into the queue, and the ticket waits.
  2. A human signs the checks on the desk (`/approve`).
  3. **Close out:** the Boss reruns, sees the payments recorded, finishes what's left (for example the restock PO once invoice 501 is paid), and marks the ticket **resolved**.

  A price override is resolved once the price is decided and the reply is drafted. Boss prompt updated accordingly.
- **Polling:** every 1.5 s while a run is going, every 4 s when idle. `/api/events?since=` only fetches new audit entries.
- The audit now keeps up to 4,000 characters of each agent's final output, so summaries aren't cut off.
- Design details are in `output/design.md`.
