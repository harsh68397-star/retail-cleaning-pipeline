"""Thin OpenAI wrapper with hybrid tool-calling + JSON mode support.

Designed to be swapped out in tests by passing a fake client.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OPENAI_AVAILABLE = False


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """One turn of the LLM."""
    text: str | None = None
    tool_call: ToolCall | None = None
    raw: Any = None


class LLMError(RuntimeError):
    """Raised when the LLM client cannot produce a usable response."""


class LLMClient:
    """Hybrid tool-calling + JSON-mode client.

    Two methods:
      - complete_with_tools(): lets the LLM call functions
      - complete_json(): forces JSON output for the final report

    A fake subclass (FakeLLMClient) is used in tests.
    """

    DEFAULT_MODEL = "gpt-4o-mini"
    MAX_RETRIES = 3

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        if not _OPENAI_AVAILABLE:
            raise LLMError("openai package not installed; pip install openai>=1.40")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY not set")
        self.model = model or self.DEFAULT_MODEL
        self._client = OpenAI(api_key=key)

    # ---- Public API ----------------------------------------------------

    def complete_with_tools(self, messages, tools):
        """Ask the LLM; it may respond with text OR a tool call."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        resp = self._call_with_retries(self._client.chat.completions.create, **kwargs)
        return self._parse_chat_response(resp)

    def complete_json(self, messages, schema_hint: str = "{}"):
        """Ask the LLM; force a JSON object matching the hint."""
        sys_msg = {
            "role": "system",
            "content": (
                "You MUST respond with a single JSON object, no prose, no markdown fences.\n"
                f"Match this shape: {schema_hint}"
            ),
        }
        all_msgs = [sys_msg, *messages]
        kwargs = dict(
            model=self.model,
            messages=all_msgs,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        resp = self._call_with_retries(self._client.chat.completions.create, **kwargs)
        raw_text = resp.choices[0].message.content or ""
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned non-JSON: {raw_text[:200]}") from exc

    # ---- Internals -----------------------------------------------------

    def _call_with_retries(self, fn, **kwargs):
        last_exc = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return fn(**kwargs)
            except Exception as exc:  # openai raises many types
                last_exc = exc
                time.sleep(2 ** attempt)
        raise LLMError(f"OpenAI call failed after {self.MAX_RETRIES} attempts: {last_exc}")

    def _parse_chat_response(self, resp) -> LLMResponse:
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            raw_args = tc.function.arguments
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError as exc:
                raise LLMError(f"Tool call args not JSON: {raw_args!r}") from exc
            return LLMResponse(tool_call=ToolCall(name=tc.function.name, arguments=args), raw=resp)
        return LLMResponse(text=msg.content or "", raw=resp)