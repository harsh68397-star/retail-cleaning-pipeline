"""Tests for the CleaningAgent.

All tests use ``FakeLLMClient`` so no real API key is required.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent import AgentReport, CleaningAgent, MAX_TURNS
from src.llm_client import LLMResponse, LLMError, ToolCall
from tests.fixtures.fake_llm import FakeLLMClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def before_profile() -> dict:
    return {"rows": 26, "missing_pct": 7.14, "cols": ["order_id", "quantity"]}


@pytest.fixture
def after_profile() -> dict:
    return {"rows": 24, "missing_pct": 6.39, "cols": ["order_id", "quantity"]}


@pytest.fixture
def final_json_payload() -> dict:
    return {
        "headline": "Cleaning removed 2 duplicate rows.",
        "what_went_well": ["Dates normalized.", "Outliers flagged not dropped."],
        "concerns": ["One price outlier still in data."],
        "suggested_rules": [
            {
                "column": "quantity",
                "kind": "value_range",
                "params": {"min_value": 1, "max_value": 1000},
                "rationale": "Current schema allows any int.",
            }
        ],
        "sample_explanation": "Order #14 had its date parsed to ISO.",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_agent_produces_report_on_happy_path(before_profile, after_profile, final_json_payload):
    """Agent asks one question via tool, then emits final JSON."""
    script = [
        FakeLLMClient.scripted_tool_call("read_quality_report"),
    ]
    fake = FakeLLMClient(script=script, final_json=final_json_payload)
    agent = CleaningAgent(llm_client=fake)

    report = agent.audit(before_profile, after_profile)

    assert isinstance(report, AgentReport)
    assert report.headline == "Cleaning removed 2 duplicate rows."
    assert "Dates normalized." in report.what_went_well
    assert report.used_fallback is False
    assert report.turns >= 2  # at least tool-call turn + final JSON turn


def test_agent_records_suggested_rule_from_tool(before_profile, after_profile, final_json_payload):
    """Rules proposed via the suggest_rule tool show up in the final report."""
    script = [
        FakeLLMClient.scripted_tool_call(
            "suggest_rule",
            column="customer_email",
            kind="str_regex",
            params={"pattern": "^[^@]+@[^@]+\\.[a-z]{2,}$"},
            rationale="TLD length check.",
        ),
        FakeLLMClient.scripted_text("Now summarize."),
    ]
    fake = FakeLLMClient(script=script, final_json=final_json_payload)
    agent = CleaningAgent(llm_client=fake)

    report = agent.audit(before_profile, after_profile)

    assert len(report.suggested_rules) >= 2  # 1 from tool + 1 from final JSON
    rule_cols = {r["column"] for r in report.suggested_rules}
    assert "customer_email" in rule_cols
    assert "quantity" in rule_cols


def test_agent_handles_malformed_json_gracefully(before_profile, after_profile):
    """If the final JSON call fails, agent returns the static fallback."""
    class BadJSONClient(FakeLLMClient):
        def complete_json(self, messages, schema_hint="{}"):
            raise LLMError("simulated bad JSON")

    fake = BadJSONClient(script=[], final_json={})
    agent = CleaningAgent(llm_client=fake)

    report = agent.audit(before_profile, after_profile)
    assert report.used_fallback is True
    assert "Static fallback" in report.concerns[0]


def test_agent_without_api_key_returns_fallback(before_profile, after_profile):
    """When no llm_client is passed, agent returns a static report."""
    agent = CleaningAgent(llm_client=None)
    report = agent.audit(before_profile, after_profile)
    assert report.used_fallback is True
    assert "26 -> 24" in report.headline or "missing-cell" in report.headline


def test_agent_handles_unknown_tool(before_profile, after_profile, final_json_payload):
    """Agent recovers gracefully when LLM invents a tool name."""
    script = [
        FakeLLMClient.scripted_tool_call("teleport"),
    ]
    fake = FakeLLMClient(script=script, final_json=final_json_payload)
    agent = CleaningAgent(llm_client=fake)
    report = agent.audit(before_profile, after_profile)
    # Should still produce a final report, not crash
    assert report.headline == final_json_payload["headline"]


def test_agent_respects_max_turns(before_profile, after_profile, final_json_payload):
    """If the LLM keeps calling tools, agent gives up after MAX_TURNS."""
    script = [FakeLLMClient.scripted_tool_call("read_quality_report")] * (MAX_TURNS + 5)
    fake = FakeLLMClient(script=script, final_json=final_json_payload)
    agent = CleaningAgent(llm_client=fake)
    report = agent.audit(before_profile, after_profile)
    # Either falls back or returns final; both are acceptable
    assert isinstance(report, AgentReport)
    assert report.turns <= MAX_TURNS


def test_agent_report_to_markdown(final_json_payload):
    """AgentReport.to_markdown produces a clean markdown string."""
    report = AgentReport(
        headline=final_json_payload["headline"],
        what_went_well=final_json_payload["what_went_well"],
        concerns=final_json_payload["concerns"],
        suggested_rules=final_json_payload["suggested_rules"],
        sample_explanation=final_json_payload["sample_explanation"],
        turns=3,
    )
    md = report.to_markdown()
    assert "# Agent Audit" in md
    assert "Dates normalized." in md
    assert "One price outlier still in data." in md
    assert "value_range" in md
    assert "Order #14 had its date parsed to ISO." in md


def test_agent_includes_sample_explanation(before_profile, after_profile, final_json_payload):
    """When a sample row is provided, it goes into the user message."""
    sample = {"order_id": 14, "order_date_raw": "15/03/2024", "unit_price_raw": "$12.99M"}
    fake = FakeLLMClient(script=[], final_json=final_json_payload)
    agent = CleaningAgent(llm_client=fake)
    agent.audit(before_profile, after_profile, sample_row=sample)
    # The sample should appear in the messages the LLM saw
    all_messages = [m for log in fake.messages_log for m in log]
    flat = json.dumps(all_messages, default=str)
    assert "15/03/2024" in flat
    assert "$12.99M" in flat