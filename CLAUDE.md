# PM Strategy Copilot — Project Context

## Purpose
An AI-powered system that helps a Technical Program Manager (TPM) decide what matters and why. Addresses tactical overload and strategic gap. Every output follows: **What → Why → Action**.

## Stack
- **UI:** Streamlit (Python), 5 tabs: Chat, Today, Insights, Requests, Settings
- **LLM:** OpenAI `gpt-4o-mini` via `OPENAI_API_KEY` env var
- **Storage:** Local JSON files in `agent-claude/data/` (no cloud sync, no DB)
- **Entry point:** `agent-claude/app.py` — run via `./run_app.sh`

## Key Directories
```
agent-claude/       # Application code
  agents/           # All agent implementations
  models/           # Pydantic data models
  storage/          # StorageManager (atomic JSON writes)
  data/             # Runtime JSON: requests, day_plans, insights, conversation
  config.py         # Paths, API key, MODEL constant
agent-prd/          # Product docs: PM_Agent_PRD_v6.md (primary spec)
docs/               # Design guidelines, DECISIONS.md (decision log)
```

## Architecture Constraints (enforce strictly)
- **One agent per output type:** Only Analyst → StrategicInsights. Only Planner → FocusItems. No overlap.
- **One surface per record type:** Insights tab = StrategicInsights. Today tab = DayPlans. Requests tab = CustomerRequests.
- **One intake pathway per data type:** Chat = conversational intake. Requests tab = structured/bulk.
- **Planner never reads raw files** — only structured data from storage.
- **Analyst never reads raw files** — only structured CustomerRequests and StrategicInsights.

## Implemented Agents
| Agent | File | Role |
|-------|------|------|
| Orchestrator | `agents/orchestrator.py` | Routes intent to correct agent |
| Intake | `agents/intake_agent.py` | Parses raw files, extracts meetings/requests |
| Planner | `agents/planner_agent.py` | Produces ranked FocusItems for Today tab |
| Analyst | `agents/analyst_agent.py` | Detects trends, gaps, risks → StrategicInsights |
| Challenger | `agents/challenger_agent.py` | Red-teams decisions |
| Writer | `agents/writer_agent.py` | Drafts emails, briefs, messages |
| Researcher | `agents/researcher_agent.py` | Deep dives, background context |

## Data Models (Pydantic v2)
- `CustomerRequest` — `models/customer_request.py` (priority, status, edit_history, surface_count)
- `DayPlan` / `FocusItem` — `models/day_plan.py`
- `StrategicInsight` — `models/strategic_insight.py`
- `WorkroomSession` / `CustomAgent` — `models/workroom.py`

## Current State (as of 2026-02-27)
- **Tier 1:** All 5 core features done. Morning workflow, planner, analyst, request intake, insight storage are functional.
- **Tier 2+:** Pattern synthesis, stakeholder reporting, weekly reflection — not yet started.
- **Workroom:** Multi-agent session feature implemented (facilitator, topic classifier, 3-step wizard, custom agents).
- **Full breakdown:** See `docs/STATUS.md`

## Session Protocol (follow every session)
1. Read `docs/STATUS.md` to understand current feature state before any discussion
2. Discuss requirements with user; clarify before designing
3. Enter **plan mode** for any non-trivial change
4. Append entry to `docs/DECISIONS.md` with **Status: Pending** before executing
5. Execute approved plan
6. Update `docs/DECISIONS.md` → **Status: Executed**; update `docs/STATUS.md` checkboxes
7. If architecture or agent inventory changed → update this file's "Current State" section

## Documentation Files
| File | Purpose | When to update |
|------|---------|----------------|
| `CLAUDE.md` (this file) | Persistent session context, auto-loaded | After architecture changes |
| `docs/STATUS.md` | Living feature tracker by PRD tier | After every execution |
| `docs/DECISIONS.md` | Append-only decision log | Before (Pending) + after (Executed) every change |

## Primary Spec
Full requirements: `agent-prd/PM_Agent_PRD_v6.md`
Design system: `docs/UI_UX_DESIGN_GUIDELINE.md`
