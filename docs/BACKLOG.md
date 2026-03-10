# Optimization Backlog

Deferred improvements identified from workroom evaluation analysis.
Rerun `python3 Tests/eval_workroom.py` after each change to verify quality/perf.

---

## P1 — High Impact

### 1. Conciseness post-processing guard
**Problem:** LLM responses sometimes exceed the 6-sentence target (62-92% pass rate across runs).
**Approach:** After each agent response, count sentences. If >6, truncate to 6 and append an ellipsis or "..." indicator. Apply only in workroom/concise mode.
**Expected gain:** 100% conciseness pass rate.
**Risk:** Truncation could cut off the takeaway arrow line. Must preserve the last `->` line.

### 2. Takeaway arrow reinforcement
**Problem:** Only 62-69% of responses include the required `->` takeaway line, despite the instruction in CONVERSATIONAL_MODE.
**Approach:** Post-process: if response lacks `->`, extract the last sentence and prepend `->` to it. Alternatively, add a second-pass LLM call (but this adds latency).
**Expected gain:** 90%+ takeaway rate.
**Risk:** Mechanical prepending may produce awkward phrasing. Prefer prompt tuning first.

---

## P2 — Medium Impact

### 3. Replace `_is_open_ended()` keyword list with lightweight classifier
**Problem:** Current `_OPEN_ENDED_PATTERNS` is a static list of 14 phrases. May miss variations or match when it shouldn't (e.g., short messages without `?` always route to round table).
**Approach:** Use a small heuristic (message length + question mark presence + keyword overlap score) rather than binary match. Or use the existing smart_route LLM call with a "route to all" option.
**Expected gain:** More precise routing for edge cases.
**Risk:** Low — current implementation works well. Only improve if routing errors appear.

### 4. Smart route caching
**Problem:** Every non-open-ended workroom message makes an LLM call just to decide which agent(s) respond (smart_route). This adds ~2-3s per message.
**Approach:** Cache the routing decision for identical or similar messages within a session. Or use a local lightweight model/heuristic for routing.
**Expected gain:** ~2s saved per routed message.
**Risk:** Cache invalidation if conversation context changes agent relevance.

---

## P3 — Low Impact / Future

### 5. Adaptive agent selection based on conversation phase
**Problem:** Round table always calls all active agents, even when the conversation has narrowed to 1-2 topics.
**Approach:** Track conversation topics over turns. If the last 3 turns focused on one domain (e.g., data quality), auto-narrow to the most relevant agent(s).
**Expected gain:** Fewer unnecessary agent calls, faster responses.
**Risk:** May frustrate users who want broad input. Needs an override mechanism.

### 6. Response deduplication across agents
**Problem:** In round table mode, agents sometimes make overlapping points despite the team_block instruction.
**Approach:** After collecting all parallel responses, run a lightweight dedup pass that identifies and removes repeated points (sentence-level similarity).
**Expected gain:** Shorter, more focused combined responses.
**Risk:** Adds post-processing latency. May remove legitimate agreement signals.

### 7. Google Maps integration
**Problem:** No location-aware capabilities (place search, directions, geocoding).
**Approach:** Add `"google_maps"` entry to `_TOOLKIT_FACTORIES` in `custom_agent_runner.py` using Agno's built-in `GoogleMapTools` (from `agno.tools.google.maps`). Requires `GOOGLE_MAPS_API_KEY` env var + `pip install googlemaps google-maps-places`. Use `include_tools=["search_places", "get_directions", "geocode_address"]` to limit tool count. Assign to Planner or a new Navigator agent.
**Expected gain:** Location-aware planning — find venues, get directions, geocode addresses.
**Risk:** Adds 3 tool definitions per agent. Needs paid Google API key. Low priority unless location use cases arise.

### 8. Dynamic per-message tool injection (Option C)
**Problem:** Currently tools are statically assigned to agents via `skill_names`. This means every message to the Researcher triggers web search tool availability, even when no search is needed.
**Approach:** Use Agno's Callable Factory pattern (`tools=my_factory_function`). The Orchestrator detects "this message needs web search" and injects `WebSearchTools` into whichever agent it routes to, just for that message. No agent has tools by default — tools are injected contextually.
**Expected gain:** Any agent can search the web when needed; no agent wastes context on unnecessary tool definitions. Most flexible and elegant pattern.
**Risk:** More complex routing logic. Requires extending Orchestrator with intent→tool mapping. Overkill until the project has 5+ toolkits.
**Prereq:** Current Option A implementation (toolkit factory dict) is the stepping stone. Migrate when toolkit count grows.

---

## Evaluation Baseline (2026-02-28)

| Metric | Run 1 (baseline) | Run 2 (consolidation) | Run 3 (retirement) | Run 4 (parallel+decision) |
|--------|------------------|-----------------------|--------------------|--------------------------|
| Conciseness | 77% | 69% | 92% | 62% |
| Prose only | 100% | 100% | 100% | 100% |
| Takeaway | 0% | 0% | 69% | 62% |
| Decisions | 2 | 2 | 2 | 0 |
| Total time | 85.0s | 78.0s | 48.6s | 41.6s |
| Overall | PASS | PASS | PASS | PASS |
