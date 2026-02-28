"""
Intake Agent — parses raw inputs, classifies customer requests, extracts briefing structure.

Responsibilities:
  - Parse briefing files (md/txt/pdf/docx) into structured DayPlan context
  - Extract meetings, emails, Teams messages, customer mentions from briefing
  - Classify and prioritize CustomerRequests from any source
  - Never called by other agents; only by the Orchestrator or directly

Does NOT:
  - Run staleness / risk analysis (Analyst's job)
  - Produce StrategicInsight records (Analyst's job)
  - Build FocusItem lists (Planner's job)
"""

import json
from typing import Optional

from config import MODEL, make_openai_client
from models import CustomerRequest, DayPlan
from storage import StorageManager
from utils import parse_file


SYSTEM_PROMPT = """You are the Intake Agent for a PM Strategy Copilot system.

Your job is to parse raw inputs and extract structured information.

When classifying customer requests, use these definitions:
- classification options: feature_request | bug_report | integration | support | feedback
- priority options: P0 (production-blocking / critical), P1 (high importance), P2 (medium), P3 (low / nice-to-have)
- Always provide a one-sentence rationale for both classification and priority

When parsing briefing files, extract:
- meetings_today: list of {title, start_time, duration_min}
- context_summary: structured markdown summary covering emails, Teams messages, customer mentions, action items, open flags
- customer_mentions: list of {company, context, sentiment} — these should be flagged for potential request logging

Always respond with valid JSON. Never include markdown code fences in your JSON responses.
"""

CLASSIFY_REQUEST_PROMPT = """Classify this customer request and return JSON:

Request text: "{text}"
Source: {source}

Return exactly this JSON structure (no markdown fences):
{{
  "description": "clean one-sentence summary of the request",
  "classification": "feature_request|bug_report|integration|support|feedback",
  "classification_rationale": "one sentence explaining why",
  "priority": "P0|P1|P2|P3",
  "priority_rationale": "one sentence explaining urgency/impact",
  "tags": ["tag1", "tag2"]
}}"""

PARSE_BRIEFING_PROMPT = """Parse this daily PM briefing file and return structured JSON.

Briefing content:
{content}

Return exactly this JSON structure (no markdown fences):
{{
  "meetings_today": [
    {{"title": "...", "start_time": "HH:MM", "duration_min": 30}}
  ],
  "context_summary": "markdown-formatted summary of emails, Teams messages, customer mentions, action items, and open flags",
  "customer_mentions": [
    {{"company": "...", "context": "one sentence", "sentiment": "Positive|Neutral|Concern|Urgent"}}
  ]
}}"""

CLASSIFY_BULK_PROMPT = """You are processing a bulk import of customer requests from {source_type}.

Here is the raw content:
{content}

Extract all distinct customer requests/issues/items from this content.
Return a JSON array. Each item must follow this structure (no markdown fences):
[
  {{
    "description": "clean one-sentence summary",
    "raw_input": "the original text that describes this item",
    "classification": "feature_request|bug_report|integration|support|feedback",
    "classification_rationale": "one sentence",
    "priority": "P0|P1|P2|P3",
    "priority_rationale": "one sentence",
    "tags": ["tag1"]
  }}
]

If there are no identifiable requests, return an empty array: []"""


class IntakeAgent:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.client = make_openai_client()

    def _call_claude(self, user_content: str, max_tokens: int = 2048) -> str:
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("IntakeAgent API error: %s", exc)
            raise RuntimeError(f"Intake agent connection error: {exc}") from exc

    def _parse_json(self, text: str) -> dict | list:
        """Robustly parse JSON from Claude response."""
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(text)

    # ------------------------------------------------------------------ #
    # Single request classification                                        #
    # ------------------------------------------------------------------ #

    def classify_request(
        self,
        text: str,
        source: str = "chat",
        source_ref: str = "typed",
    ) -> CustomerRequest:
        """Classify a single request text and save it to storage."""
        prompt = CLASSIFY_REQUEST_PROMPT.format(text=text, source=source)
        raw = self._call_claude(prompt)

        try:
            data = self._parse_json(raw)
        except json.JSONDecodeError:
            # Fallback: minimal request
            data = {
                "description": text[:200],
                "classification": "feature_request",
                "classification_rationale": "Could not parse AI response.",
                "priority": "P2",
                "priority_rationale": "Default priority assigned.",
                "tags": [],
            }

        req = CustomerRequest(
            description=data.get("description", text[:200]),
            raw_input=text,
            source=source,  # type: ignore[arg-type]
            source_ref=source_ref,
            classification=data.get("classification", "feature_request"),  # type: ignore[arg-type]
            classification_rationale=data.get("classification_rationale", ""),
            priority=data.get("priority", "P2"),  # type: ignore[arg-type]
            priority_rationale=data.get("priority_rationale", ""),
            tags=data.get("tags", []),
            status="triaged",
        )
        self.storage.save_request(req)
        return req

    # ------------------------------------------------------------------ #
    # Briefing file processing                                            #
    # ------------------------------------------------------------------ #

    def process_briefing(
        self,
        file_source,
        filename: str = "",
        date: str = "",
    ) -> tuple[DayPlan, list[dict]]:
        """
        Parse a briefing file and return:
          - A partially-built DayPlan (context_summary + meetings filled in)
          - List of detected customer mentions for PM review

        The DayPlan is NOT saved here — the Planner saves it after adding focus_items.
        """
        parsed = parse_file(file_source, filename)
        prompt = PARSE_BRIEFING_PROMPT.format(content=parsed["text"][:8000])
        raw = self._call_claude(prompt, max_tokens=3000)

        try:
            data = self._parse_json(raw)
        except json.JSONDecodeError:
            data = {
                "meetings_today": [],
                "context_summary": parsed["text"][:2000],
                "customer_mentions": [],
            }

        if not date:
            from datetime import date as _date
            date = _date.today().isoformat()

        plan = DayPlan(
            date=date,
            briefing_source=parsed["filename"] or "pasted",
            context_summary=data.get("context_summary", ""),
            meetings_today=data.get("meetings_today", []),
        )

        return plan, data.get("customer_mentions", [])

    # ------------------------------------------------------------------ #
    # Bulk import (CSV / PDF / Word)                                      #
    # ------------------------------------------------------------------ #

    def process_bulk_file(
        self,
        file_source,
        filename: str = "",
    ) -> list[CustomerRequest]:
        """
        Parse a CSV/PDF/Word file and extract all customer requests.
        Returns a list of (unsaved) CustomerRequest objects for PM review.
        """
        parsed = parse_file(file_source, filename)
        source_type = parsed["source_type"]
        prompt = CLASSIFY_BULK_PROMPT.format(
            source_type=source_type,
            content=parsed["text"][:8000],
        )
        raw = self._call_claude(prompt, max_tokens=4000)

        try:
            items = self._parse_json(raw)
            if not isinstance(items, list):
                items = []
        except json.JSONDecodeError:
            items = []

        requests = []
        for item in items:
            req = CustomerRequest(
                description=item.get("description", ""),
                raw_input=item.get("raw_input", ""),
                source=source_type,  # type: ignore[arg-type]
                source_ref=parsed["filename"],
                classification=item.get("classification", "feature_request"),  # type: ignore[arg-type]
                classification_rationale=item.get("classification_rationale", ""),
                priority=item.get("priority", "P2"),  # type: ignore[arg-type]
                priority_rationale=item.get("priority_rationale", ""),
                tags=item.get("tags", []),
                status="triaged",
            )
            requests.append(req)
        return requests

    def save_requests(self, requests: list[CustomerRequest]) -> list[CustomerRequest]:
        """Persist a list of already-created CustomerRequest objects."""
        saved = []
        for req in requests:
            saved.append(self.storage.save_request(req))
        return saved

    # ------------------------------------------------------------------ #
    # Chat-mode: extract request from natural language                    #
    # ------------------------------------------------------------------ #

    def extract_and_log_from_chat(self, message: str) -> CustomerRequest:
        """
        Given a natural-language PM message in chat, extract and log a request.
        Example: "Log this: Stripe need webhook retry logic, blocking production."
        """
        # Strip log command prefixes
        for prefix in ("log this:", "log:", "add request:", "add this:"):
            if message.lower().startswith(prefix):
                message = message[len(prefix):].strip()
                break

        return self.classify_request(message, source="chat", source_ref="typed")
