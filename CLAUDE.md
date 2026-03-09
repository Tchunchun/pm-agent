# PM Strategy Copilot — Project Context

## Purpose
An AI-powered system that helps a Technical Program Manager (TPM) decide what matters and why. Addresses tactical overload and strategic gap. Every output follows: **What → Why → Action**.

## Stack
- **UI:** Streamlit (Python), 5 tabs: Chat, Today, Insights, Requests, Settings
- **LLM:** Agno Agent framework (v2.5.8) wrapping Azure OpenAI / OpenAI; model via `config.get_agno_model()`
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
All agents are defined as `CustomAgent` records in `custom_agents.json` and executed via `CustomAgentRunner` → Agno `Agent`.

| Component | File | Role |
|-----------|------|------|
| Orchestrator | `agents/orchestrator.py` | Routes intent, document Q&A, smart routing, round table |
| CustomAgentRunner | `agents/custom_agent_runner.py` | Universal executor: CustomAgent def → Agno Agent |
| FacilitatorAgent | `agents/facilitator_agent.py` | Workroom session facilitation & summaries |
| TopicClassifier | `agents/topic_classifier.py` | Recommends agents for workroom topics |
| AgentDesigner | `agents/agent_designer.py` | Generates specialist agent teams from problems |
| Default Agents | `agents/default_agents.py` | Seeds 6 built-in agents (intake, planner, analyst, challenger, writer, researcher) |
| Skills/Tools | `skills/tools.py` | Agno tool functions (get_date, search_backlog, get_insights) |

## Data Models (Pydantic v2)
- `CustomerRequest` — `models/customer_request.py` (priority, status, edit_history, surface_count)
- `DayPlan` / `FocusItem` — `models/day_plan.py`
- `StrategicInsight` — `models/strategic_insight.py`
- `WorkroomSession` / `CustomAgent` — `models/workroom.py`

## Current State (as of 2026-03-01)
- **Tier 1:** All 5 core features done. Morning workflow, planner, analyst, request intake, insight storage are functional.
- **Tier 2+:** Pattern synthesis, stakeholder reporting, weekly reflection — not yet started.
- **Workroom:** Multi-agent session feature implemented (facilitator, topic classifier, 3-step wizard, custom agents).
- **Agno Migration:** Complete. All LLM calls use `agno.agent.Agent`. No raw OpenAI SDK usage in production code.
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
