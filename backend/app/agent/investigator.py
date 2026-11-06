"""Investigator Agent orchestrator for TraceGuard.

Conducts tool-grounded financial incident investigations with:
1. Max 8 tool-call steps.
2. Structured JSON output with cited event IDs.
3. Pure-code validation of claims and target resources.
4. Automatic feedback & retry loop (max 2 retries).
5. Comprehensive audit trail logging into agent_runs table.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agent.tools import (
    INVESTIGATOR_TOOLS_SCHEMA,
    tool_get_capture,
    tool_get_evidence,
    tool_get_incident,
    tool_list_events,
    tool_search_transactions,
)
from backend.app.agent.validator import validate_report
from backend.app.models.agent_run import AgentRun
from backend.app.models.incident import Incident, IncidentStatus
from backend.app.services.llm_client import LLMClient, TokenUsage

logger = logging.getLogger("traceguard.agent.investigator")

SYSTEM_PROMPT = """You are TraceGuard's Autonomous Payment Investigator.
Your job is to investigate financial incidents using verified ground truth events from PayPal Sandbox.

CORE RULES:
1. Ground every conclusion in evidence retrieved using your tools. Never fabricate or assume.
2. Max 8 tool calls per investigation.
3. If an assertion cannot be proven by the events, place it in the `unknowns` list.
4. Output MUST be valid JSON matching this schema:
{
  "summary": "Clear, objective explanation of what happened",
  "claims": [
    {
      "text": "Specific claim describing a verified event, amount, or state change",
      "event_ids": ["WH-xxxx", "WH-yyyy"]
    }
  ],
  "recommended_action": "REFUND" | "DISPUTE_EVIDENCE" | "NONE",
  "target_resource_id": "Resource ID to act upon (e.g. CAP-xxxx for refund)",
  "confidence": 0.0 to 1.0,
  "unknowns": ["Unverified aspects or missing telemetry"]
}

CRITICAL: Every item in `claims` must cite the exact `event_ids` retrieved from `list_events`.
A separate deterministic code validator will check every event ID and amount.
Reports citing non-existent event IDs will be rejected.
"""


class InvestigatorAgent:
    """Agent that drives multi-step tool reasoning and evidence-backed report synthesis."""

    def __init__(self, llm_client: LLMClient | None = None, max_steps: int = 8):
        self.llm = llm_client or LLMClient()
        self.max_steps = max_steps

    async def execute_tool(self, db: Session, name: str, args: dict[str, Any]) -> Any:
        """Dispatch a tool call to the corresponding validated Python tool."""
        logger.info("Executing tool: %s with args: %s", name, args)
        if name == "get_incident":
            return tool_get_incident(db, args.get("incident_id", ""))
        elif name == "list_events":
            return tool_list_events(db, args.get("order_ref", ""))
        elif name == "get_capture":
            return await tool_get_capture(args.get("capture_id", ""))
        elif name == "search_transactions":
            return tool_search_transactions(db, args.get("order_ref", ""))
        elif name == "get_evidence":
            return tool_get_evidence(db, args.get("order_ref", ""))
        else:
            return {"error": f"Unknown tool '{name}'"}

    async def investigate(
        self,
        db: Session,
        incident_id: str,
    ) -> tuple[dict[str, Any], AgentRun]:
        """Run the full investigation loop with tool calling, validation, and retries.

        Returns:
            (validated_report_dict, agent_run_record)
        """
        incident = db.get(Incident, incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        # Set incident status to investigating
        incident.status = IncidentStatus.INVESTIGATING.value
        db.commit()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Investigate incident '{incident.id}' for order reference '{incident.order_ref}' (anomaly type: {incident.type}). "
                "Use tools to examine the event timeline and provide your structured findings.",
            },
        ]

        recorded_steps: list[dict[str, Any]] = []
        recorded_tool_calls: list[dict[str, Any]] = []
        accumulated_usage = TokenUsage()

        step_count = 0
        final_report: dict[str, Any] = {}
        raw_response_text = ""

        # Main tool-calling loop (up to max_steps)
        while step_count < self.max_steps:
            step_count += 1
            response = await self.llm.chat(messages, tools=INVESTIGATOR_TOOLS_SCHEMA)

            # Accumulate token usage
            accumulated_usage.prompt_tokens += response.usage.prompt_tokens
            accumulated_usage.completion_tokens += response.usage.completion_tokens
            accumulated_usage.total_tokens += response.usage.total_tokens

            step_record: dict[str, Any] = {
                "step": step_count,
                "content": response.content,
                "tool_calls": [tc.model_dump() for tc in response.tool_calls],
            }
            recorded_steps.append(step_record)

            # If tool calls were requested, execute them and continue loop
            if response.tool_calls:
                # Add assistant message with tool calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function_name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in response.tool_calls
                        ],
                    }
                )

                for tc in response.tool_calls:
                    recorded_tool_calls.append(
                        {
                            "id": tc.id,
                            "function": tc.function_name,
                            "arguments": tc.arguments,
                        }
                    )
                    result = await self.execute_tool(db, tc.function_name, tc.arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, default=str),
                        }
                    )
            else:
                # Agent completed with a text/JSON response
                raw_response_text = response.content or ""
                break

        # Attempt to parse final structured JSON report
        try:
            # Clean potential markdown fences ```json ... ```
            cleaned = raw_response_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            final_report = json.loads(cleaned.strip())
        except Exception:
            logger.warning("Agent output was not valid JSON: %s", raw_response_text)
            final_report = {
                "summary": raw_response_text or "Investigation completed with unstructured output.",
                "claims": [],
                "recommended_action": "NONE",
                "target_resource_id": "UNKNOWN",
                "confidence": 0.5,
                "unknowns": ["Output could not be parsed into structured format."],
            }

        # -------------------------------------------------------------------
        # Deterministic Code Validation + Retry Loop (Core Principle 2)
        # -------------------------------------------------------------------
        max_retries = 2
        retry_count = 0
        is_valid, validation_errors = validate_report(db, incident.id, final_report)

        while not is_valid and retry_count < max_retries:
            retry_count += 1
            logger.warning(
                "Report validation failed (retry %d/%d): %s",
                retry_count,
                max_retries,
                validation_errors,
            )

            # Feed errors back to model for correction
            feedback_prompt = (
                f"Your report failed deterministic verification with {len(validation_errors)} error(s):\n"
                + "\n".join(f"- {err}" for err in validation_errors)
                + "\n\nPlease correct your claims. Cite ONLY real event IDs and ensure amounts match cited events exactly."
            )
            messages.append({"role": "user", "content": feedback_prompt})

            retry_response = await self.llm.chat(messages, tools=None)
            accumulated_usage.prompt_tokens += retry_response.usage.prompt_tokens
            accumulated_usage.completion_tokens += retry_response.usage.completion_tokens
            accumulated_usage.total_tokens += retry_response.usage.total_tokens

            try:
                cleaned_retry = (retry_response.content or "").strip()
                if cleaned_retry.startswith("```"):
                    cleaned_retry = cleaned_retry.split("\n", 1)[1]
                if cleaned_retry.endswith("```"):
                    cleaned_retry = cleaned_retry.rsplit("```", 1)[0]
                final_report = json.loads(cleaned_retry.strip())
            except Exception:
                pass

            is_valid, validation_errors = validate_report(db, incident.id, final_report)

        validation_status = "verified" if is_valid else "unverified"

        # -------------------------------------------------------------------
        # Save Agent Run Audit Log into agent_runs table
        # -------------------------------------------------------------------
        agent_run = AgentRun(
            incident_id=incident.id,
            model=self.llm.model,
            steps=recorded_steps,
            tool_calls=recorded_tool_calls,
            tokens_used=accumulated_usage.model_dump(),
            claims=final_report.get("claims", []),
            validation_status=validation_status,
            validation_errors=validation_errors,
        )
        db.add(agent_run)

        # Update incident status to awaiting_approval
        incident.status = IncidentStatus.AWAITING_APPROVAL.value
        db.commit()
        db.refresh(agent_run)

        logger.info(
            "Investigation complete for incident %s: status=%s, tokens=%d, run_id=%s",
            incident.id,
            validation_status,
            accumulated_usage.total_tokens,
            agent_run.id,
        )

        return final_report, agent_run
