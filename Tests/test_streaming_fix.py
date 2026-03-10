#!/usr/bin/env python3
"""Verify the SmartRouter works with increased max_tokens (500)
and that streaming produces content chunks."""
import sys, json, time
sys.path.insert(0, "/Users/chunchun/Documents/ccfiles/PM Agent/agent-claude")
from config import get_agno_model
from agno.agent import Agent, RunEvent
from agno.models.message import Message

PASS = 0
FAIL = 0

# ---- Test 1: SmartRouter with 500 tokens returns parseable JSON ----
print("=== Test 1: SmartRouter max_tokens=500 ===")
SMART_ROUTE_SYSTEM = (
    "You are an AI routing assistant. Given a user message and agents, "
    "pick the 1-2 best agents. Return ONLY a JSON array of keys."
)
router = Agent(
    name="SmartRouter",
    model=get_agno_model(max_tokens=500),
    instructions=SMART_ROUTE_SYSTEM,
    markdown=False,
    add_datetime_to_context=False,
)

prompt = (
    "Available agents:\n"
    "- researcher: Research specialist with web search capability | tools: web_search\n"
    "- planner: Builds day plans and focus items\n"
    "- analyst: Strategic analysis of trends\n\n"
    "User message: Recommend the top 3 hotels in Suncadia\n\n"
    "Which agent(s) should respond? Return JSON array of keys."
)

result = router.run(input=prompt)
content = result.content
print("  content:", repr(content))

if content and content.strip():
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
        print("  parsed:", parsed)
        print("  PASS (router returns valid JSON)")
        PASS += 1
    except json.JSONDecodeError as e:
        print("  FAIL (JSON parse error):", e)
        FAIL += 1
else:
    print("  FAIL (empty content - reasoning model consumed all tokens)")
    FAIL += 1

# ---- Test 2: Agent streaming yields content chunks ----
print("\n=== Test 2: Streaming with max_tokens=2000 ===")
agent = Agent(
    name="TestStreamer",
    model=get_agno_model(max_tokens=2000),
    instructions="You are a helpful assistant. Reply in 2-3 sentences.",
    markdown=True,
)

msgs = [Message(role="user", content="What is the capital of France?")]
chunks = []
t0 = time.time()
first_chunk_t = None

for ch in agent.run(input=msgs, stream=True):
    if hasattr(ch, "event") and ch.event == RunEvent.run_content.value:
        if ch.content:
            chunks.append(str(ch.content))
            if first_chunk_t is None:
                first_chunk_t = time.time() - t0

total_t = round(time.time() - t0, 2)
text = "".join(chunks)
print("  chunks:", len(chunks))
print("  first content at: {}s".format(round(first_chunk_t, 2) if first_chunk_t else "NEVER"))
print("  total time: {}s".format(total_t))
print("  text:", text[:150])

if len(chunks) > 1:
    print("  PASS (multiple streaming chunks)")
    PASS += 1
elif len(chunks) == 1:
    print("  WARN (only 1 chunk - not true streaming)")
    PASS += 1
else:
    print("  FAIL (0 content chunks)")
    FAIL += 1

# ---- Summary ----
print("\n=== Summary: {} PASS, {} FAIL ===".format(PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
