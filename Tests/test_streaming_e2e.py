#!/usr/bin/env python3
"""End-to-end test of the actual smart_route_stream code path"""
import sys, json, time
sys.path.insert(0, "/Users/chunchun/Documents/ccfiles/PM Agent/agent-claude")
from config import get_agno_model
from agno.agent import Agent

# Test 1: Does router.run() return something with .content?
print("=== Test 1: Router response structure ===")
router = Agent(
    name="SmartRouter",
    model=get_agno_model(max_tokens=100),
    instructions="Return a JSON array of agent keys. Nothing else.",
    markdown=False,
    add_datetime_to_context=False,
)

result = router.run(input="Pick one from: researcher, planner, analyst. Return JSON array.")
print("Result type:", type(result).__name__)
print("Has .content:", hasattr(result, 'content'))
print(".content value:", repr(getattr(result, 'content', 'MISSING')))
print("Has .output:", hasattr(result, 'output'))
print(".output value:", repr(getattr(result, 'output', 'MISSING')))

# Check type of content
content = getattr(result, 'content', None)
if content is None:
    # Maybe it's .output now?
    content = getattr(result, 'output', None)
print("Content to parse:", repr(content))

# Try to parse it like smart_route_stream does
if content:
    raw = content.strip() if isinstance(content, str) else str(content).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
        print("Parsed successfully:", parsed)
    except json.JSONDecodeError as e:
        print("JSON parse error:", e)
        print("Raw content:", repr(raw))
else:
    print("No content found! Checking all attributes...")
    for attr in sorted(dir(result)):
        if attr.startswith('_'):
            continue
        val = getattr(result, attr)
        if callable(val):
            continue
        print("  {}: {}".format(attr, repr(val)[:200]))

# Test 2: Streaming check
print("\n=== Test 2: Streaming produces tokens? ===")
from agno.agent import RunEvent
from agno.models.message import Message

agent = Agent(
    name="TestAgent",
    model=get_agno_model(max_tokens=100),
    instructions="Reply briefly.",
    markdown=True,
)
msgs = [Message(role="user", content="Say hello")]
chunks = []
for ch in agent.run(input=msgs, stream=True):
    if hasattr(ch, "event") and ch.event == RunEvent.run_content.value:
        if ch.content:
            chunks.append(str(ch.content))
print("Content chunks:", len(chunks))
print("Joined:", "".join(chunks)[:200])
