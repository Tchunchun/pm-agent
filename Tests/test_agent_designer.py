"""
Agent Designer (Explorer) test suite — validates AgentDesigner across diverse topics.

Usage:
    cd "PM Agent" && python3 Tests/test_agent_designer.py
"""

import sys
import json
import time
from pathlib import Path

agent_dir = Path(__file__).resolve().parent.parent / "agent-claude"
sys.path.insert(0, str(agent_dir))

from config import MODEL, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, OPENAI_API_KEY
from agents.agent_designer import AgentDesigner

# ── Test cases ────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id": "relationship_communication",
        "topic": (
            "I have conflicts with my partner and want some advice on the "
            "communication and issue summarization so that I can better "
            "communicate the issue with him and find a resolution together."
        ),
        "expect_categories": ["life"],
        "min_agents": 3,
    },
    {
        "id": "build_vs_buy",
        "topic": (
            "We need to decide whether to build or buy a recommendation "
            "engine for our platform."
        ),
        "expect_categories": ["pm_workflow", "ai_product"],
        "min_agents": 3,
    },
    {
        "id": "career_transition",
        "topic": (
            "I'm a senior engineer considering a move into engineering "
            "management. How should I evaluate the transition and prepare?"
        ),
        "expect_categories": ["career"],
        "min_agents": 3,
    },
    {
        "id": "product_launch",
        "topic": (
            "We're launching a new SaaS product in 3 months and need to "
            "coordinate marketing, pricing, and onboarding strategy."
        ),
        "expect_categories": ["pm_workflow", "marketing"],
        "min_agents": 3,
    },
    {
        "id": "health_wellness",
        "topic": (
            "I want to improve my sleep quality and build a sustainable "
            "morning routine. I've tried several apps but nothing sticks."
        ),
        "expect_categories": ["life"],
        "min_agents": 3,
    },
]

# ── Helpers ───────────────────────────────────────────────────────

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


def validate_agent(agent: dict) -> list[str]:
    """Return list of validation issues for a single agent dict."""
    issues = []
    for field in ("key", "label", "emoji", "description", "system_prompt", "category"):
        if not agent.get(field):
            issues.append(f"missing '{field}'")
    if agent.get("key") and not agent["key"].replace("_", "").isalnum():
        issues.append(f"key '{agent['key']}' is not valid snake_case")
    if agent.get("system_prompt") and len(agent["system_prompt"]) < 50:
        issues.append("system_prompt too short (<50 chars)")
    return issues


# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Agent Designer Test Suite")
    print("=" * 70)
    print(f"Endpoint: {AZURE_OPENAI_ENDPOINT or '(standard OpenAI)'}")
    print(f"Model:    {MODEL}")
    print(f"API key:  {'set' if (AZURE_OPENAI_KEY or OPENAI_API_KEY) else 'MISSING'}")
    print()

    if not (AZURE_OPENAI_KEY or OPENAI_API_KEY):
        print(f"{FAIL}  No API key configured — cannot run tests.")
        sys.exit(1)

    designer = AgentDesigner()
    results = []
    passed = 0
    failed = 0

    for tc in TEST_CASES:
        tid = tc["id"]
        print(f"── {tid} ──")
        print(f"   Topic: {tc['topic'][:80]}...")

        t0 = time.time()
        try:
            result = designer.design(tc["topic"])
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"   {FAIL}  Exception after {elapsed:.1f}s: {exc}")
            results.append({"id": tid, "status": "FAIL", "error": str(exc)})
            failed += 1
            continue

        elapsed = time.time() - t0
        agents = result.get("agents", [])
        reasoning = result.get("reasoning", "")

        # Check: got agents
        if len(agents) < tc["min_agents"]:
            print(f"   {FAIL}  Only {len(agents)} agents (need ≥{tc['min_agents']})  [{elapsed:.1f}s]")
            if not agents:
                print(f"         Reasoning: {reasoning[:120] or '(empty)'}")
            results.append({"id": tid, "status": "FAIL", "agent_count": len(agents)})
            failed += 1
            continue

        # Check: reasoning present
        if not reasoning.strip():
            print(f"   {FAIL}  No reasoning returned  [{elapsed:.1f}s]")
            results.append({"id": tid, "status": "FAIL", "error": "no reasoning"})
            failed += 1
            continue

        # Check: agent schema validity
        all_valid = True
        for agent in agents:
            issues = validate_agent(agent)
            if issues:
                print(f"   {FAIL}  Agent '{agent.get('key', '?')}' issues: {', '.join(issues)}")
                all_valid = False

        if not all_valid:
            results.append({"id": tid, "status": "FAIL", "error": "agent validation"})
            failed += 1
            continue

        # Check: unique keys
        keys = [a["key"] for a in agents]
        if len(keys) != len(set(keys)):
            print(f"   {FAIL}  Duplicate keys: {keys}")
            results.append({"id": tid, "status": "FAIL", "error": "duplicate keys"})
            failed += 1
            continue

        # All checks passed
        print(f"   {PASS}  {len(agents)} agents, reasoning present  [{elapsed:.1f}s]")
        for a in agents:
            print(f"         {a['emoji']} {a['label']} ({a['key']}) [{a['category']}]")
        results.append({
            "id": tid,
            "status": "PASS",
            "agent_count": len(agents),
            "elapsed": round(elapsed, 1),
        })
        passed += 1

        print()

    # ── Summary ───────────────────────────────────────────────────
    print("=" * 70)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    if failed:
        print(f"\nFailed tests: {', '.join(r['id'] for r in results if r['status'] == 'FAIL')}")
    print("=" * 70)

    # Write machine-readable results
    out_path = Path(__file__).parent / "eval_agent_designer.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out_path}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
