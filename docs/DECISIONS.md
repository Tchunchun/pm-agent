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

---

## 2026-02-28 — Google OAuth2 Authentication (Feature Branch)

**Decision:** Add Google OAuth2 authentication to gate app access behind Google sign-in. Implementation on `feat/google-auth` branch to avoid blocking `main` deployment.

**Approach:**
1. **Google OAuth2 Authorization Code Flow** — user clicks "Sign in with Google", redirected to Google consent, callback completes auth
2. **Backward compatible** — auth only activates when `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` env vars are set; without them, app works as before (anonymous placeholder user)
3. **Session-based** — re-auth per browser session; no cookie persistence in v1
4. **User store** — `data/users.json` with atomic writes (matching existing StorageManager pattern)
5. **Minimal dependencies** — only `requests` (already transitive via streamlit/openai); no heavy auth libraries

**Scope:**
- Created: `agent-claude/auth/__init__.py` — module exports: `require_auth`, `get_current_user`, `logout`, `is_auth_enabled`
- Created: `agent-claude/auth/google_oauth.py` — OAuth URL builder, token exchange, userinfo fetch
- Created: `agent-claude/auth/user_store.py` — JSON-backed user persistence with atomic writes
- Created: `agent-claude/auth/login_page.py` — Streamlit login UI with branded card + Google button
- Created: `agent-claude/auth/session.py` — Session management: CSRF state, callback handling, `require_auth()` gating
- Modified: `agent-claude/config.py` — added `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `APP_URL` env vars
- Modified: `agent-claude/app.py` — auth gate after `set_page_config`, logout button in sidebar, user avatar display
- Modified: `agent-claude/requirements.txt` — added `requests>=2.28`

**Env vars required for activation:**
- `GOOGLE_CLIENT_ID` — from Google Cloud Console OAuth 2.0 credentials
- `GOOGLE_CLIENT_SECRET` — from Google Cloud Console OAuth 2.0 credentials
- `APP_URL` — (optional) defaults to `http://localhost:8501`; set to production URL in Azure

**Status:** Executed

---

## 2026-03-01 — Agno Framework Adoption

**Decision:** Replace all raw OpenAI SDK calls with Agno Agent framework (v2.5.8). Every LLM interaction now goes through `agno.agent.Agent` instead of `openai.ChatCompletion.create()`.

**Rationale:** Agno provides a structured agent abstraction with built-in tool-call loop, structured outputs, and message management. This eliminates ~200 lines of manual tool-call iteration code in `CustomAgentRunner`, standardizes the LLM interface across all agents, and positions the project for future features (Teams, Knowledge, State Management).

**Scope:**
- Modified: `agent-claude/requirements.txt` — added `agno[openai]>=2.5.8`
- Modified: `agent-claude/config.py` — added `get_agno_model(max_tokens=None)` factory returning `agno.models.azure.AzureOpenAI` or `agno.models.openai.OpenAIChat`; kept `make_openai_client()` for test backward compat
- Created: `agent-claude/skills/tools.py` — 3 plain Agno tool functions replacing old Skill class hierarchy
- Modified: `agent-claude/skills/__init__.py` — simplified to export only `skills.tools` functions
- Modified: `agent-claude/agents/custom_agent_runner.py` — fully rewritten; Agno Agent replaces manual tool-call loop
- Modified: `agent-claude/agents/facilitator_agent.py` — uses Agno Agent via `_run_facilitator()` helper
- Modified: `agent-claude/agents/topic_classifier.py` — uses Agno Agent for classification
- Modified: `agent-claude/agents/agent_designer.py` — uses Agno Agent for team design
- Modified: `agent-claude/agents/orchestrator.py` — all 5 raw OpenAI calls replaced (summarize_document, _handle_document_query, smart_route, generate_output, removed `self._openai`)
- Modified: `agent-claude/app.py` — `_parse_meeting_context()` uses Agno Agent; removed `bootstrap_skills` import/call
- Deleted: `agent-claude/agents/challenger_agent.py` — dead code (never imported)
- Deleted: `agent-claude/agents/writer_agent.py` — dead code (never imported)
- Deleted: `agent-claude/agents/researcher_agent.py` — dead code (never imported)
- Deleted: `agent-claude/skills/base.py`, `skills/registry.py`, `skills/bootstrap.py`, `skills/builtin/` — old Skill class hierarchy replaced by `skills/tools.py`

**Key technical notes:**
- `max_completion_tokens` is a model-level param in Agno (not Agent-level): pass via `get_agno_model(max_tokens=N)`
- Azure model class is `agno.models.azure.AzureOpenAI` (not AzureOpenAIChat)
- `Agent.run(input=str|List[Message])` returns `RunOutput` with `.content` field
- Tool functions are plain Python functions; Agno auto-generates schemas from docstrings + type hints

**Status:** Executed

---

## 2026-03-09 — Streaming Responses for Workroom Chat

**Decision:** Add token-by-token streaming for single-agent responses in workroom chat. When exactly one agent responds (focused mode, or smart_route selecting 1 agent), tokens stream live into the Streamlit UI via `st.write_stream()`. Multi-agent round-table and 2-agent mini round tables remain batch (unchanged).

**Rationale:** User reported workroom chat feels slow because each agent response blocks until fully complete. Streaming gives immediate visual feedback, reducing perceived latency. Scope limited to single-agent paths to avoid complexity of streaming N parallel agents.

**Scope:**
- Modified: `agent-claude/agents/custom_agent_runner.py` — added `respond_stream()` generator method alongside `respond()`. Uses `Agent.run(stream=True)` and yields `RunContentEvent.content` chunks.
- Modified: `agent-claude/agents/orchestrator.py` — added `route_by_key_stream()` (streaming dispatch by key) and `smart_route_stream()` (LLM routing → single-agent streaming or None for multi-agent fallback). Added `Generator` to imports.
- Modified: `agent-claude/app.py` — rewrote Phase 2 processing block: focused mode uses `route_by_key_stream()` → `st.write_stream()`, open mode tries `smart_route_stream()` first with batch fallback, round table unchanged.

**Key technical notes:**
- Agno streaming: `Agent.run(input=..., stream=True)` → `Iterator[RunOutputEvent | RunOutput]`
- Filter on `chunk.event == RunEvent.run_content.value` (= `"RunContent"`) to get text deltas
- `st.write_stream(generator)` accepts any string generator, returns concatenated full text
- Existing `respond()`, `_route_by_key()`, `smart_route()` untouched (backward compatible)
- Facilitator falls back to non-streaming (yields full text in one chunk)

**Status:** Executed

---

## 2026-03-09 — Fix Empty Streaming Responses in Workroom Concise Mode

**Decision:** Increase `max_completion_tokens` from 500 to 2000 for workroom (concise) mode in both `respond()` and `respond_stream()`.

**Rationale:** `gpt-5-mini` is a reasoning model that uses internal reasoning tokens counted against the `max_completion_tokens` budget. With concise mode's 500-token limit, the model's reasoning consumed the entire budget, leaving 0 tokens for visible output. The concise constraint in the system prompt already limits response length (3-6 sentences), so increasing the token budget to 2000 lets the model reason properly while still producing short output.

**Root cause evidence:**
- Workroom messages stored with empty content despite correct agent routing
- `max_tokens=500` + analyst prompt + concise constraint → 0 RunContent chunks
- `max_tokens=2000` + same prompt → 106 chunks (working)
- `max_tokens=500` + analyst prompt (no concise) → 112 chunks (working)

**Scope:**
- Modified: `agent-claude/agents/custom_agent_runner.py` — changed `get_agno_model(max_tokens=500 if concise else 2000)` to `get_agno_model(max_tokens=2000)` in both `respond()` and `respond_stream()`.

**Status:** Executed

---

## 2026-03-09 — Full Streaming Support for Open Discussion Mode

**Decision:** Extend streaming to cover all open mode scenarios — single-agent, multi-agent, and open-ended messages. Previously only single-agent selections streamed; multi-agent and open-ended fell back to batch.

**Rationale:** User expects consistent streaming in open mode. Sequential streaming of multiple agents provides immediate feedback for each agent while maintaining readability, rather than waiting for all agents to finish via batch.

**Design:**
- `smart_route_stream()` return type changed from `tuple | None` to `list[tuple[str, Generator]] | None`
- Single agent selection → `[(label, gen)]` — streams one agent
- Multi-agent selection (2+) → `[(label1, gen1), (label2, gen2)]` — streams each sequentially
- Open-ended messages → streams all active agents sequentially (previously went to batch round_table)
- Returns `None` only on routing error (batch fallback)
- App.py iterates the list, streaming each agent into its own `chat_message("assistant")` bubble
- Single-response stored as simple message; multi-response stored with `multi_response` list for proper re-rendering

**Scope:**
- Modified: `agent-claude/agents/orchestrator.py` — `smart_route_stream()` returns list of (label, generator) tuples; open-ended and multi-agent paths now produce streams
- Modified: `agent-claude/app.py` — open mode handler iterates stream list, renders each agent sequentially via `st.write_stream()`

---

## 2026-03-09 — Workroom Response Quality Improvements

**Decision:** Implement 5 improvements based on review of the "Plan for the weekend" workroom session where agents repeatedly asked clarifying questions instead of delivering outputs, duplicated each other's content, and the writer drafted inter-agent messages instead of user-facing content.

**Changes:**

1. **Reduce clarification loops (action-bias):** Added `_ACTION_BIAS_CONSTRAINT` to `custom_agent_runner.py` — instructs agents to assume reasonable defaults and deliver a usable output first, limiting follow-up questions to at most one truly critical question.

2. **Turn-awareness for delivery mode:** Added `_DELIVERY_TURN_THRESHOLD` (3 user messages) — after this threshold, agents receive an instruction to deliver concrete output and stop asking questions. Counts user turns from `conversation_history`.

3. **Frustration detection:** Added `_detect_frustration()` in `orchestrator.py` — regex-based detection of impatience signals ("what's the output?", "just give me", "stop asking", etc.) plus a heuristic for short messages after 3+ user turns. When triggered, injects `_FRUSTRATION_MODE_CONSTRAINT` into all agent prompts to force immediate delivery mode.

4. **Round-table deduplication:** Added `_deduplicate_round_table()` in `orchestrator.py` — after all agents respond in parallel, an LLM pass edits responses to remove cross-agent redundancy so each agent adds only its unique perspective. Falls back to original responses on error.

5. **Writer targets end-users:** Updated writer system prompt in both `default_agents.py` and `custom_agents.json` — added AUDIENCE RULE that defaults to end-user audience, explicitly prohibits drafting messages to other AI agents, and instructs writer to synthesise discussion into user-actionable content.

**Rationale:** The weekend-planning workroom session revealed that agents asked for energy level 3 times, all 4 agents restated identical facts (drive time, pet fees, group size), the user expressed frustration ("what's the plan?") which was ignored, and the writer drafted a "Teams message to weekend_planner" instead of a shareable plan for the user.

**Scope:**
- Modified: `agent-claude/agents/custom_agent_runner.py` — new constraints (`_ACTION_BIAS_CONSTRAINT`, `_FRUSTRATION_MODE_CONSTRAINT`, `_DELIVERY_TURN_THRESHOLD`), `respond()` and `respond_stream()` accept `frustration_detected` param
- Modified: `agent-claude/agents/orchestrator.py` — `_detect_frustration()` function, `_deduplicate_round_table()` method, frustration propagation through `smart_route()`, `round_table()`, `_route_by_key()`, and their streaming variants
- Modified: `agent-claude/agents/default_agents.py` — writer agent system prompt updated with AUDIENCE RULE
- Modified: `agent-claude/data/custom_agents.json` — live writer agent prompt updated

**Status:** Executed

**Status:** Executed

## 2026-03-09 — Web Connectivity: Web Search & Google Maps via Agno Toolkits

**Decision:** Enable web connectivity using Agno's built-in toolkits (`WebSearchTools`, `GoogleMapTools`) instead of building custom wrappers. Use Option A: only the Researcher agent receives `web_search` tools; Google Maps available to agents via `skill_names` configuration.

**Changes:**

1. **Toolkit factory in `_resolve_tools()`:** Added `_build_toolkit_factories()` and `_TOOLKIT_FACTORIES` dict to `custom_agent_runner.py`. Maps `"web_search"` → `WebSearchTools(cache_results=True)` and `"google_maps"` → `GoogleMapTools(include_tools=[...], cache_results=True)`. Agno `Agent(tools=[...])` accepts both plain functions and Toolkit objects. Adding a future integration (Jira, Slack, GitHub) = one entry in this dict.

2. **Researcher agent wired with web search:** Added `skill_names=["web_search", "search_backlog", "get_recent_insights"]` to both `default_agents.py` and live `custom_agents.json`. Updated system prompt to instruct the agent when to use web search vs. general knowledge.

3. **Dependencies:** Added `ddgs>=6.0` (for `WebSearchTools` — DuckDuckGo meta-search, free, no API key) and `googlemaps>=4.10` (for `GoogleMapTools` — requires `GOOGLE_MAPS_API_KEY`).

4. **Config:** Added `GOOGLE_MAPS_API_KEY` to `config.py`. Web search works out of the box with no key.

**Rationale:** Agno ships 120+ pre-built toolkits. Building custom wrappers would duplicate tested, cached, filterable code. The toolkit factory dict provides the same scalability as a custom registry with zero new files.

**Scope:**
- Modified: `agent-claude/agents/custom_agent_runner.py` — `_build_toolkit_factories()`, `_TOOLKIT_FACTORIES`, refactored `_resolve_tools()`
- Modified: `agent-claude/agents/default_agents.py` — Researcher agent: added `skill_names`, updated description + system prompt
- Modified: `agent-claude/data/custom_agents.json` — live Researcher agent updated
- Modified: `agent-claude/config.py` — added `GOOGLE_MAPS_API_KEY`
- Modified: `agent-claude/requirements.txt` — added `ddgs>=6.0`, `googlemaps>=4.10`

**Status:** Executed

---

## 2026-03-09 — Fix Streaming: Reasoning Model Token Budget

**Decision:** Increase `max_tokens` for internal utility agents (SmartRouter, MeetingContextParser) to accommodate reasoning models (gpt-5-mini / o-series) that consume tokens for chain-of-thought before generating output.

**Rationale:** After upgrading to `gpt-5-mini`, the SmartRouter's `max_tokens=100` was entirely consumed by internal reasoning tokens (100 reasoning + 0 output), producing empty `.content` on every call. This caused `smart_route_stream()` to always return `None`, falling back to the batch (non-streaming) code path — making it appear that streaming was broken. The MeetingContextParser at `max_tokens=400` was similarly at risk.

**Changes:**
- SmartRouter in `smart_route()`: 100 → 500
- SmartRouter in `smart_route_stream()`: 100 → 500
- MeetingContextParser in `app.py`: 400 → 800

**Scope:**
- Modified: `agent-claude/agents/orchestrator.py` — both SmartRouter instances
- Modified: `agent-claude/app.py` — MeetingContextParser

**Status:** Executed

---

## 2026-03-09 — Agent Chaining: Research-First Pipeline

**Decision:** Implement agent chaining so the Researcher agent runs silently as a data-gathering layer before domain experts respond. When smart_route determines a question needs real-world facts (restaurants, hotels, prices, events, directions), Researcher executes first (with `web_search` tool), then its output is injected as grounded context into the selected domain expert(s). The user only sees the expert's synthesized answer — not the raw Researcher output.

**Rationale:** In the "Plan for weekend" workroom, the Dining Curator (no web_search) and Researcher (has web_search) both responded to "Any restaurants?" in parallel, producing conflicting outputs — generic placeholders from the Curator vs. real venue names from the Researcher. This is a structural problem: domain experts lack factual grounding, while Researcher lacks domain synthesis. Chaining solves both: one search pass feeds all experts, experts synthesize from real data, user sees one coherent answer. This scales to any number of domain agents without per-agent tool configuration.

**Design:**
- SmartRouter prompt updated to return structured JSON: `{"agents": [...], "needs_research": bool}`
- New `_run_research_phase()` method runs Researcher silently and returns factual context
- `smart_route()` and `smart_route_stream()` detect `needs_research` → run research phase → inject output as `research_context` into expert prompts via the existing `doc_context` mechanism
- Researcher doesn't need to be in `active_agents` — used as infrastructure
- Works for single agent, mini round-table, and full round-table

**Scope:**
- Modified: `agent-claude/agents/orchestrator.py` — SMART_ROUTE_SYSTEM prompt, smart_route(), smart_route_stream(), new _run_research_phase()
- Unchanged: `agents/custom_agent_runner.py`, `models/`, `app.py`, `data/`

---

## 2026-03-09 — Summarize Routing Fix + Writer Context-Awareness

**Decision:** Fix "summarize"/"recap" requests routing to all agents (round-table) instead of Writer. Three changes: (1) Add summarize/recap/wrap-up/consolidate/compile patterns to `WRITE_PATTERNS` for solo-chat intent detection. (2) Fix `_is_open_ended()` to check intent patterns BEFORE the short-message heuristic — messages like "Please summarize the itinerary" (5 words, no ?, no @) were false-positive open-ended. (3) Add `SUMMARIZATION / SYNTHESIS RULE` to `SMART_ROUTE_SYSTEM` prompt so the LLM router sends such requests to Writer only in workroom mode. Additionally, enrich Writer's system prompt with synthesis/summarization instructions: scan full chat history, detect output format from context (itinerary for trips, project brief for projects, meeting summary for meetings), merge/deduplicate multi-agent contributions, include specifics, and flag gaps.

**Rationale:** In the "Plan for weekend" workroom, "Please summarize the itinerary" (MSG 23) went to all 6 agents. The Writer didn't know it should compile the whole conversation into an itinerary format. Root cause was (a) the short-message heuristic in `_is_open_ended()` catching it before intent detection, (b) no summarize patterns in `WRITE_PATTERNS`, (c) SmartRouter had no rule about summarize→Writer, and (d) Writer's prompt only covered drafting communications, not synthesizing conversations.

**Scope:**
- Modified: `agent-claude/agents/orchestrator.py` — WRITE_PATTERNS (6 new patterns), `_is_open_ended()` (intent check first), SMART_ROUTE_SYSTEM (synthesis routing rule)
- Modified: `agent-claude/data/custom_agents.json` — Writer description and system_prompt (synthesis instructions, format detection, itinerary template)

**Status:** Executed

---

## 2026-03-09 — Facilitator Empty Responses (max_tokens too low for reasoning model)

**Decision:** Increase `max_completion_tokens` across all low-limit Agent calls to accommodate `gpt-5-mini`'s reasoning token overhead. Facilitator 600/700→2000, SmartRouter 500→1500, DocumentSummarizer 1200→3000, DocumentQA 1500→3000.

**Rationale:** The deployed model is `gpt-5-mini`, a reasoning model that consumes internal reasoning tokens from the `max_completion_tokens` budget. With `max_completion_tokens=600`, the model used all 600 tokens on reasoning, leaving 0 tokens for visible output. This caused the Facilitator to save empty messages (opening, periodic summaries) despite the code path executing correctly. Verified: `output_tokens=600` with `content=""`. After increasing to 2000, the same prompt produced 786 chars of high-quality summary. Custom agents (at 2000) were unaffected because 2000 provides enough headroom.

**Scope:**
- Modified: `agent-claude/agents/facilitator_agent.py` — `_run_facilitator()` default 700→2000, `open_session()` 700→2000, `generate_summary()` 600→2000
- Modified: `agent-claude/agents/orchestrator.py` — SmartRouter 500→1500 (×2), DocumentSummarizer 1200→3000, DocumentQA 1500→3000

**Status:** Executed