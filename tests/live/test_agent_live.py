"""Live integration test for the agent.

Skipped unless ``RUN_LIVE_LLM=1`` is set in the environment AND a real
``OPENAI_API_KEY`` is available. This test calls the real OpenAI API and
incurs a small cost (~$0.01 per run with gpt-4o-mini).
"""
from __future__ import annotations

import os

import pytest

from src.agent import CleaningAgent
from src.llm_client import LLMClient, LLMError


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM") != "1",
    reason="set RUN_LIVE_LLM=1 to enable live LLM tests",
)


def _try_real_client():
    try:
        return LLMClient()
    except LLMError as exc:
        pytest.skip(f"OPENAI_API_KEY not available: {exc}")


@pytest.mark.live
def test_live_audit_produces_report():
    """Run the agent against a tiny synthetic dataset and verify the shape."""
    client = _try_real_client()
    agent = CleaningAgent(llm_client=client)

    before = {"rows": 26, "missing_pct": 7.14, "cols": ["order_id", "quantity", "unit_price"]}
    after = {"rows": 24, "missing_pct": 6.39, "cols": ["order_id", "quantity", "unit_price"]}
    sample = {"order_id": 14, "order_date": "2024-03-15", "unit_price": 12.99}

    report = agent.audit(before, after, sample_row=sample)

    assert report.headline, "headline must not be empty"
    assert isinstance(report.what_went_well, list)
    assert isinstance(report.concerns, list)
    assert isinstance(report.suggested_rules, list)
    assert report.used_fallback is False
    assert report.turns >= 1