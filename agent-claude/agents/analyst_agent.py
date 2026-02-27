"""
Analyst Agent — sole generator of strategic insight and risk signals.

Operates in four modes (all triggered through Chat):
  1. Trend Detection   — what themes are growing in frequency?
  2. Gap Detection     — what is being asked for with no committed response?
  3. Risk Detection    — what could escalate if not addressed?
  4. Decision Support  — structured trade-off analysis for explicit choices

Reads: CustomerRequests (all), StrategicInsights (all)
Writes: StrategicInsight records

Does NOT:
  - Read raw files (intake-agent's job)
  - Build FocusItem lists (planner-agent's job)
  - Run daily planning (planner-agent's job)
"""

import json
from datetime import datetime, timezone

from openai import OpenAI

from config import MODEL, OPENAI_API_KEY, MIN_REQUESTS_FOR_ANALYSIS
from models import StrategicInsight
from storage import StorageManager


SYSTEM_PROMPT = """You are the Analyst Agent for a PM Strategy Copilot.

Your job is to detect patterns, gaps, and risks in customer request data, and support PM decision-making.

Every output must follow: What → Why → Recommended Action

Confidence levels:
- High: 3+ requests with same theme, or a P0 with explicit urgency signal
- Medium: 2 requests with related theme, or inferred urgency without explicit signal
- Low: single request, or pattern is speculative

Return valid JSON only — no markdown fences, no extra text.
"""

TREND_PROMPT = """Analyse these customer requests for emerging trends and growing themes.

Total requests: {total_count}
Requests data:
{requests_data}

Existing insights (for context, avoid duplicating):
{existing_insights}

Identify the 1–3 most significant trends. For each, return this JSON structure:
{{
  "insights": [
    {{
      "insight_type": "trend",
      "title": "Short title for this trend",
      "what": "What is specifically happening — be concrete with numbers",
      "why": "Why this matters right now — deadlines, urgency signals, business impact",
      "recommended_action": "One concrete next step the PM should take",
      "confidence": "high|medium|low",
      "period": "last-30-days",
      "linked_request_ids": ["id1", "id2"]
    }}
  ]
}}"""

GAP_PROMPT = """Analyse these customer requests to detect unaddressed gaps — themes that have multiple requests but no existing insight or decision covering them.

Total requests: {total_count}
Requests data:
{requests_data}

Existing insights (avoid flagging gaps that are already covered):
{existing_insights}

Identify clusters of requests with no decision/trend insight. Return this JSON structure:
{{
  "insights": [
    {{
      "insight_type": "gap",
      "title": "Short title for this gap",
      "what": "What is being asked for — specific cluster with count",
      "why": "Why this gap matters — customer impact, workarounds being built, hidden load",
      "recommended_action": "One concrete next step to address this gap",
      "confidence": "high|medium|low",
      "period": "last-30-days",
      "linked_request_ids": ["id1", "id2"]
    }}
  ]
}}"""

RISK_PROMPT = """Analyse these customer requests for escalation risks — P0s without progress, stale high-priority items, silent customers.

Total requests: {total_count}
Requests data:
{requests_data}

Today's date: {today}

Existing risk insights (avoid duplicating):
{existing_insights}

Identify 1–3 risks. Return this JSON structure:
{{
  "insights": [
    {{
      "insight_type": "risk",
      "title": "Short title for this risk",
      "what": "What specifically is at risk — be concrete with time elapsed, customer names",
      "why": "Why this could escalate — exec visibility, SLA breach, customer silence",
      "recommended_action": "One urgent concrete action to take today",
      "confidence": "high|medium|low",
      "period": "now",
      "linked_request_ids": ["id1", "id2"]
    }}
  ]
}}"""

DECISION_PROMPT = """Support a PM decision by analysing customer request data as evidence.

The PM is deciding: {decision_question}

Options to evaluate: {options}

Request data to inform the decision:
{requests_data}

Existing insights for context:
{existing_insights}

Return a structured decision analysis as this JSON:
{{
  "insights": [
    {{
      "insight_type": "decision",
      "title": "Decision: {short_title}",
      "what": "Summary of the options and the signal strength for each",
      "why": "The key trade-offs, risks for each option, and which signal is stronger",
      "recommended_action": "The recommended choice with specific rationale",
      "confidence": "high|medium|low",
      "period": "now",
      "linked_request_ids": ["id1", "id2"]
    }}
  ]
}}"""


def _format_requests(requests) -> str:
    if not requests:
        return "No requests in database."
    lines = []
    for req in requests[:50]:  # Cap to avoid token overflow
        lines.append(
            f"[{req.id}] {req.priority} {req.classification} | "
            f"surfaced:{req.surface_count}x | tags:{','.join(req.tags)} | "
            f"created:{req.created_at[:10]} | {req.description}"
        )
    return "\n".join(lines)


def _format_insights(insights) -> str:
    if not insights:
        return "No existing insights."
    lines = []
    for ins in insights[:20]:
        lines.append(
            f"[{ins.id}] {ins.insight_type.upper()}·{ins.confidence}: {ins.title}"
        )
    return "\n".join(lines)


class AnalystAgent:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def _call_claude(self, user_content: str) -> str:
        response = self.client.chat.completions.create(
            model=MODEL,
            max_tokens=3000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content.strip()

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(text)

    def _low_data_warning(self, count: int) -> str | None:
        if count < MIN_REQUESTS_FOR_ANALYSIS:
            return (
                f"⚠️ Low data warning: Only {count} requests in the database "
                f"(recommended: {MIN_REQUESTS_FOR_ANALYSIS}+). "
                "Analysis may be speculative — import more historical requests for better signal."
            )
        return None

    def _save_insights(self, items_data: list[dict]) -> list[StrategicInsight]:
        saved = []
        for item in items_data:
            try:
                ins = StrategicInsight(
                    insight_type=item.get("insight_type", "trend"),
                    title=item.get("title", "Untitled insight"),
                    what=item.get("what", ""),
                    why=item.get("why", ""),
                    recommended_action=item.get("recommended_action", ""),
                    confidence=item.get("confidence", "medium"),
                    period=item.get("period", "last-30-days"),
                    linked_request_ids=item.get("linked_request_ids", []),
                )
                self.storage.save_insight(ins)
                saved.append(ins)
            except Exception:
                pass
        return saved

    def _run_mode(self, prompt: str) -> tuple[list[StrategicInsight], str | None]:
        """Run a prompt and return (saved_insights, warning_message)."""
        all_requests = self.storage.list_requests()
        warning = self._low_data_warning(len(all_requests))

        raw = self._call_claude(prompt)
        try:
            data = self._parse_json(raw)
            items = data.get("insights", [])
        except (json.JSONDecodeError, KeyError):
            items = []

        saved = self._save_insights(items)
        return saved, warning

    # ------------------------------------------------------------------ #
    # Mode 1 — Trend Detection                                            #
    # ------------------------------------------------------------------ #

    def detect_trends(self) -> tuple[list[StrategicInsight], str | None]:
        all_requests = self.storage.list_requests()
        existing = self.storage.list_insights()

        prompt = TREND_PROMPT.format(
            total_count=len(all_requests),
            requests_data=_format_requests(all_requests),
            existing_insights=_format_insights(existing),
        )
        return self._run_mode(prompt)

    # ------------------------------------------------------------------ #
    # Mode 2 — Gap Detection                                              #
    # ------------------------------------------------------------------ #

    def detect_gaps(self) -> tuple[list[StrategicInsight], str | None]:
        all_requests = self.storage.list_requests()
        existing = self.storage.list_insights(
            insight_type=["decision", "trend"]
        )

        prompt = GAP_PROMPT.format(
            total_count=len(all_requests),
            requests_data=_format_requests(all_requests),
            existing_insights=_format_insights(existing),
        )
        return self._run_mode(prompt)

    # ------------------------------------------------------------------ #
    # Mode 3 — Risk Detection                                             #
    # ------------------------------------------------------------------ #

    def detect_risks(self) -> tuple[list[StrategicInsight], str | None]:
        all_requests = self.storage.list_requests()
        existing = self.storage.list_insights(insight_type=["risk"])

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prompt = RISK_PROMPT.format(
            total_count=len(all_requests),
            requests_data=_format_requests(all_requests),
            today=today,
            existing_insights=_format_insights(existing),
        )
        return self._run_mode(prompt)

    # ------------------------------------------------------------------ #
    # Mode 4 — Decision Support                                           #
    # ------------------------------------------------------------------ #

    def support_decision(
        self,
        decision_question: str,
        options: list[str] | None = None,
    ) -> tuple[list[StrategicInsight], str | None]:
        all_requests = self.storage.list_requests()
        existing = self.storage.list_insights()

        options_str = "\n".join(f"- {opt}" for opt in (options or []))
        if not options_str:
            options_str = "(infer options from the question)"

        short_title = decision_question[:50] + ("..." if len(decision_question) > 50 else "")

        prompt = DECISION_PROMPT.format(
            decision_question=decision_question,
            options=options_str,
            requests_data=_format_requests(all_requests),
            existing_insights=_format_insights(existing),
            short_title=short_title,
        )
        return self._run_mode(prompt)

    # ------------------------------------------------------------------ #
    # Dispatcher — route from natural language intent                     #
    # ------------------------------------------------------------------ #

    def run_from_intent(
        self, intent: str, user_message: str
    ) -> tuple[list[StrategicInsight], str | None]:
        """
        intent: "trend" | "gap" | "risk" | "decision"
        """
        if intent == "trend":
            return self.detect_trends()
        elif intent == "gap":
            return self.detect_gaps()
        elif intent == "risk":
            return self.detect_risks()
        elif intent == "decision":
            return self.support_decision(user_message)
        else:
            # Default to trend
            return self.detect_trends()
