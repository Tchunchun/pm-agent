"""
Workroom Conversation Evaluation
=================================
Runs a standardised multi-turn conversation against a test workroom and
measures routing accuracy, response quality, and decision-detection precision.

Usage:
    python3 Tests/eval_workroom.py              # Run eval, print report, save results
    python3 Tests/eval_workroom.py --history     # Print past results only

Results are appended to Tests/eval_results.json after each run.
"""

import json
import re
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
RESULTS_FILE = TESTS_DIR / "eval_results.json"

agent_dir = TESTS_DIR.parent / "agent-claude"
sys.path.insert(0, str(agent_dir))

from storage import StorageManager
from agents.orchestrator import Orchestrator, _is_decision


# ================================================================== #
# Quality thresholds — a run PASSES only if all thresholds are met    #
# ================================================================== #

THRESHOLDS = {
    "routing_fallback_max": 0,       # Max fallback menu hits (0 = perfect routing)
    "conciseness_min_pct": 60,       # Min % of responses with <= 6 sentences
    "no_structure_min_pct": 80,      # Min % of responses without headers/bullets
    "decision_max": 3,               # Max decision detections (advisory = low)
}


# ================================================================== #
# Test messages                                                       #
# ================================================================== #

TEST_MESSAGES = [
    {
        "id": "Q1",
        "label": "Open-ended kick-off",
        "message": (
            "Please review the customer requirements and share your thoughts "
            "on the feasibility, questions, or concerns."
        ),
        "expect": "round_table",
    },
    {
        "id": "Q2",
        "label": "Conversational acknowledgement",
        "message": "Good questions to start. Please continue.",
        "expect": "smart_route",
    },
    {
        "id": "Q3",
        "label": "Specific question",
        "message": "What are the key requirements for the denial prediction model?",
        "expect": "smart_route",
    },
    {
        "id": "Q4",
        "label": "@mention single agent",
        "message": (
            "@science_advisor what are the main challenges or concerns you have "
            "from the science perspective in building the prediction model?"
        ),
        "expect": "single_route",
    },
    {
        "id": "Q5",
        "label": "Follow-up with context",
        "message": (
            "For data quality, I think we should make it clear to customer that "
            "the quality of data matters to the prediction outcomes. For the model "
            "interpretability, yes we should inform user too. What follow-up "
            "questions should we ask the customer?"
        ),
        "expect": "smart_route",
    },
    {
        "id": "Q6",
        "label": "Short conversational turn",
        "message": "Good question. Please continue.",
        "expect": "smart_route",
    },
]


# ================================================================== #
# Metric helpers                                                      #
# ================================================================== #

def count_sentences(text: str) -> int:
    """Rough sentence count via period/question/exclamation splitting."""
    clean = re.sub(r'\*\*|\*|`|#{1,6}\s', '', text)
    clean = re.sub(r'\n+', ' ', clean)
    sents = re.split(r'[.!?]+', clean)
    return len([s for s in sents if s.strip() and len(s.strip()) > 10])


def has_structured_formatting(text: str) -> bool:
    """Check if response uses headers, bullets, or numbered lists."""
    patterns = [
        r'^#{1,6}\s',
        r'^\s*[-*]\s',
        r'^\s*\d+\.\s',
        r'\*\*[A-Z].*?\*\*:',
    ]
    for line in text.split('\n'):
        for p in patterns:
            if re.match(p, line.strip()):
                return True
    return False


def has_takeaway(text: str) -> bool:
    """Check if response contains a takeaway arrow."""
    return '\u2192' in text  # →


def evaluate_response(text: str) -> dict:
    """Return per-response metrics dict."""
    return {
        "sentences": count_sentences(text),
        "concise": count_sentences(text) <= 6,
        "has_structure": has_structured_formatting(text),
        "has_takeaway": has_takeaway(text),
        "is_decision": _is_decision(text),
        "char_count": len(text),
    }


# ================================================================== #
# Display helpers                                                     #
# ================================================================== #

def _divider(char='\u2501', width=80):
    print(char * width)


def _print_response(label: str, text: str, metrics: dict):
    print(f"\n  \U0001f4ce {label}")
    wrapped = textwrap.fill(text, width=76, initial_indent='     ', subsequent_indent='     ')
    print(wrapped[:600])
    if len(text) > 600:
        print(f"     ...({len(text)} total chars)")

    sents = metrics['sentences']
    concise_ok = '\u2705' if metrics['concise'] else '\u274c'
    format_ok = '\u2705' if not metrics['has_structure'] else '\u26a0\ufe0f  structured'
    takeaway_ok = '\u2705' if metrics['has_takeaway'] else '\u26a0\ufe0f  missing \u2192'
    print(f"     [{concise_ok} {sents} sentences | {format_ok} | {takeaway_ok}]")


# ================================================================== #
# Core evaluation runner                                              #
# ================================================================== #

def run_evaluation() -> dict:
    """Execute the full eval suite and return a structured result dict."""
    storage = StorageManager()
    orch = Orchestrator(storage)

    # Find the test workroom with document context
    active_ws = None
    for ws in storage.list_workrooms(include_archived=True):
        if ws.document_context and ws.active_agents:
            active_ws = ws
            break

    if not active_ws:
        print("ERROR: No workroom found with document_context.")
        sys.exit(1)

    print("=" * 80)
    print("  WORKROOM CONVERSATION EVALUATION")
    print("=" * 80)
    print(f"\n  Workroom : {active_ws.title} (id: {active_ws.id})")
    print(f"  Agents   : {active_ws.active_agents}")
    print(f"  Document : {active_ws.document_context.get('filename', '?')}")
    print(f"  Goal     : {active_ws.goal[:100]}...")

    # Conversation history (reset each run)
    msgs: list[dict] = [
        {"role": "assistant", "content": "Welcome to the workroom session.", "agent": "Facilitator"}
    ]

    # Accumulators
    question_results: list[dict] = []
    all_response_metrics: list[dict] = []
    fallback_hits = 0
    total_time = 0.0

    for test in TEST_MESSAGES:
        _divider()
        print(f"\n  \U0001f9ea {test['id']}: {test['label']}")
        print(f"  \U0001f4e4 User: \"{test['message'][:100]}{'...' if len(test['message']) > 100 else ''}\"")
        print(f"  \U0001f4cb Expected: {test['expect']}")

        msgs.append({"role": "user", "content": test['message']})

        t0 = time.time()
        result = orch.handle_message(
            test['message'],
            file_bytes=None,
            filename="",
            date="2026-02-27",
            document_context=active_ws.document_context,
            conversation_history=msgs,
            active_agents=active_ws.active_agents,
            workroom=active_ws,
        )
        elapsed = time.time() - t0
        total_time += elapsed

        agent_label = result.get("agent", "?")
        text = result.get("text", "")
        multi = result.get("multi_response") or []

        print(f"  \u23f1\ufe0f  Response in {elapsed:.1f}s \u2014 Agent: {agent_label}")

        is_fallback = "I'm not sure what you'd like to do" in text
        if is_fallback:
            fallback_hits += 1
            print(f"  \u274c HIT FALLBACK MENU \u2014 routing failed")

        q_result = {
            "id": test["id"],
            "label": test["label"],
            "expected": test["expect"],
            "agent": agent_label,
            "is_fallback": is_fallback,
            "elapsed_s": round(elapsed, 1),
            "response_count": len(multi) if multi else 1,
            "responses": [],
        }

        if multi:
            print(f"  \U0001f4ca Round table: {len(multi)} agents responded")
            for resp in multi:
                r_text = resp.get('text', '')
                m = evaluate_response(r_text)
                _print_response(resp.get('agent', '?'), r_text, m)
                m["agent"] = resp.get('agent', '?')
                q_result["responses"].append(m)
                all_response_metrics.append(m)
        else:
            m = evaluate_response(text)
            _print_response(agent_label, text, m)
            m["agent"] = agent_label
            q_result["responses"].append(m)
            all_response_metrics.append(m)

        question_results.append(q_result)
        msgs.append({"role": "assistant", "content": text, "agent": agent_label})

    # ── Aggregate scores ──────────────────────────────────────────
    total_responses = len(all_response_metrics)
    concise_pass = sum(1 for m in all_response_metrics if m["concise"])
    no_struct_pass = sum(1 for m in all_response_metrics if not m["has_structure"])
    takeaway_pass = sum(1 for m in all_response_metrics if m["has_takeaway"])
    decision_count = sum(1 for m in all_response_metrics if m["is_decision"])

    concise_pct = round(concise_pass / total_responses * 100) if total_responses else 0
    no_struct_pct = round(no_struct_pass / total_responses * 100) if total_responses else 0
    takeaway_pct = round(takeaway_pass / total_responses * 100) if total_responses else 0

    scorecard = {
        "tests_run": len(TEST_MESSAGES),
        "total_responses": total_responses,
        "fallback_hits": fallback_hits,
        "conciseness_pass": concise_pass,
        "conciseness_total": total_responses,
        "conciseness_pct": concise_pct,
        "no_structure_pass": no_struct_pass,
        "no_structure_total": total_responses,
        "no_structure_pct": no_struct_pct,
        "takeaway_pass": takeaway_pass,
        "takeaway_total": total_responses,
        "takeaway_pct": takeaway_pct,
        "decision_count": decision_count,
        "total_time_s": round(total_time, 1),
        "avg_time_s": round(total_time / len(TEST_MESSAGES), 1),
    }

    # ── Pass / fail against thresholds ────────────────────────────
    checks = {
        "routing": fallback_hits <= THRESHOLDS["routing_fallback_max"],
        "conciseness": concise_pct >= THRESHOLDS["conciseness_min_pct"],
        "no_structure": no_struct_pct >= THRESHOLDS["no_structure_min_pct"],
        "decision_detection": decision_count <= THRESHOLDS["decision_max"],
    }
    overall_pass = all(checks.values())

    # ── Print scorecard ───────────────────────────────────────────
    _divider()
    print("\n" + "=" * 80)
    print("  EVALUATION SCORECARD")
    print("=" * 80)

    def _status(ok):
        return "\u2705 PASS" if ok else "\u274c FAIL"

    print(f"\n  Routing:")
    print(f"    Fallback hits   : {fallback_hits}/{len(TEST_MESSAGES)}  "
          f"(max {THRESHOLDS['routing_fallback_max']})  {_status(checks['routing'])}")

    print(f"\n  Conciseness (\u22646 sentences):")
    print(f"    Pass rate       : {concise_pass}/{total_responses} ({concise_pct}%)  "
          f"(min {THRESHOLDS['conciseness_min_pct']}%)  {_status(checks['conciseness'])}")

    print(f"\n  Prose only (no headers/bullets):")
    print(f"    Pass rate       : {no_struct_pass}/{total_responses} ({no_struct_pct}%)  "
          f"(min {THRESHOLDS['no_structure_min_pct']}%)  {_status(checks['no_structure'])}")

    print(f"\n  Takeaway (\u2192 arrow):")
    print(f"    Present         : {takeaway_pass}/{total_responses} ({takeaway_pct}%)  (informational)")

    print(f"\n  Decision detection:")
    print(f"    Decisions found : {decision_count}  "
          f"(max {THRESHOLDS['decision_max']})  {_status(checks['decision_detection'])}")

    print(f"\n  Performance:")
    print(f"    Total time      : {scorecard['total_time_s']}s")
    print(f"    Avg per question: {scorecard['avg_time_s']}s")

    print(f"\n  {'=' * 40}")
    print(f"  OVERALL: {_status(overall_pass)}")
    print(f"  {'=' * 40}\n")

    # Build result record
    result_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workroom": active_ws.title,
        "agents": active_ws.active_agents,
        "scorecard": scorecard,
        "thresholds": THRESHOLDS,
        "checks": checks,
        "overall_pass": overall_pass,
        "questions": question_results,
    }

    return result_record


# ================================================================== #
# Result persistence                                                  #
# ================================================================== #

def save_result(record: dict):
    """Append a result record to the JSON history file."""
    history = load_history()
    history.append(record)
    RESULTS_FILE.write_text(json.dumps(history, indent=2, default=str))
    print(f"  Result saved to {RESULTS_FILE.relative_to(TESTS_DIR.parent)}")


def load_history() -> list[dict]:
    """Load past results from the JSON history file."""
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return []


def print_history():
    """Print a comparison table of all past evaluation runs."""
    history = load_history()
    if not history:
        print("No evaluation history found.")
        return

    print("=" * 96)
    print("  EVALUATION HISTORY")
    print("=" * 96)
    print(f"\n  {'#':<4} {'Timestamp':<22} {'Route':<8} {'Concise':<10} {'Prose':<10} "
          f"{'Decide':<8} {'Time':<8} {'Result':<8}")
    print(f"  {'─'*4} {'─'*22} {'─'*8} {'─'*10} {'─'*10} {'─'*8} {'─'*8} {'─'*8}")

    for i, rec in enumerate(history, 1):
        sc = rec.get("scorecard", {})
        ts = rec.get("timestamp", "?")[:19].replace("T", " ")
        route = f"{sc.get('fallback_hits', '?')}/{sc.get('tests_run', '?')}"
        concise = f"{sc.get('conciseness_pct', '?')}%"
        prose = f"{sc.get('no_structure_pct', '?')}%"
        decide = str(sc.get("decision_count", "?"))
        total_t = f"{sc.get('total_time_s', '?')}s"
        passed = "\u2705 PASS" if rec.get("overall_pass") else "\u274c FAIL"

        print(f"  {i:<4} {ts:<22} {route:<8} {concise:<10} {prose:<10} "
              f"{decide:<8} {total_t:<8} {passed:<8}")

    print(f"\n  {len(history)} run(s) recorded.\n")


# ================================================================== #
# Main                                                                #
# ================================================================== #

def main():
    if "--history" in sys.argv:
        print_history()
        return

    record = run_evaluation()
    save_result(record)

    # Show comparison with previous run if available
    history = load_history()
    if len(history) >= 2:
        prev = history[-2]["scorecard"]
        curr = history[-1]["scorecard"]
        print("\n  COMPARISON WITH PREVIOUS RUN:")
        print(f"  {'─' * 50}")

        def _delta(key, label, fmt="%", lower_better=False):
            p, c = prev.get(key, 0), curr.get(key, 0)
            diff = c - p
            if fmt == "%":
                arrow = "\u2191" if diff > 0 else ("\u2193" if diff < 0 else "\u2194")
                if lower_better:
                    arrow = "\u2193" if diff > 0 else ("\u2191" if diff < 0 else "\u2194")
                print(f"    {label:<22}: {p}% \u2192 {c}% ({arrow} {abs(diff)}pp)")
            else:
                arrow = "\u2191" if diff > 0 else ("\u2193" if diff < 0 else "\u2194")
                if lower_better:
                    arrow = "\u2193" if diff > 0 else ("\u2191" if diff < 0 else "\u2194")
                print(f"    {label:<22}: {p} \u2192 {c} ({arrow} {abs(diff)})")

        _delta("conciseness_pct", "Conciseness")
        _delta("no_structure_pct", "Prose only")
        _delta("takeaway_pct", "Takeaway")
        _delta("decision_count", "Decisions", fmt="n", lower_better=True)
        _delta("fallback_hits", "Fallback hits", fmt="n", lower_better=True)
        _delta("total_time_s", "Total time (s)", fmt="n", lower_better=True)
        print()


if __name__ == "__main__":
    main()
