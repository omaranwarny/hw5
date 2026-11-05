# Campus Customs Multi-Agent Operations (HW5)

An agent team runs the back office of **Campus Customs**, a Yale apparel shop. Open tickets (a customer order, a rent notice, a bulk-discount request) are worked by five **PydanticAI** agents (Boss, Inventory, Accounting, Facilities, Customer Service) that can delegate to each other. They reach the shop's data **only through an MCP server** (FastMCP) over SQLite. A **FastAPI** backend runs the team, and a **React** dashboard lets a human watch the agents and **approve every payment**.

> Class project set at Campus Customs / Yale Bulldog Blue. Not affiliated with the shop. Every agent uses **only `gpt-6-luna`** through Portkey.

```
frontend/ (React + Vite :5173) ──HTTP──▶ backend/main.py (FastAPI :8000) ──▶ team.py (5 agents)
                                                   │                                │
                                                   └────────── MCP (stdio) ──────────┴──▶ mcp_server/server.py ──▶ data/campus_customs_new.db
```

## What's in the repo

| Path | What it is |
|---|---|
| `data/campus_customs.db` | **Original** shop database. Never modified. |
| `data/campus_customs_new.db` | **Working copy** the MCP server and agents read and write. It's committed in its post-run state (all 3 tickets resolved, checking $152.00). |
| `mcp_server/server.py` | FastMCP server: 21 tools over the working DB (see `mcp_server/README.md`) |
| `.mcp.json` | Connects the MCP server to Claude Code (project-scoped) |
| `backend/main.py` | FastAPI routes for the dashboard |
| `backend/team.py`, `agent prompts in backend/prompts/` | The five agents, delegation, per-ticket budget, and audit logging |
| `backend/models.py` | Pydantic types (agent reports, ticket outcome, audit entries) |
| `frontend/` | React + Vite + TypeScript dashboard ("The Back Office on Broadway") |
| `output/` | harness, MCP smoke test, ticket plans with Actual/Cash/Reflection, design notes, resolved tickets, board screenshots, audit trail, repo URL |

## 1. One-time setup

You need **Python 3.11+**, **Node 20+**, and a **Portkey API key** with access to `gpt-6-luna`.

```bash
cd hw5
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then put your key in .env:
#   PORTKEY_API_KEY=your-key

cd frontend && npm install && cd ..
```

## 2. Get a clean database (copy the original over the working copy)

Do this **before every full three-ticket run**:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Other ways to do the same thing:

- the dashboard's **⟲ Reset day** button
- `curl -X POST http://localhost:8000/api/reset`
- `cd backend && python run_tickets.py --all --reset`

The reset restores checking to **$3,400.00** and all three tickets to `open`. The audit trail is never wiped.

## 3. Start the MCP server

You don't need to start it by hand for the app. The backend launches `mcp_server/server.py` over **stdio** on its own (one process for the agents, one for the dashboard routes). To run or inspect it directly:

```bash
cd mcp_server
python server.py            # stdio (what the backend and Claude Code use)
python server.py --http     # or HTTP at http://127.0.0.1:8001/mcp
```

**From Claude Code:** open `hw5/`, approve the `campus-customs-ops` server from `.mcp.json`, and run `/mcp` to see 21 tools.

## 4. Start the FastAPI backend

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

Check http://localhost:8000/api/health. It should show `"model": "gpt-6-luna"` and `"shop_date": "2026-08-31"`. The full route list is at http://localhost:8000/docs.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000`, and CORS allows the Vite origin.

## 6. A full three-ticket run (what produced the files in `output/`)

1. **Reset** the database (step 2). The register should read **$3,400.00**.
2. **▶ Start team** on **#101**, then on **#102**. The agents prepare an **$840** invoice payment and **$2,400** rent; nothing is paid yet.
3. Type your name under **Signing as**, then **✍️ Sign & pay** the $840 invoice first and the $2,400 rent second. Checking drops to **$160.00**.
4. **✔ Close out #102**, and it's resolved.
5. **✔ Close out #101.** The team queues the **$8** tee reprint PO. Sign it, then close out #101 again, and it's resolved. Checking is **$152.00**.
6. **▶ Start team** on **#103.** The Boss sets the bulk price and Customer Service drafts the reply, so it's resolved with no money moved.

Expected final state: all three resolved and checking **$152.00** ($3,400 − $840 − $2,400 − $8). Details are in `output/desk_tickets.html` (Expected / Actual / Cash / Reflection tabs) and `output/resolved_tickets.json`.

There's also a terminal-only path: `cd backend && python run_tickets.py --ticket 101`, and `python approve.py --list` / `--approve <id> --by "Your Name"`.

## Safety, in one paragraph

Agents can only **request** payments. The single money-moving tool (`decide_approval`) is human-only: no agent can see it, and it refuses any payment that would make checking negative. Each payment records `approved_by`. Vendors with unpaid invoices can't be paid for new orders, and discounts must keep a 40% margin. Customer messages and purchase orders stay as **drafts**; nothing is emailed. Each agent sees only its role's MCP tools, and each ticket run is capped at 30 model calls, 50 tool calls and 200k tokens. Everything is in `output/harness.md`.
