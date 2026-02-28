"""
Workroom Evaluation Suite — 5 Topics × 4 Turns × LLM-as-Judge
================================================================
Creates ephemeral workrooms for 5 diverse topics, runs a 4-turn
multi-agent roundtable conversation through each, and evaluates
quality using both heuristic metrics and an LLM-as-judge rubric.

Topics cover: AI use cases (2), TPM work (1), weekend planning (1),
career growth (1).

Usage:
    cd "PM Agent" && source .venv/bin/activate
    python3 Tests/eval_workroom_suite.py
"""

import sys
import re
import json
import time
import textwrap
from pathlib import Path
from datetime import date

agent_dir = Path(__file__).resolve().parent.parent / "agent-claude"
sys.path.insert(0, str(agent_dir))

from config import MODEL, make_openai_client
from storage import StorageManager
from models.workroom import WorkroomSession
from agents.orchestrator import Orchestrator


# ── Heuristic metric helpers ─────────────────────────────────────

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
    """Check if response contains a → takeaway."""
    return '→' in text


def print_divider(char='─', width=80):
    print(char * width)


def print_response(label: str, text: str, metrics: dict):
    """Pretty-print an agent response with metrics."""
    print(f"\n  📎 {label}")
    wrapped = textwrap.fill(text, width=76, initial_indent='     ', subsequent_indent='     ')
    print(wrapped[:600])
    if len(text) > 600:
        print(f"     ...({len(text)} total chars)")

    sents = metrics['sentences']
    concise_ok = '✅' if sents <= 6 else '❌'
    format_ok = '✅' if not metrics['has_structure'] else '⚠️  structured'
    takeaway_ok = '✅' if metrics['has_takeaway'] else '⚠️  missing →'
    print(f"     [{concise_ok} {sents} sent | {format_ok} | {takeaway_ok}]")


# ── LLM-as-Judge ─────────────────────────────────────────────────

JUDGE_SYSTEM = """You are an expert evaluator of multi-agent AI conversations.

You will receive a workroom conversation between a user (TPM) and multiple AI agents.
Rate the conversation on 5 dimensions using a 1-5 scale:

1. **Relevance** (1-5): Do agent responses address the stated topic and goal?
   1=off-topic, 3=partially relevant, 5=precisely on-target
2. **Differentiation** (1-5): Do agents bring distinct perspectives, or repeat each other?
   1=heavy overlap, 3=some unique points, 5=each agent clearly distinct
3. **Actionability** (1-5): Are responses concrete with next steps, or vague advice?
   1=purely abstract, 3=some concrete points, 5=clear actionable recommendations
4. **Coherence** (1-5): Does the conversation build logically across turns?
   1=disjointed, 3=loosely connected, 5=clear logical progression
5. **Conciseness** (1-5): Are responses appropriately brief for a workroom discussion?
   1=verbose/rambling, 3=acceptable length, 5=tight and focused

Return ONLY valid JSON in this exact format (no markdown fences):
{"relevance": N, "differentiation": N, "actionability": N, "coherence": N, "conciseness": N, "rationale": "1-2 sentence summary"}
"""


def llm_judge(topic_label: str, goal: str, conversation: list[dict]) -> dict:
    """Send full conversation to LLM for rubric-based evaluation."""
    client = make_openai_client()

    # Build conversation transcript
    lines = [f"TOPIC: {topic_label}", f"GOAL: {goal}", "", "CONVERSATION:"]
    for msg in conversation:
        role = msg.get("role", "?")
        agent = msg.get("agent", "")
        content = msg.get("content", "")[:500]  # Truncate for cost
        prefix = f"[{agent}]" if agent else f"[{role}]"
        lines.append(f"{prefix}: {content}")

    transcript = "\n".join(lines)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": transcript},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except Exception as exc:
        print(f"     ⚠️ Judge error: {exc}")
        return {
            "relevance": 0, "differentiation": 0, "actionability": 0,
            "coherence": 0, "conciseness": 0,
            "rationale": f"Judge failed: {exc}",
        }


# ── Evaluation Topics ────────────────────────────────────────────

EVAL_TOPICS = [
    {
        "label": "Topic 1: Customer Churn Prediction for SaaS",
        "title": "AI Churn Prediction Model",
        "goal": (
            "Define AI requirements for a customer churn prediction model for a B2B SaaS platform. "
            "Determine the right ML approach, data requirements, and success metrics."
        ),
        "outcome": "AI requirements brief with approach, data needs, and evaluation plan",
        "agents": ["biz_clarifier", "science_advisor", "eng_advisor", "req_reviewer"],
        "turns": [
            {
                "label": "T1: Kick-off",
                "message": (
                    "Our enterprise SaaS customer wants to build a churn prediction model. "
                    "They have 3 years of usage data, support tickets, and billing history. "
                    "Monthly churn rate is around 4%. Share your thoughts on the approach and feasibility."
                ),
            },
            {
                "label": "T2: Data deep-dive",
                "message": (
                    "Good points on the data requirements. What specific features should we "
                    "prioritise extracting from usage logs and support tickets? And what's the "
                    "minimum viable dataset to get a first model running?"
                ),
            },
            {
                "label": "T3: Trade-off challenge",
                "message": (
                    "The customer wants real-time churn risk scores in their dashboard with "
                    "sub-second latency, but they also want high accuracy. How should we navigate "
                    "the latency vs. accuracy trade-off? Is real-time even necessary here?"
                ),
            },
            {
                "label": "T4: Summary",
                "message": "Summarise our key recommendations and the open questions we need to take back to the customer.",
            },
        ],
    },
    {
        "label": "Topic 2: RAG-Powered Enterprise Knowledge Search",
        "title": "LLM Knowledge Base Search",
        "goal": (
            "Evaluate the feasibility of adding LLM-powered semantic search to an enterprise "
            "internal knowledge base (50K+ documents, mix of PDFs, wikis, Confluence pages). "
            "Identify key risks and infrastructure requirements."
        ),
        "outcome": "Feasibility assessment with architecture recommendation and risk register",
        "agents": ["biz_clarifier", "science_advisor", "ux_advisor", "eng_advisor"],
        "turns": [
            {
                "label": "T1: Kick-off",
                "message": (
                    "Our customer has 50,000+ internal documents across Confluence, SharePoint, "
                    "and legacy PDF archives. They want natural-language search that 'just works'. "
                    "Current keyword search has very low adoption. Let's assess feasibility."
                ),
            },
            {
                "label": "T2: Architecture specifics",
                "message": (
                    "What embedding model and vector database would you recommend for this scale? "
                    "They need to handle incremental updates as documents change daily."
                ),
            },
            {
                "label": "T3: User trust & hallucination",
                "message": (
                    "The biggest concern from leadership is hallucination risk — they can't have "
                    "the system generating answers that aren't grounded in source documents. "
                    "How do we address this? What guardrails should we build in?"
                ),
            },
            {
                "label": "T4: Summary",
                "message": "Wrap up with your key recommendations, the critical risks, and what we should propose to the customer as a phased rollout.",
            },
        ],
    },
    {
        "label": "Topic 3: Q2 Planning — API Migration vs AI Features vs Tech Debt",
        "title": "Q2 Initiative Prioritisation",
        "goal": (
            "As a TPM, I need to prioritise 3 competing Q2 initiatives: "
            "(1) API v2 migration affecting 40 enterprise customers, "
            "(2) shipping 3 new AI-powered features requested by sales, "
            "(3) addressing critical tech debt in the auth service. "
            "Help me decide what to tackle first and build a stakeholder message."
        ),
        "outcome": "Ranked priority list with rationale and draft stakeholder update",
        "agents": ["planner", "challenger", "writer"],
        "turns": [
            {
                "label": "T1: Kick-off",
                "message": (
                    "I have three competing priorities for Q2: (1) API v2 migration — 40 enterprise "
                    "customers on deprecated v1, contractual deadline end of Q3. (2) Three AI features "
                    "that sales says are blocking two $500K deals. (3) Auth service tech debt — 3 P1 "
                    "incidents in the past month, on-call team is burned out. Help me think through this."
                ),
            },
            {
                "label": "T2: Sequencing",
                "message": (
                    "Good analysis. If I only have engineering bandwidth for 1.5 of these in Q2, "
                    "what's the right sequencing? Can any of these be partially shipped?"
                ),
            },
            {
                "label": "T3: Stakeholder pushback",
                "message": (
                    "Sales leadership will push back hard if AI features slip. They're saying "
                    "these deals will close in Q2 with the features or walk. How do I handle that conversation?"
                ),
            },
            {
                "label": "T4: Summary",
                "message": "Summarise our recommendation and draft a brief stakeholder message I can send to the VP of Engineering.",
            },
        ],
    },
    {
        "label": "Topic 4: Weekend Getaway for a Family of Four",
        "title": "Family Weekend Plan",
        "goal": (
            "Plan a balanced 2-day weekend getaway for a family of four (two adults, "
            "kids ages 6 and 10). Budget around $500. Within 2 hours driving distance "
            "from Seattle. Mix of outdoor activities, rest, and good food."
        ),
        "outcome": "Day-by-day weekend plan with activities, meals, and backup options",
        "agents": ["weekend_planner", "nutritionist"],
        "turns": [
            {
                "label": "T1: Kick-off",
                "message": (
                    "We're a family of four — kids are 6 and 10. We want a weekend getaway "
                    "within 2 hours of Seattle, budget around $500. We love hiking but the kids "
                    "need variety. Share your ideas for a fun, balanced weekend."
                ),
            },
            {
                "label": "T2: Meal planning",
                "message": (
                    "Those are great activity ideas. Now help with food — the 6-year-old is a "
                    "picky eater (only likes pasta, chicken nuggets, fruit). We want to eat "
                    "healthy but keep it realistic. What should we pack vs. eat out?"
                ),
            },
            {
                "label": "T3: Rain backup",
                "message": (
                    "What if it rains on Saturday? We need indoor backup options that still "
                    "feel like a getaway, not just sitting in the hotel room."
                ),
            },
            {
                "label": "T4: Summary",
                "message": "Put together the final weekend plan with the timeline, meals, and rain backup.",
            },
        ],
    },
    {
        "label": "Topic 5: Career Transition — TPM to AI Product Manager",
        "title": "TPM to AI PM Career Plan",
        "goal": (
            "I'm a senior TPM with 8 years of experience. I want to transition into an "
            "AI Product Manager role within the next 6-12 months. Help me build a concrete "
            "90-day plan to close the skills gap and position myself for the move."
        ),
        "outcome": "90-day career transition plan with skills gap analysis and action items",
        "agents": ["planner", "challenger", "researcher"],
        "turns": [
            {
                "label": "T1: Kick-off",
                "message": (
                    "I'm a senior TPM at a large tech company with 8 years of experience managing "
                    "platform and infrastructure programs. I want to move into AI Product Management. "
                    "I have basic ML knowledge from online courses but no hands-on AI product experience. "
                    "What's my realistic path and biggest gaps?"
                ),
            },
            {
                "label": "T2: Skills prioritisation",
                "message": (
                    "Good overview of the gaps. If I can only dedicate 5-7 hours per week to "
                    "upskilling while keeping my current job, what should I focus on in the "
                    "first 30 days specifically?"
                ),
            },
            {
                "label": "T3: Challenge the plan",
                "message": (
                    "I'm worried that just taking courses won't be enough to get hired. "
                    "What's the most compelling way to demonstrate AI PM skills when I don't "
                    "have the title yet? Should I consider a lateral move internally first?"
                ),
            },
            {
                "label": "T4: Summary",
                "message": "Summarise the 90-day plan with specific weekly goals and the key decision I need to make about internal vs. external move.",
            },
        ],
    },
]


# ── Session Runner ────────────────────────────────────────────────

def run_session(topic: dict, storage: StorageManager, orch: Orchestrator) -> dict:
    """
    Run a single evaluation topic: create workroom, execute turns,
    collect metrics, run LLM judge.

    Returns a dict with per-turn metrics and judge scores.
    """
    print_divider('━')
    print(f"\n  🧪 {topic['label']}")
    print(f"  🎯 Goal: {topic['goal'][:100]}...")
    print(f"  👥 Agents: {', '.join(topic['agents'])}")

    # Create ephemeral workroom (not persisted to storage)
    ws = WorkroomSession(
        title=f"[Eval] {topic['title']}",
        goal=topic['goal'],
        key_outcome=topic['outcome'],
        mode="work" if "weekend" not in topic['title'].lower() else "life",
        active_agents=topic['agents'],
        facilitator_enabled=False,
    )

    # Conversation accumulator
    msgs: list[dict] = []

    # Per-turn metrics
    turn_metrics: list[dict] = []
    session_start = time.time()

    for i, turn in enumerate(topic['turns']):
        print(f"\n  ── {turn['label']} ──")
        print(f"  📤 \"{turn['message'][:90]}{'...' if len(turn['message']) > 90 else ''}\"")

        msgs.append({"role": "user", "content": turn['message']})

        start = time.time()
        result = orch.handle_message(
            turn['message'],
            file_bytes=None,
            filename="",
            date=str(date.today()),
            document_context=None,
            conversation_history=msgs,
            active_agents=ws.active_agents,
            workroom=ws,
        )
        elapsed = time.time() - start

        agent_label = result.get("agent", "?")
        text = result.get("text", "")
        multi = result.get("multi_response") or []

        print(f"  ⏱️  {elapsed:.1f}s — {agent_label}")

        # Check fallback
        is_fallback = "I'm not sure what you'd like to do" in text

        # Collect per-response metrics
        responses = []
        if multi:
            print(f"  📊 Round table: {len(multi)} agent(s)")
            for resp in multi:
                r_text = resp.get('text', '')
                m = {
                    'agent': resp.get('agent', '?'),
                    'sentences': count_sentences(r_text),
                    'has_structure': has_structured_formatting(r_text),
                    'has_takeaway': has_takeaway(r_text),
                    'is_fallback': False,
                    'char_count': len(r_text),
                }
                responses.append(m)
                print_response(m['agent'], r_text, m)
        else:
            m = {
                'agent': agent_label,
                'sentences': count_sentences(text),
                'has_structure': has_structured_formatting(text),
                'has_takeaway': has_takeaway(text),
                'is_fallback': is_fallback,
                'char_count': len(text),
            }
            responses.append(m)
            if is_fallback:
                print(f"  ❌ FALLBACK MENU HIT")
            else:
                print_response(agent_label, text, m)

        turn_metrics.append({
            'turn': turn['label'],
            'elapsed': elapsed,
            'responses': responses,
        })

        # Add to conversation history
        msgs.append({"role": "assistant", "content": text, "agent": agent_label})
        if multi:
            for resp in multi:
                msgs.append({
                    "role": "assistant",
                    "content": resp.get('text', ''),
                    "agent": resp.get('agent', ''),
                })

    session_elapsed = time.time() - session_start

    # ── LLM Judge ──
    print(f"\n  🤖 Running LLM judge...")
    judge_scores = llm_judge(topic['label'], topic['goal'], msgs)
    rationale = judge_scores.pop('rationale', '')
    print(f"     Scores: {judge_scores}")
    if rationale:
        print(f"     Rationale: {rationale}")

    return {
        'topic': topic['label'],
        'agents': topic['agents'],
        'turn_metrics': turn_metrics,
        'judge_scores': judge_scores,
        'judge_rationale': rationale,
        'session_elapsed': session_elapsed,
    }


# ── Scorecard ─────────────────────────────────────────────────────

def compute_session_score(result: dict) -> dict:
    """Compute heuristic pass rates and combined score for a session."""
    all_responses = []
    for tm in result['turn_metrics']:
        all_responses.extend(tm['responses'])

    total = len(all_responses) or 1
    concise_pass = sum(1 for r in all_responses if r['sentences'] <= 6)
    prose_pass = sum(1 for r in all_responses if not r['has_structure'])
    takeaway_pass = sum(1 for r in all_responses if r['has_takeaway'])
    fallback_count = sum(1 for r in all_responses if r.get('is_fallback'))

    heuristic_rate = (concise_pass + prose_pass + takeaway_pass) / (total * 3)

    judge = result['judge_scores']
    judge_vals = [v for v in judge.values() if isinstance(v, (int, float))]
    judge_avg = sum(judge_vals) / len(judge_vals) if judge_vals else 0

    # session_score = heuristic_pass_rate * 50 + judge_avg * 10  → scale 0-100
    session_score = (heuristic_rate * 50) + (judge_avg * 10)

    return {
        'total_responses': total,
        'concise_pass': concise_pass,
        'prose_pass': prose_pass,
        'takeaway_pass': takeaway_pass,
        'fallback_count': fallback_count,
        'heuristic_rate': heuristic_rate,
        'judge_avg': judge_avg,
        'session_score': round(session_score, 1),
    }


def print_scorecard(results: list[dict]):
    """Print the final aggregate scorecard."""
    print("\n" + "=" * 80)
    print("  EVALUATION SCORECARD")
    print("=" * 80)

    all_scores = []
    for result in results:
        sc = compute_session_score(result)
        all_scores.append(sc)

        print(f"\n  📋 {result['topic']}")
        print(f"     Agents: {', '.join(result['agents'])}")
        print(f"     Time: {result['session_elapsed']:.1f}s")
        print(f"     Responses: {sc['total_responses']}")
        print(f"     Concise (≤6 sent): {sc['concise_pass']}/{sc['total_responses']} "
              f"({sc['concise_pass']/sc['total_responses']*100:.0f}%)")
        print(f"     Prose-only:        {sc['prose_pass']}/{sc['total_responses']} "
              f"({sc['prose_pass']/sc['total_responses']*100:.0f}%)")
        print(f"     Takeaway (→):      {sc['takeaway_pass']}/{sc['total_responses']} "
              f"({sc['takeaway_pass']/sc['total_responses']*100:.0f}%)")
        print(f"     Fallback hits:     {sc['fallback_count']}")

        j = result['judge_scores']
        print(f"     LLM Judge: rel={j.get('relevance','?')} "
              f"diff={j.get('differentiation','?')} "
              f"act={j.get('actionability','?')} "
              f"coh={j.get('coherence','?')} "
              f"con={j.get('conciseness','?')}")
        print(f"     Session Score: {sc['session_score']}/100")

    # Aggregate
    print_divider('━')
    print("\n  📊 AGGREGATE")
    total_resp = sum(s['total_responses'] for s in all_scores)
    total_concise = sum(s['concise_pass'] for s in all_scores)
    total_prose = sum(s['prose_pass'] for s in all_scores)
    total_takeaway = sum(s['takeaway_pass'] for s in all_scores)
    total_fallback = sum(s['fallback_count'] for s in all_scores)
    avg_score = sum(s['session_score'] for s in all_scores) / len(all_scores)

    print(f"     Topics evaluated:   {len(results)}")
    print(f"     Total responses:    {total_resp}")
    print(f"     Concise pass rate:  {total_concise}/{total_resp} ({total_concise/total_resp*100:.0f}%)")
    print(f"     Prose pass rate:    {total_prose}/{total_resp} ({total_prose/total_resp*100:.0f}%)")
    print(f"     Takeaway pass rate: {total_takeaway}/{total_resp} ({total_takeaway/total_resp*100:.0f}%)")
    print(f"     Fallback hits:      {total_fallback}")
    print(f"     Average score:      {avg_score:.1f}/100")

    # Judge averages
    dims = ['relevance', 'differentiation', 'actionability', 'coherence', 'conciseness']
    print(f"\n     LLM Judge Averages:")
    for dim in dims:
        vals = [r['judge_scores'].get(dim, 0) for r in results if isinstance(r['judge_scores'].get(dim), (int, float))]
        avg = sum(vals) / len(vals) if vals else 0
        print(f"       {dim:20s}: {avg:.1f}/5")

    total_time = sum(r['session_elapsed'] for r in results)
    print(f"\n     Total eval time:    {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"\n     {'✅ PASS' if avg_score >= 70 else '❌ NEEDS IMPROVEMENT'} (target: ≥70/100)")
    print("=" * 80)


# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  WORKROOM EVALUATION SUITE — 5 Topics × 4 Turns")
    print("=" * 80)
    print(f"  Date: {date.today()}")
    print(f"  Model: {MODEL}")

    storage = StorageManager()
    orch = Orchestrator(storage)

    results = []
    for topic in EVAL_TOPICS:
        try:
            result = run_session(topic, storage, orch)
            results.append(result)
        except Exception as exc:
            print(f"\n  ❌ TOPIC FAILED: {topic['label']}")
            print(f"     Error: {exc}")
            import traceback
            traceback.print_exc()
            results.append({
                'topic': topic['label'],
                'agents': topic['agents'],
                'turn_metrics': [],
                'judge_scores': {},
                'judge_rationale': f'Session failed: {exc}',
                'session_elapsed': 0,
            })

    print_scorecard(results)


if __name__ == "__main__":
    main()
