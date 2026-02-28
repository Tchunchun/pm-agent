# Decision Log

Running log of all requirements discussions and implementation decisions.
Each entry is appended after an approved plan, before execution (status: Pending), then updated after execution (status: Executed).

---

## Entry format

```markdown
## [YYYY-MM-DD] — [Topic]
**Decision:** What was agreed upon
**Rationale:** Why this approach
**Scope:** Files/components affected
**Status:** Pending | Executed | Rolled Back
```

---

## 2026-02-27 — Documentation Workflow Setup

**Decision:** Adopt a three-layer documentation system:
1. `CLAUDE.md` at project root — persistent context loaded automatically each session
2. `docs/DECISIONS.md` (this file) — append-only log updated before and after every execution
3. Plan mode — required for all non-trivial changes; approved plan is summarised here

**Rationale:** The project was missing durable session context, causing Claude to re-discover architecture constraints each session. A decision log prevents requirement drift and provides an audit trail for all changes.

**Scope:**
- Created: `/PM Agent/CLAUDE.md`
- Created: `/PM Agent/docs/DECISIONS.md`

**Status:** Executed

---

## 2026-02-27 — Create New Workroom: 3-Step Wizard Flow

**Decision:** Replace the flat "Create Workroom" form with a guided 3-step wizard:
1. **Step 1 — Goal & Context:** User provides topic, meeting objective, desired outcome, supporting documents, mode, and output type.
2. **Step 2 — Agent Recommendation:** System calls `TopicClassifier` to analyse the topic and recommend agents with per-agent rationale. User reviews, adjusts, and confirms.
3. **Step 3 — Launch:** System creates `WorkroomSession` (populating `topic_description`, `ai_recommended_agents`, `key_outcome`), then `FacilitatorAgent.open_session()` generates an opening message to kick off the meeting.

**Rationale:** The previous flat form asked users to manually pick agents without guidance, did not use the already-implemented `TopicClassifier` or `FacilitatorAgent`, and did not capture structured meeting objectives. The wizard connects all existing infrastructure: model fields (`topic_description`, `ai_recommended_agents`, `facilitator_intro_sent`), the `TopicClassifier` agent, and the `FacilitatorAgent.open_session()` method.

**Scope:**
- Modified: `agent-claude/app.py` — sidebar "New Workroom" button resets wizard state; MODE C replaced with 3-step wizard; facilitator opens session on creation.
- Unchanged: `agents/topic_classifier.py`, `agents/facilitator_agent.py`, `models/workroom.py` — all already had the required logic.

**Status:** Executed

---

## 2026-02-27 — Documentation Workflow: Feature Tracker + Session Protocol

**Decision:** Add two elements to complete the documentation workflow:
1. `docs/STATUS.md` — living feature tracker listing all PRD features (Tier 1/2/3) plus bonus features and PRD recommendations, with status (✅ Done / 🔄 In Progress / ⬜ Not Started / 🚫 Deferred) and cross-reference to DECISIONS.md entries.
2. "Session Protocol" section in `CLAUDE.md` — 7-step per-session instructions that Claude reads automatically at session start, ensuring documentation steps (Pending → Executed) happen consistently.

**Rationale:** CLAUDE.md and DECISIONS.md provided context and change history, but no at-a-glance view of feature completion. STATUS.md fills this gap. The Session Protocol embeds the workflow into CLAUDE.md so it is followed automatically without prompting.

**Scope:**
- Created: `docs/STATUS.md` — full audit-based feature tracker (Tier 1 all done; Tier 2 not started; Workroom + Agents as bonus)
- Modified: `CLAUDE.md` — added "Session Protocol" (7 steps) and "Documentation Files" reference table; updated "Current State" to point to STATUS.md

**Status:** Executed

---

## 2026-02-27 — Smart Agent Routing + Multi-Mention Support

**Decision:** Replace the default "round-table everything" behavior in workroom open mode with smart routing:
1. **Smart routing:** When a user sends a message in open mode, an LLM call picks the 1-2 best agents to respond (instead of all agents). Falls back to round table for broad questions like "what does everyone think?"
2. **Multi @mention:** `_detect_mention` replaced with `_detect_mentions` (returns a list). Mentioning multiple agents (e.g., `@analyst @challenger`) triggers a mini round table with just those agents.
3. **Round table preserved:** The 🔄 Round Table button still invokes all agents explicitly.

**Rationale:** Round-tabling every message created walls of text that defeated the purpose of multi-agent collaboration. Most questions only need 1-2 agents. Smart routing reduces noise while preserving the ability to get everyone's opinion on demand.

**Scope:**
- Modified: `agents/orchestrator.py` — `_detect_mentions()` (multi-mention), `smart_route()` (LLM-based agent selection), `_build_agent_descriptions()`, updated `handle_message()` call sites
- No model changes required

**Status:** Executed

---

## Backlog — Planned Improvements

| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| B1 | Collapsible agent responses in round table | Medium | Show one-line summary per agent, expand for full response |
| B2 | Auto-synthesis after round table | Medium | Facilitator auto-summarizes after every round table exchange |
| B3 | Agent role taxonomy (specialist vs task-taker) | Low | Classify agents as advisory (specialist) or action (task-taker); task-takers observe but don't participate in round tables |

---

## 2026-02-27 — Conversational Mode + Multi-Turn Follow-Up

**Decision:** Add conversational mode to all agents when operating inside a workroom:
1. **Concise responses:** All agents receive a conversational style instruction in workrooms — 3-6 sentences, lead with key insight, no headers/bullets unless asked. Max tokens reduced from 1500 to 600.
2. **Multi-turn context:** Conversation history window increased from 8→12 messages in workroom mode. Agents are explicitly instructed to acknowledge user answers to their questions and incorporate new information.
3. **Analyst conversational handler:** New `_handle_analyst_conversational()` method gives the analyst agent full conversation history and LLM-based responses in workrooms (previously it only ran data-based intent routing).
4. **No quality sacrifice:** Agent system prompts (expertise, persona) are unchanged. Only the response style is adjusted — like an advisor speaking in a meeting vs. writing a report.

**Rationale:** Individual agent responses were too long for interactive discussion. Users answering agent follow-up questions weren't properly tracked as context. Round table verbosity was already addressed by smart routing; this addresses per-agent verbosity.

**Scope:**
- Modified: `agents/orchestrator.py` — `CONVERSATIONAL_MODE` constant, `_route_by_key()` accepts workroom param + passes `concise` flag, new `_handle_analyst_conversational()`
- Modified: `agents/challenger_agent.py` — `challenge()` accepts `concise` param
- Modified: `agents/writer_agent.py` — `write()` accepts `concise` param
- Modified: `agents/researcher_agent.py` — `research()` accepts `concise` param
- Modified: `agents/custom_agent_runner.py` — `respond()` accepts `concise` param

**Status:** Executed

## 2026-02-27 — Agent Hub Cleanup + Prompt Divergence Fix

**Decision:**
1. Remove `intake`, `analyst`, `researcher`, and `writer` from `default_agents.py` (and therefore from Agent Hub). These agents remain fully functional for solo chat via their Python files and the Orchestrator — they are just no longer selectable for workrooms.
2. Fix prompt divergence: `planner` and `challenger` system prompts in `default_agents.py` (used by `CustomAgentRunner` in workrooms) were lighter than their Python counterparts. Enriched both for conversational workroom use.

**Changes to planner prompt:** Removed `"Return valid JSON only"` (only valid for programmatic `build_day_plan()`); added conversational mode guidance; strengthened "WHY" framing to require naming the customer/deadline/consequence; added concrete next-action requirement.

**Changes to challenger prompt:** Synced richer "Evidence against" instruction (first-principles fallback when no data); added detail to Blind spots; added **Alternative path** as fifth structural element; added persona voice guard against hedging.

**Rationale:** When agents are added to a Workroom, `CustomAgentRunner` uses the `default_agents.py` system prompt exclusively — Python agent files are bypassed. Without this fix, a Planner in a workroom produced rigid JSON or shallow advice because its prompt lacked the full ranking intelligence.

**Scope:**
- Modified: `agents/default_agents.py` — removed intake, analyst, researcher, writer; enriched planner + challenger; PM Workflow now has 3 agents; total: 11 default agents

**Status:** Executed

---

## 2026-02-27 — Explore Experts: Problem-First Agent Discovery in Agent Hub

**Decision:** Add an "Explore Experts" primary entry point to Agent Hub. Instead of manually defining an agent, users describe a problem or challenge and the system identifies the required domain expertise, explains the reasoning (WHY), and proposes 3–5 specialist agents with full system prompts for review and one-click saving to the library.

**Rationale:** Manual agent creation requires users to already know what expertise they need — the exact gap this feature addresses. Users who don't know what agents to create are blocked. Problem-first discovery removes that barrier. Showing reasoning builds trust and helps users validate the system's interpretation of their problem.

**Scope:**
- Created: `agents/agent_designer.py` — new `AgentDesigner` class; `design(problem)` → `{reasoning, agents}`
- Modified: `app.py` — import `AgentDesigner`; 3 new session state keys (`show_explore_form`, `explore_results`, `explore_selected`); Agent Hub "Add Custom Agent" section replaced with "Add Agents" section containing dual entry points (Explore / Manual), explore pane with reasoning display + agent review cards + editable system prompts + selective save

**Status:** Executed

---

## 2026-02-27 — Agent Category Overhaul: 4-Category System + Dynamic Sections

**Decision:** Replace the coarse 2-category system ("professional" / "life") with a 4-category taxonomy (`pm_workflow`, `ai_product`, `career`, `life`) and make Agent Hub sections fully dynamic — any category string (including those generated by Explore Experts) auto-renders its own labelled section.

**Rationale:** The "professional" catch-all grouped PM workflow tools, AI product agents, and design tools together — too broad to be useful for navigation. Dynamic sections mean user-created agents from Explore Experts (e.g. `creative`, `legal`) automatically get their own section without code changes. The `career` category is reserved for future user-created career agents and won't appear until populated. Backward-compat alias (`professional` → `pm_workflow`) avoids breaking stored agent records immediately; category sync in `ensure_default_agents()` migrates them on next startup.

**Scope:**
- Modified: `agents/default_agents.py` — reclassified 13 agents: 7 → `pm_workflow` (intake, planner, analyst, challenger, writer, researcher, ux_designer); 6 → `ai_product` (biz_clarifier, science_advisor, ux_advisor, eng_advisor, ai_req_writer, req_reviewer); 2 life unchanged
- Modified: `storage/manager.py` — added category sync block in `ensure_default_agents()` to migrate stored default categories on startup
- Modified: `app.py` — new `_CATEGORY_META` (4 keys), `_CATEGORY_ALIAS` (professional→pm_workflow), updated `_category_badge()`, replaced 3 hardcoded sections with dynamic grouping, updated "Create Manually" form with 5-option selectbox + custom text input for "other"
- Modified: `agents/agent_designer.py` — system prompt updated with new category vocabulary

**Status:** Executed

---

## 2026-02-28 — Skills Framework: Agent Tool-Use Infrastructure

**Decision:** Build a skills framework that allows agents to invoke external tools (functions) via OpenAI function-calling. The framework is infrastructure-first — 3 built-in placeholder skills shipped now; actual skill extensions deferred to later sessions.

**Rationale:** Agents are currently pure system-prompt wrappers: they can only reason from what's already in their context window. A skills framework enables agents to actively retrieve live data (backlog, insights, calendar, etc.) mid-conversation. The factory pattern (Skill base class + SkillRegistry singleton + bootstrap function) means new skills can be added in one file with zero changes to the runner.

**Scope:**
- Created: `skills/__init__.py`, `skills/base.py`, `skills/registry.py`, `skills/bootstrap.py`
- Created: `skills/builtin/__init__.py`, `skills/builtin/get_date.py`, `skills/builtin/search_backlog.py`, `skills/builtin/get_insights.py`
- Modified: `models/workroom.py` — added `skill_names: list[str]` field to `CustomAgent` (default `[]`, backward-compatible)
- Modified: `agents/custom_agent_runner.py` — full tool-call loop (MAX_TOOL_ROUNDS=5), executes tool calls via SkillRegistry, falls back gracefully if skills package unavailable
- Modified: `app.py` — added `bootstrap_skills` import; call `bootstrap_skills(storage=...)` once after StorageManager is created in `_init_state()`

**Built-in skills:**
| Skill name | Class | Needs storage? | What it does |
|---|---|---|---|
| `get_current_date` | `GetCurrentDateSkill` | No | Returns today's UTC date |
| `search_backlog` | `SearchBacklogSkill` | Yes | Keyword search across CustomerRequests |
| `get_recent_insights` | `GetInsightsSkill` | Yes | Returns N most recent StrategicInsights |

**How to assign skills to an agent:**
```python
CustomAgent(key="my_agent", ..., skill_names=["get_current_date", "search_backlog"])
```

**Status:** Executed

---

## 2026-02-28 — Workroom Quality: 7→9 Improvement (5 Fixes)

**Decision:** Implement 5 targeted improvements to bring workroom multi-agent response quality from 7/10 to 9/10:
1. **Open-message detection** — `smart_route()` bypasses LLM routing for open-ended messages (e.g. "share your thoughts"), sending to ALL curated agents instead of dropping some.
2. **Document-aware grounding** — `_get_doc_context_block()` now instructs agents to cite 1-2 specific doc facts before analyzing, preventing generic questions about content already in the document.
3. **Team-awareness** — `_route_by_key()` injects a team roster into each agent's context with instruction to stay in their lane and not duplicate other agents' specialties.
4. **Tighter concise caps** — Hard cap at 3-5 sentences (max 6) across all agents. Added "you'll get follow-up turns" instruction. Reduced max_tokens: analyst 400, challenger 400, researcher 400, writer 500, custom 400.
5. **Prioritized takeaway** — Every agent ends with a `→` prefixed single takeaway (recommendation, risk, or question).

**Rationale:** Test ROOM 2 evaluation showed: agents gave overlapping responses, ignored document details, responses too long (8+ sentences), no structured takeaway, and smart_route dropped agents for open-ended messages.

**Scope:**
- Modified: `agents/orchestrator.py` — CONVERSATIONAL_MODE tightened, `_get_doc_context_block()` grounding rule, `_route_by_key()` team-awareness injection, `_is_open_ended()` + `_OPEN_ENDED_PATTERNS`, `smart_route()` early bypass, analyst max_tokens reduced
- Modified: `agents/challenger_agent.py` — concise instruction + max_tokens 400
- Modified: `agents/writer_agent.py` — concise instruction + max_tokens 500
- Modified: `agents/researcher_agent.py` — concise instruction + max_tokens 400
- Modified: `agents/custom_agent_runner.py` — concise instruction + max_tokens 400
- Created: `Tests/create_test_room3.py` — Test ROOM 3 with persisted doc context

**Status:** Executed