"""Deterministic stub for the OpenAI client used in tests.

The ``FakeLLMClient`` plays back a scripted list of ``LLMResponse`` objects,
one per ``complete_with_tools`` / ``complete_json`` call. Tests can inspect
the recorded message log to assert on what the agent said.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.llm_client import LLMResponse, ToolCall


@dataclass
class FakeLLMClient:
    """Plays back scripted responses and records every call."""

    script: list  # list of LLMResponse for complete_with_tools calls
    final_json: dict  # returned by complete_json
    tool_calls_log: list = field(default_factory=list)  # tool calls the agent made
    messages_log: list = field(default_factory=list)  # raw messages passed in

    def __post_init__(self):
        self._cursor = 0

    # ------------------------------------------------------------------
    def complete_with_tools(self, messages, tools):
        self.messages_log.append(list(messages))
        if self._cursor >= len(self.script):
            # Out of scripted responses: return a final text response
            return LLMResponse(text="(no more scripted responses)")
        resp = self.script[self._cursor]
        self._cursor += 1
        if resp.tool_call:
            self.tool_calls_log.append(resp.tool_call)
        return resp

    def complete_json(self, messages, schema_hint: str = "{}"):
        self.messages_log.append(list(messages))
        return self.final_json

    # ------------------------------------------------------------------
    @staticmethod
    def scripted_tool_call(name: str, **arguments) -> LLMResponse:
        return LLMResponse(tool_call=ToolCall(name=name, arguments=arguments))

    @staticmethod
    def scripted_text(text: str) -> LLMResponse:
        return LLMResponse(text=text)