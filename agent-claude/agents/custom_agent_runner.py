"""
CustomAgentRunner — executes user-defined agents with their own system prompt.

Supports optional skill/tool-use: if the agent's CustomAgent definition
includes skill_names, those skills are looked up in the global SkillRegistry
and passed to the LLM as OpenAI function-calling tools.

Tool-call loop (up to MAX_TOOL_ROUNDS):
  1. Call LLM with tools=[...]
  2. If finish_reason == "tool_calls" → execute each tool, append results,
     loop back to step 1.
  3. Otherwise → return the text response.
"""

import json
import logging

from config import MODEL, make_openai_client
from models.workroom import CustomAgent

logger = logging.getLogger(__name__)

# Safety cap: prevent infinite tool-call loops
MAX_TOOL_ROUNDS = 5


class CustomAgentRunner:
    def __init__(self, agent_def: CustomAgent):
        self.agent_def = agent_def
        self.client = make_openai_client()

    def respond(
        self,
        message: str,
        conversation_history: list | None = None,
        document_context: dict | None = None,
        concise: bool = False,
        doc_context: str = "",
    ) -> str:
        # ------------------------------------------------------------------ #
        # Build system prompt                                                 #
        # ------------------------------------------------------------------ #
        system_prompt = self.agent_def.system_prompt
        if concise:
            system_prompt += (
                "\n\nCRITICAL CONSTRAINT — You are in a live workroom discussion. "
                "You MUST respond in 3-5 sentences (absolute hard max 6 sentences). "
                "Do NOT use headers, bullet lists, numbered lists, or multi-section formatting. "
                "Write in flowing prose paragraphs only. "
                "Cite specific facts from the document context — don't ask questions the doc already answers. "
                "You'll get follow-up turns — don't try to cover everything now. "
                "End with → your single most important takeaway, question, or recommendation."
            )
        # Prefer pre-built summary (doc_context) over raw document text for cost efficiency
        if doc_context:
            system_prompt += f"\n\n{doc_context}"
        elif document_context:
            filename = document_context.get("filename", "the uploaded document")
            system_prompt += (
                f"\n\nA reference document has been uploaded to this session: **{filename}**. "
                "The full text of this document is embedded directly in the user message under "
                "'Document context'. You already have access to all of its content — do NOT say "
                "you cannot access the file. Read the embedded text and use it to answer."
            )

        # ------------------------------------------------------------------ #
        # Build message history                                               #
        # ------------------------------------------------------------------ #
        messages = [{"role": "system", "content": system_prompt}]

        history_window = 12 if concise else 8
        if conversation_history:
            for msg in conversation_history[-history_window:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Skip any prior confused "cannot access" messages to avoid reinforcing them
                if not content or role not in ("user", "assistant"):
                    continue
                if "cannot access" in content.lower() or "i need to extract" in content.lower():
                    continue
                messages.append({"role": role, "content": content})

        user_content = message
        # Only embed full doc text if no pre-built summary was provided (non-workroom mode)
        if document_context and not doc_context:
            doc_text = document_context.get("text", "")[:8000]
            user_content = (
                f"Document context ({document_context.get('filename', '')}):\n"
                f"---\n{doc_text}\n---\n\n{message}"
            )

        messages.append({"role": "user", "content": user_content})

        # ------------------------------------------------------------------ #
        # Resolve skills / tools                                              #
        # ------------------------------------------------------------------ #
        tools: list[dict] = []
        if self.agent_def.skill_names:
            try:
                from skills.registry import registry as skill_registry
                tools = skill_registry.to_openai_tools(self.agent_def.skill_names)
            except ImportError:
                logger.warning("CustomAgentRunner: skills package not available")

        # ------------------------------------------------------------------ #
        # LLM call — with optional tool-call loop                            #
        # ------------------------------------------------------------------ #
        try:
            for _round in range(MAX_TOOL_ROUNDS):
                call_kwargs: dict = {
                    "model": MODEL,
                    "max_completion_tokens": 500 if concise else 2000,
                    "messages": messages,
                }
                if tools:
                    call_kwargs["tools"] = tools
                    call_kwargs["tool_choice"] = "auto"

                response = self.client.chat.completions.create(**call_kwargs)
                choice = response.choices[0]

                # ---- tool_calls: execute each tool and loop ----
                if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Append assistant turn (including tool_calls metadata)
                    assistant_msg: dict = {
                        "role": "assistant",
                        "content": choice.message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.message.tool_calls
                        ],
                    }
                    messages.append(assistant_msg)

                    # Execute each tool call and append results
                    try:
                        from skills.registry import registry as skill_registry
                    except ImportError:
                        skill_registry = None

                    for tc in choice.message.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            fn_args = {}

                        if skill_registry:
                            result = skill_registry.execute(fn_name, **fn_args)
                        else:
                            result = f"[Skill '{fn_name}' could not be executed: registry unavailable]"

                        logger.debug(
                            "CustomAgentRunner: tool '%s'(%s) → %s",
                            fn_name, fn_args, result[:120],
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })
                    # Continue loop — LLM will now see tool results
                    continue

                # ---- normal response ----
                return (choice.message.content or "").strip()

            # Exceeded MAX_TOOL_ROUNDS — return whatever the last response was
            logger.warning(
                "CustomAgentRunner: exceeded %d tool rounds for agent '%s'",
                MAX_TOOL_ROUNDS, self.agent_def.key,
            )
            return (choice.message.content or "").strip()  # type: ignore[possibly-undefined]

        except Exception as exc:
            logger.exception("CustomAgentRunner API error: %s", exc)
            return (
                f"_({self.agent_def.label} is temporarily unavailable due to a "
                "connection issue. Please try again.)_"
            )
