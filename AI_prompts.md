# AI Prompts Log — HW5: Campus Customs Multi-Agent Operations

## Problem 1: Vibe coder prompts

**Prompt:**
starting hw5. make a hw5 folder and an AI_prompts.md in it. log what I ask you for every problem, one section each with the problem number and title, my prompt in my own words, and a follow-up if I needed one. keep it updated as we go

**Follow-up:**
for each follow-up also add one line saying what was missing after the first try

*What was lacking:* the first version had no place to explain why a follow-up was needed, which the assignment asks for.

## Problem 2: Study the Campus Customs database

**Prompt:**
open data/campus_customs.db and go through every table and field. make a copy called campus_customs_new.db that we'll actually change later, and leave the original alone. look at the 3 open tickets and figure out how they connect to the other tables. then start output/harness.md with each table, its fields, and a quick line on why it matters for the agents

**Follow-up:**
also check if the tickets fight over anything, like cash or the same vendor, and write that down

*What was lacking:* the first pass described each ticket on its own, but missed that paying both bills leaves almost no cash and that one unpaid invoice blocks two of the tickets.

## Problem 3: Build the MCP server

**Prompt:**
build an MCP server with FastMCP in mcp_server/ that reads data/campus_customs_new.db. no need to run it yet. give it 3 tools we'll definitely need for the tickets, with clear names, and it can only return what's actually in the database, never made-up stuff. add a short mcp_server/README.md and a harness section listing each tool, the table it reads, which ticket it unlocks, and why it's the right tool for that ticket

**Follow-up:**
make the invoice tool also say whether the vendor will actually ship, using the "no shipping while they have an unpaid invoice" rule, and use the shop's date from the desk table, not today's real date

*What was lacking:* the first version only showed the invoice amount and due date, so the agents would have had to work out the shipping block and the days overdue themselves.

## Problem 4: Connect the MCP server and test each tool

**Prompt:**
hook the MCP server up to my vibe coder so it can call the tools. save the connection config as .mcp.json in the hw5 root. then test all 3 tools through the vibe coder and save the proof in output/mcp_smoke.json: the prompt I asked, the tool name, and what the tool returned, which has to match the database

**Follow-up (in Claude Code):**
store each output as a raw string instead

*What was lacking:* the first save turned each tool output into a nested JSON object, and I wanted the exact unedited text the tool sent back.

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**
now build the agent team with pydantic ai: boss, inventory, accounting, facilities and customer service. each one gets its own prompt file in backend/prompts with the shop rules it needs, types go in backend/models.py, and the agents live in backend/. any agent should be able to hand work to any other one. only gpt-6-luna through portkey for all of them. add whatever MCP tools they need to actually work the 3 tickets, but all the shop data still has to go through the MCP server, no shortcuts. every agent step should append to output/audit_trail.json without wiping it. update the harness with the agents, every tool and the table it uses, plus a safety section with guardrails and token limits, and update the mcp_server README

**Follow-up:**
make sure no agent can actually pay anything or pretend to be the boss. paying should be a human-only step, it has to refuse if cash would go negative, and it should update the invoice or lease when it pays

*What was lacking:* the first version let the accounting agent pay directly and trusted whatever author name the agent typed, which breaks the human-approval rule and lets an agent close tickets as the boss.

**Follow-up:**
running ticket 102 crashed with "MCPServerStdio was removed in Pydantic AI V2, use MCPToolset". fix it for the version I have installed

*What was lacking:* the agents were wired with an MCP class from an older PydanticAI version, so the team couldn't start on my machine even though the MCP server itself worked.

**Follow-up:**
now it says "Function tools with reasoning_effort are not supported for gpt-6-luna in /v1/chat/completions, use /v1/responses". keep gpt-6-luna but make it work

*What was lacking:* the agents called the model through the chat completions endpoint, which Portkey doesn't allow for this model when tools are attached, so no agent could call a single MCP tool.

## Problem 6: Plan the three tickets

**Prompt:**
before we run anything for real, make output/desk_tickets.html, a page I can just double click, with a tab for each ticket (101, 102, 103) plus empty Cash and Reflection tabs for later. on each ticket tab fill in only an Expected section: who the boss should call first and why, every delegation I expect, and which MCP tools should get used. leave space for an Actual section

**Follow-up:**
don't send every specialist on every ticket. for each one say who's NOT needed and why, and remember the tickets run in order so cash from 101 and 102 affects 103

*What was lacking:* the first draft had Accounting and Customer Service on every ticket and ignored that the earlier approvals leave only $160, which changes what should happen on 103.

## Problem 7: Backend routes

**Prompt:**
make backend/main.py a FastAPI app the dashboard can call. I need routes to: list the 3 tickets and whether they're open or resolved, run the agent team on a ticket id, get recent agent events (what each agent said and which tools it used) so the board can refresh, approve a payment or purchase when a human clicks approve (that's the only thing that should actually change cash), get the checking balance, and reset the database to the original. it should start with `uvicorn main:app --reload --port 8000` from backend/. list every route in one line in the harness

**Follow-up:**
running a ticket takes like a minute, so don't make the browser wait. start it in the background and let the board poll the events. also only one run at a time since they all share the same cash

*What was lacking:* the first version ran the whole ticket inside the request, so the page would hang for a minute, and two runs at once could both spend the same cash.

## Problem 8: Agent dashboard

**Prompt:**
build the dashboard in frontend/ with react + vite + typescript, calling the routes from problem 7 at http://localhost:8000 (allow localhost:5173 on the backend). it needs to list the 3 tickets, let me pick one and start the team, show each agent and what it's saying and doing while it runs, mark the ticket resolved when it's done, show a short summary of what each agent did, let me approve a payment or purchase, and show the checking balance dropping after I approve. make it look like a real desk people would want to sit at, and write output/design.md about the look and why

**Follow-up:**
the boss leaves tickets as "waiting approval" so nothing ever shows as resolved. after I approve the payments, let me hit a close out button so the boss checks again and resolves it, and count a price override as done once the price is set and the reply is drafted

*What was lacking:* the first version had no way for a ticket to ever reach "resolved", because the money rule blocks it while a payment waits, and the Boss had no instructions for a second pass after a human approves.

## Problem 9: Resolve the tickets

**Prompt:**
reset the database, note the starting cash, and run all 3 tickets on the board until they're resolved. then fill the Actual sections in desk_tickets.html (who worked, who they handed off to, what tools they used) next to my Expected, itemize the money on the Cash tab with the ending balance matching the database, save output/resolved_tickets.json with each ticket's outcome, agent contributions and approvals, and make output/resolved_board.html with a screenshot of the board for each resolved ticket. finish the harness too

**Follow-up:**
the transcript on my screenshots shows a line from an old run at the top. fix that, and in the write-up be honest about where the agents did worse than my plan

*What was lacking:* the board was adding the same events twice on load, so an old pre-reset line showed up under ticket 101, and the first Actual write-up only listed what matched the plan.

## Problem 10: Reflection

**Prompt:**
fill the Reflection tab in desk_tickets.html. grade how the agents did on each ticket and why, compare Actual vs my Expected plan for each one, say what would've been simpler as one agent with tools, and give 3 new Campus Customs problems this team could handle with the tools we have plus 3 it couldn't, with the tools and agents we'd need. use real numbers from the ticket and cash tabs, not generic AI talk

**Follow-up:**
tie the "couldn't solve" ones back to what actually went wrong, like the hoodie quote promising a restock we can't pay for and rent coming due again on 10-02 with only $152 left

*What was lacking:* the first draft listed generic gaps (like email and forecasting) without showing how they would have changed the outcome of tickets 101 and 103 in this run.

## Problem 11: Submit to GitHub

**Prompt:**
get hw5 ready for a public github repo. match the expected file layout, write a README that explains how to copy the original db to the working copy, start the MCP server, start the FastAPI backend, start the React board, and reset before a full three-ticket run. keep my real .env out, but this time include both database files in data/. put the repo url in output/github_url.txt

**Follow-up:**
do a dry run first and show me what's getting committed, I want to see both .db files in there and no .env

*What was lacking:* the .gitignore from earlier problems still excluded data/ and *.db, so the databases graders need would have been left out of the repo.
