"""LLM-powered quality auditor that runs after the deterministic pipeline.

The agent does NOT make cleaning decisions (those stay deterministic in
``pipeline.py``). Instead, it reads the before/after profiles, optionally
calls a few inspection tools, and returns a structured critique with
suggested new validation rules.

Designed to be safely stubbable in tests via ``FakeLLMClient``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .llm_client import LLMClient, LLMResponse, LLMError

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "quality_audit.txt"
MAX_TURNS = 4

# JSON schema the final report must match (used as the JSON-mode hint).
REPORT_SCHEMA_HINT = json.dumps(
    {
        "headline": "string",
        "what_went_well": ["string"],
        "concerns": ["string"],
        "suggested_rules": [
            {
                "column": "string",
                "kind": "str_regex|value_range|isin|not_null",
                "params": {},
                "rationale": "string",
            }
        ],
        "sample_explanation": "string",
    }
)


@dataclass
class AgentReport:
    """Structured audit result."""

    headline: str
    what_went_well: list[str]
    concerns: list[str]
    suggested_rules: list[dict]
    sample_explanation: str
    turns: int = 0
    used_fallback: bool = False

    def to_markdown(self) -> str:
        """Render as a human-readable markdown report."""
        out = [f"# Agent Audit\n", f"**{self.headline}**\n"]
        out.append("\n## What went well\n")
        out.extend(f"- {x}\n" for x in self.what_went_well)
        out.append("\n## Concerns\n")
        if self.concerns:
            out.extend(f"- {x}\n" for x in self.concerns)
        else:
            out.append("_None flagged._\n")
        out.append("\n## Suggested new validation rules\n")
        if self.suggested_rules:
            for r in self.suggested_rules:
                out.append(
                    f"- **{r.get('column', '?')}** ({r.get('kind', '?')}): "
                    f"{r.get('rationale', '')}\n"
                )
        else:
            out.append("_None suggested._\n")
        out.append(f"\n## Sample explanation\n\n{self.sample_explanation}\n")
        if self.used_fallback:
            out.append(
                "\n> _Note: this report was generated from a static fallback "
                "because no OPENAI_API_KEY was set._\n"
            )
        return "".join(out)


class CleaningAgent:
    """LLM-powered auditor with bounded tool use and graceful fallback.

    Parameters
    ----------
    llm_client
        Anything implementing ``complete_with_tools`` and ``complete_json``.
        In production this is ``LLMClient()``; in tests it is ``FakeLLMClient``.
    quality_report_path
        Optional path to the deterministic before/after markdown. The agent
        reads it via the ``read_quality_report`` tool.
    after_profile_fn
        Callable returning a per-column profile dict for the cleaned data.
        Defaults to a stub that returns an empty dict.
    """

    TOOL_DEFINITIONS: list[dict] = [
        {
            "type": "function",
            "function": {
                "name": "read_quality_report",
                "description": "Return the markdown before/after quality summary.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "profile_after",
                "description": "Return per-column statistics for the cleaned dataset.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_rule",
                "description": "Propose a new validation rule; recorded in the report.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": ["str_regex", "value_range", "isin", "not_null"],
                        },
                        "params": {"type": "object"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["column", "kind", "rationale"],
                },
            },
        },
    ]

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        quality_report_path: Path | None = None,
        after_profile_fn: Callable[[], dict] | None = None,
    ) -> None:
        self.llm = llm_client
        self.quality_report_path = quality_report_path
        self._after_profile_fn = after_profile_fn or (lambda: {})
        self._collected_rules: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def audit(self, before_profile: dict, after_profile: dict, sample_row: dict | None = None) -> AgentReport:
        """Run the audit. Returns an AgentReport either way."""
        if self.llm is None:
            return self._fallback_report(before_profile, after_profile)

        system_prompt = self._load_system_prompt()
        user_msg = self._format_user_message(before_profile, after_profile, sample_row)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        turns = 0
        for _ in range(MAX_TURNS):
            turns += 1
            try:
                resp = self.llm.complete_with_tools(messages, tools=self.TOOL_DEFINITIONS)
            except LLMError as exc:
                log.warning("LLM tool call failed (turn %d): %s; falling back", turns, exc)
                return self._fallback_report(before_profile, after_profile)

            if resp.tool_call:
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{turns}",
                                "type": "function",
                                "function": {
                                    "name": resp.tool_call.name,
                                    "arguments": json.dumps(resp.tool_call.arguments),
                                },
                            }
                        ],
                    }
                )
                tool_result = self._dispatch_tool(resp.tool_call)
                messages.append(
                    {"role": "tool", "tool_call_id": f"call_{turns}", "content": tool_result}
                )
                continue

            # Final turn: ask for structured JSON.
            messages.append({"role": "assistant", "content": resp.text or ""})
            try:
                final = self.llm.complete_json(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Now produce the final audit JSON matching the schema. "
                                "Incorporate the suggested_rules you collected via tools."
                            ),
                        }
                    ],
                    schema_hint=REPORT_SCHEMA_HINT,
                )
            except LLMError as exc:
                log.warning("LLM JSON call failed: %s; falling back", exc)
                return self._fallback_report(before_profile, after_profile)

            return self._build_report(final, turns)

        # Hit MAX_TURNS without a final answer.
        log.warning("Agent exhausted %d turns without final report; falling back", MAX_TURNS)
        return self._fallback_report(before_profile, after_profile)

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------
    def _dispatch_tool(self, tool_call) -> str:
        name = tool_call.name
        args = tool_call.arguments or {}
        if name == "read_quality_report":
            return self._read_quality_report()
        if name == "profile_after":
            return json.dumps(self._after_profile_fn(), default=str)
        if name == "suggest_rule":
            rule = {
                "column": args.get("column"),
                "kind": args.get("kind"),
                "params": args.get("params", {}),
                "rationale": args.get("rationale", ""),
            }
            self._collected_rules.append(rule)
            return json.dumps({"recorded": True, "rule": rule})
        return json.dumps({"error": f"unknown tool: {name}"})

    def _read_quality_report(self) -> str:
        if not self.quality_report_path or not self.quality_report_path.exists():
            return "(no quality report available)"
        return self.quality_report_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_system_prompt(self) -> str:
        return PROMPT_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _format_user_message(before: dict, after: dict, sample: dict | None) -> str:
        lines = [
            "## Before profile",
            "```json",
            json.dumps(before, indent=2, default=str),
            "```",
            "",
            "## After profile",
            "```json",
            json.dumps(after, indent=2, default=str),
            "```",
        ]
        if sample:
            lines += ["", "## Sample row to explain", "```json", json.dumps(sample, indent=2, default=str), "```"]
        return "\n".join(lines)

    def _build_report(self, payload: dict, turns: int) -> AgentReport:
        rules = list(self._collected_rules)
        extra = payload.get("suggested_rules") or []
        for r in extra:
            if r not in rules:
                rules.append(r)
        return AgentReport(
            headline=str(payload.get("headline", "")).strip(),
            what_went_well=list(payload.get("what_went_well") or []),
            concerns=list(payload.get("concerns") or []),
            suggested_rules=rules,
            sample_explanation=str(payload.get("sample_explanation", "")).strip(),
            turns=turns,
            used_fallback=False,
        )

    @staticmethod
    def _fallback_report(before: dict, after: dict) -> AgentReport:
        """Static report so the pipeline completes without an API key."""
        before_rows = before.get("rows", "?")
        after_rows = after.get("rows", "?")
        before_missing = before.get("missing_pct", 0.0)
        after_missing = after.get("missing_pct", 0.0)
        headline = (
            f"Cleaned {before_rows} -> {after_rows} rows; "
            f"missing-cell rate {before_missing:.2f}% -> {after_missing:.2f}%."
        )
        return AgentReport(
            headline=headline,
            what_went_well=["Pipeline ran end-to-end without errors."],
            concerns=["Static fallback used; no LLM audit available."],
            suggested_rules=[],
            sample_explanation="(LLM unavailable in fallback mode.)",
            turns=0,
            used_fallback=True,
        )