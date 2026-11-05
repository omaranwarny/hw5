# Dashboard Design: "The Back Office on Broadway"

**The idea:** the dashboard should feel like the real back room of a campus shop: tickets stuck on an order spike, the team sitting at a wooden desk, receipts piling up as they work, notes pinned to a cork board, and a cash register with a checkbook that only a human can sign. People should *want* to sit here and watch the team work, and it should be impossible to miss what needs a human.

## Layout: three zones, read left to right like the work itself

| Zone | What's there | Why |
|---|---|---|
| **Left: the order spike** | Each ticket is a paper **stub** with a punched hole, #number, type icon (🧾 order, 🏠 rent, 🏷️ price), the requester, linked SKU/lease/invoice, a status tag, "✍️ 2 to sign" / "📝 3 drafts" chips, and one big button: **▶ Start team → ↻ Run again → ✔ Close out** | Work comes in on the left. You see all three tickets at once and what each needs. The button changes to say exactly what happens next. |
| **Center: the desk** | **Five agent seats** on a wood-grain desk, then the **live transcript**, then **Who did what** and the **cork board** | This is the show: who's talking, what they looked up, and what they produced |
| **Right: the register** | A **cash register** (green odometer balance) and a **checkbook** of payment requests waiting for a signature, plus a ledger | Money is always visible and always separate. The human's job lives in one place. |

## How each agent reads differently

- Every agent has a **seat with its own color, icon and nameplate**:

  | Agent | Icon | Color |
  |---|---|---|
  | Boss | 🎩 | navy |
  | Inventory | 📦 | warm amber |
  | Accounting | 🧮 | ledger green |
  | Facilities | 🔑 | plum |
  | Customer Service | 💬 | rose |

  The same color carries through their seat, avatar, speech bubbles, tool receipts, and summary card, so you can scan the transcript by color alone.
- **Seat lamps** show who's involved: grey = *off this ticket*, pulsing gold = *working*, green = *done*, red = *stopped*. The agent **talking right now lifts out of its chair** with a colored glow and a bobbing avatar.
  - This makes the plan-vs-actual comparison visual: on ticket 102 only three seats light up (Boss, Facilities, Accounting), and the other two stay grey.
- **Hand-offs are routing slips:** a yellow "📞 Facilities → Accounting" slip shows the exact task one agent gave another. You can see the full-connectivity chain, not just "the Boss called everyone".
- **Tool calls are receipts:** small monospace slips that say, in plain words, what happened ("🧾 counted stock" · `check_stock` · sku=CC-HOOD-NAVY · size=M), followed by the real result. **Guardrail refusals print as red ⛔ receipts**, so a blocked action is obvious.
- Each run ends with a sign-off line, "✓ Accounting filed the report", and the Boss's sign-off shows the team's total model calls and tokens.

## How resolved tickets show up

- When the Boss resolves a ticket, a **red rubber "RESOLVED" stamp** slams onto its stub (a short scale-and-rotate animation) and appears large on the stage. The stub fades slightly, like finished paperwork.
- Status tags use a small, consistent palette: amber **Waiting on approval**, rose **Waiting on customer**, green **Resolved**.
- **Who did what** (after a run) leads with the **Boss's call** in a blue quote card, plus "👉" next steps for the human. Under it is **one card per agent** that worked: its own summary, who asked it, and tags for every tool it used ("ran a quote ×3"). It also shows the run's total model calls, tool calls, and tokens.
- The **cork board** pins what the team produced: 📦 purchase orders (vendor, item, cost, ETA, and a red "blocked vendor hold" tag when that applies), 🏷️ the price quote (with the list price crossed out and the margin), and ✉️ customer letters stamped **"Draft · not sent"**.

## How cash shows up

- **The till:** a dark register face with a glowing green **mechanical odometer**. When a payment is approved, **each digit rolls** to the new balance and a red **"−$2,400.00"** floats up and fades, so you *feel* the money leave. Under it: "If all pending are approved: $160.00" (turns red if negative) and "Paid out so far".
- **Approvals are paper checks** (green security pattern, check number, date, "Pay to the order of …", amount box, memo with the ticket and the agent that prepared it). You type your name once in **"Signing as"**; it appears as a **handwritten signature** (Caveat font) on every check line. **"✍️ Sign & pay"** is the only thing on the whole page that moves money. "Void" rejects.
- **Guardrails are visible before you click:** a check that's bigger than the balance turns pink with "Not enough in checking. The bank will refuse this." If you click anyway, the backend refuses it and a red toast explains why.
- A small **ledger** lists the last decisions (✓ paid −$840.00 · by Omar, ✕ voided).

## Small touches that make it pleasant

- **Top bar:** navy, with a gold-and-white **letterman stripe**, pills for the shop date (2026-08-31, not today's real date), the model (gpt-6-luna), and a status that pulses gold while the team is working ("● Team working") or shows "Backend offline" if FastAPI is down.
- Text has a typed-out feel: a bouncing three-dot "typing" indicator in the speaking agent's color, and new transcript lines rise in.
- **Live but calm:** it polls every 1.5 s while a run is going and every 4 s when idle, and the transcript auto-scrolls only while live.
- **One run at a time:** while the team is working, every Start button is disabled, with a tooltip saying why (tickets share one bank account).
- **Reset day** (top right) restores the original database after a confirmation. The audit trail is kept.
- Accessible: real buttons, keyboard-focusable ticket stubs, `aria-live` transcript, good contrast, and **all motion turns off for `prefers-reduced-motion`**. On narrow screens the register drops below the desk.

## Why these choices

- **Physical metaphors** (spike, desk, receipts, cork board, checks, stamp) map directly to what's happening: tickets are paperwork, tools leave receipts, drafts get pinned up, money needs a signature. People understand them instantly, with no legend needed.
- **Color per agent plus lamps** make multi-agent work readable at a glance, and make it easy to compare the plan in `desk_tickets.html` with what actually ran.
- **Separating money into its own zone with a signature step** matches the shop rule (humans approve every payment) and makes the one consequential action deliberate, not a stray click.
