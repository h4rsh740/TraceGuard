"""Provider-agnostic LLM client for TraceGuard.

Supports OpenAI, Anthropic, Gemini, and Mock providers with structured tool-calling.
Provider and model are configured via environment variables (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY).
Called strictly from the backend, never from frontend.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from backend.app.core.config import settings

logger = logging.getLogger("traceguard.llm")


class ToolCall(BaseModel):
    id: str
    function_name: str
    arguments: dict[str, Any]


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""


class LLMClient:
    """Provider-agnostic client handling tool calling across OpenAI, Anthropic, Gemini, and Mock."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.provider = (provider or settings.LLM_PROVIDER or "mock").lower()
        self.model = model or settings.LLM_MODEL or "gpt-4o-mini"
        self.api_key = api_key or settings.LLM_API_KEY
        self.timeout = timeout

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Dispatch a chat completion request to the configured LLM provider."""
        is_mock_key = (
            not self.api_key
            or self.api_key.startswith("mock")
            or self.api_key in ("mock_key", "test_key", "change_me")
        )
        if self.provider == "mock" or is_mock_key:
            return await self._mock_completion(messages, tools)

        if self.provider == "openai":
            return await self._openai_completion(messages, tools)
        elif self.provider == "anthropic":
            return await self._anthropic_completion(messages, tools)
        elif self.provider == "gemini":
            return await self._gemini_completion(messages, tools)
        else:
            logger.warning("Unknown LLM provider '%s', defaulting to mock", self.provider)
            return await self._mock_completion(messages, tools)

    async def _openai_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call OpenAI / compatible REST endpoint."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        choice = data["choices"][0]["message"]
        tool_calls = []
        if "tool_calls" in choice and choice["tool_calls"]:
            for tc in choice["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        function_name=tc["function"]["name"],
                        arguments=args,
                    )
                )

        raw_usage = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=choice.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            model=self.model,
        )

    async def _anthropic_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call Anthropic Messages REST endpoint."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Separate system message if present
        system_content = ""
        user_assistant_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                user_assistant_messages.append(m)

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": user_assistant_messages,
        }
        if system_content:
            payload["system"] = system_content

        if tools:
            # Map OpenAI tool schema to Anthropic tool schema
            anthropic_tools = []
            for t in tools:
                fn = t.get("function", {})
                anthropic_tools.append(
                    {
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {}),
                    }
                )
            payload["tools"] = anthropic_tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        tool_calls = []
        content_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        function_name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("input_tokens", 0)
        completion_tokens = raw_usage.get("output_tokens", 0)

        return LLMResponse(
            content=content_text if content_text else None,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=self.model,
        )

    async def _gemini_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call Google Gemini REST endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": str(m.get("content", ""))}],
                }
            )

        payload: dict[str, Any] = {"contents": contents}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        candidate = data.get("candidates", [{}])[0]
        content_parts = candidate.get("content", {}).get("parts", [{}])
        text_content = content_parts[0].get("text", "")

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)

        return LLMResponse(
            content=text_content,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=self.model,
        )

    async def _mock_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Deterministic mock responses for offline testing, CI, and evaluation."""
        last_message = messages[-1] if messages else {}
        role = last_message.get("role", "")
        content = last_message.get("content", "")

        # Step 1: Initial call from user -> Agent calls get_incident and list_events
        if role == "user":
            # Extract incident_id or order_ref if mentioned in prompt
            prompt_str = str(content)
            inc_id = "INC-1001"
            if "INC-" in prompt_str:
                for word in prompt_str.replace("'", " ").replace('"', " ").split():
                    if word.startswith("INC-"):
                        inc_id = word.strip(".,;:?!")
                        break

            return LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_mock_1",
                        function_name="get_incident",
                        arguments={"incident_id": inc_id},
                    )
                ],
                usage=TokenUsage(prompt_tokens=150, completion_tokens=30, total_tokens=180),
                model="mock-investigator-v1",
            )

        # Step 2: After get_incident tool response -> call list_events
        if role == "tool":
            tool_data = str(content)
            order_ref = "ORD-1001"
            if '"order_ref"' in tool_data:
                try:
                    parsed = json.loads(tool_data)
                    order_ref = parsed.get("order_ref", "ORD-1001")
                except Exception:
                    pass

            # If tool response was get_incident, request list_events
            if "INC-" in tool_data and '"order_ref"' in tool_data and '"events"' not in tool_data:
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_2",
                            function_name="list_events",
                            arguments={"order_ref": order_ref},
                        )
                    ],
                    usage=TokenUsage(prompt_tokens=250, completion_tokens=40, total_tokens=290),
                    model="mock-investigator-v1",
                )

            # Step 3: We have events data, now generate final structured report!
            # Inspect events in tool_data to find real event IDs and capture IDs
            event_ids = []
            target_resource = "CAP-002"
            try:
                parsed_events = json.loads(tool_data)
                if isinstance(parsed_events, list):
                    for ev in parsed_events:
                        if isinstance(ev, dict) and "paypal_event_id" in ev:
                            event_ids.append(ev["paypal_event_id"])
                        if isinstance(ev, dict) and ev.get("resource_id"):
                            target_resource = ev["resource_id"]
            except Exception:
                event_ids = ["WH-001", "WH-002"]

            if not event_ids:
                event_ids = ["WH-001", "WH-002"]

            # Format final structured JSON report adhering strictly to Section 5.4
            first_event_id = event_ids[0]
            second_event_id = event_ids[1] if len(event_ids) > 1 else first_event_id

            if "DIS" in order_ref or "DISP" in tool_data:
                rec_action = "DISPUTE_EVIDENCE"
                summary_text = f"Order {order_ref} subject to customer dispute; evidence vault documents available."
            else:
                rec_action = "REFUND"
                summary_text = f"Order {order_ref} experienced a duplicate capture anomaly due to simulated merchant cart timeout."

            report = {
                "summary": summary_text,
                "claims": [
                    {
                        "text": f"Initial transaction for order {order_ref} was recorded.",
                        "event_ids": [first_event_id],
                    },
                    {
                        "text": f"Secondary event occurred for order {order_ref}.",
                        "event_ids": [second_event_id],
                    },
                ],
                "recommended_action": rec_action,
                "target_resource_id": target_resource,
                "confidence": 0.98,
                "unknowns": [],
            }

            return LLMResponse(
                content=json.dumps(report, indent=2),
                tool_calls=[],
                usage=TokenUsage(prompt_tokens=450, completion_tokens=180, total_tokens=630),
                model="mock-investigator-v1",
            )

        # Fallback response
        fallback_report = {
            "summary": "Investigation completed.",
            "claims": [],
            "recommended_action": "NONE",
            "target_resource_id": "UNKNOWN",
            "confidence": 0.5,
            "unknowns": ["No sufficient evidence found."],
        }
        return LLMResponse(
            content=json.dumps(fallback_report),
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            model="mock-investigator-v1",
        )
