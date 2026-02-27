# Feature Implementation Status

Living tracker — updated after every execution. Cross-referenced with `docs/DECISIONS.md`.

**Status legend:** ✅ Done · 🔄 In Progress · ⬜ Not Started · 🚫 Deferred

---

## Tier 1 — Core Features (Build First)

| # | Feature | Status | Notes | DECISIONS ref |
|---|---------|--------|-------|---------------|
| 1 | Morning Workflow | ✅ Done | Full pipeline: intake → confirm → planner → Today tab | — |
| 2 | Daily Planner Agent | ✅ Done | `agents/planner_agent.py` — ranked 3-5 FocusItems with What/Why/Source/Est | — |
| 3 | Analyst Agent | ✅ Done | `agents/analyst_agent.py` — 4 modes: trend, gap, risk, decision support | — |
| 4 | Request Intake & Storage | ✅ Done | Chat + Requests tab pathways; CSV/PDF/DOCX parsing; auto-classify + priority | — |
| 5 | Strategic Insight Storage + History | ✅ Done | `models/strategic_insight.py`; Insights tab with feedback loop status | — |

**Tier 1 data models:** ✅ All complete — `CustomerRequest`, `DayPlan`, `FocusItem`, `StrategicInsight`

**Tier 1 UI tabs:** ✅ All present — Today, Chat, Insights, Requests

---

## Tier 2 — Next Phase (Depends on Tier 1)

| # | Feature | Status | Notes | DECISIONS ref |
|---|---------|--------|-------|---------------|
| 1 | Pattern → Feature Synthesis | ⬜ Not Started | Needs 4-6 weeks of stored requests; no Feature model yet | — |
| 2 | Stakeholder Reporting (exec summary) | ⬜ Not Started | Needs accumulated insights; no report generation logic | — |
| 3 | Weekly Reflection Agent | ⬜ Not Started | Framework ready (DayPlan history exists); agent not coded | — |
| 4 | Power Automate briefing automation | ⬜ Not Started | Nice-to-have; removes manual Copilot step | — |

---

## Tier 3 — Deferred

| Feature | Status | Reason |
|---------|--------|--------|
| Roadmap management | 🚫 Deferred | Adds tracking overhead; not core value |
| PRD / release note generation | 🚫 Deferred | Low relevance without multi-team scope |
| Customer Health dashboard | 🚫 Deferred | Single-customer context |
| CLI interface | 🚫 Deferred | Web UI covers all needs |
| Jira / Linear sync | 🚫 Deferred | High complexity, low v1 value |
| Teams bot | 🚫 Deferred | Requires IT/admin approval |

---

## Bonus Features (Beyond PRD — Implemented)

| Feature | Status | Notes | DECISIONS ref |
|---------|--------|-------|---------------|
| Challenger Agent | ✅ Done | `agents/challenger_agent.py` — red-teams decisions; PRD §10 Tier 2 vision | — |
| Writer Agent | ✅ Done | `agents/writer_agent.py` — emails, briefs, stakeholder updates | — |
| Researcher Agent | ✅ Done | `agents/researcher_agent.py` — deep dives, industry context | — |
| Workroom Sessions | ✅ Done | Multi-agent collaborative sessions with goal-driven workflow; `models/workroom.py` | 2026-02-27 |
| Custom Agent Creation | ✅ Done | User-defined agents with custom prompts; `agents/default_agents.py` | — |
| Agent Hub Tab | ✅ Done | Browse, create, test custom agents; Settings tab | — |
| Workroom: 3-Step Wizard | ✅ Done | Guided creation with TopicClassifier → agent recommendation → FacilitatorAgent launch | 2026-02-27 |
| Smart Agent Routing | ✅ Done | LLM picks best 1-2 agents per message instead of round-tabling all; reduces noise | 2026-02-27 |
| Multi @mention Support | ✅ Done | Users can @mention multiple agents; triggers mini round table with just those agents | 2026-02-27 |
| Conversational Agent Mode | ✅ Done | Agents give concise 3-6 sentence responses in workrooms; wider history window for multi-turn follow-ups | 2026-02-27 |
| Explore Experts (Agent Hub) | ✅ Done | Problem-first agent discovery: describe challenge → LLM proposes domain experts with reasoning → review + save to library | 2026-02-27 |
| Agent Category Overhaul | ✅ Done | 4-category system (pm_workflow/ai_product/career/life) + dynamic sections; category sync migration; manual create form updated | 2026-02-27 |

---

## PRD Recommendations (§11)

| Rec | Description | Status | Notes |
|-----|-------------|--------|-------|
| R1 | Onboarding flow (first-run wizard) | ⬜ Not Started | No wizard; user must manually set up inbox + paste Copilot prompt |
| R2 | Context persistence across sessions | ✅ Done | Conversation + DayPlan state persist via StorageManager |
| R3 | Weekly reflection prompt | ⬜ Not Started | DayPlan history ready; reflection agent not built |
| R4 | Agent response labelling | ✅ Done | All responses labelled `[Planner]`, `[Analyst]`, etc. |
| R5 | Privacy boundary declaration | 🔄 Partial | Local-only storage (no cloud); no in-UI privacy statement |
| R6 | Graceful first week (low-data warning) | ⬜ Not Started | `MIN_REQUESTS_FOR_ANALYSIS` config exists; no user-facing warning |
| R7 | Challenger as early Tier 2 priority | ✅ Done | Challenger implemented and routable |

---

## Architecture Invariants (must not regress)

| Rule | Status |
|------|--------|
| One agent per output type | ✅ Enforced |
| One surface per record type | ✅ Enforced |
| One intake pathway per data type | ✅ Enforced |
| Planner never reads raw files | ✅ Enforced |
| Analyst never reads raw files | ✅ Enforced |
| Atomic JSON writes (StorageManager) | ✅ Enforced |
| What → Why → Action output format | ✅ Enforced |
