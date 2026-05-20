# ABOUTME: Tests for usage.py — pricing entries resolve and CallRecord costs compute correctly.

"""Tests for usage tracking pricing entries (no API calls)."""

from simmer_sdk.usage import PRICING, CallRecord, UsageTracker


# ---------------------------------------------------------------------------
# Gemini pricing entries
# ---------------------------------------------------------------------------


def test_gemini_3_5_flash_pricing_resolves():
    """The model we use in the smoke + DnD + orrery scripts must price correctly."""
    assert "gemini-3.5-flash" in PRICING
    input_rate, output_rate = PRICING["gemini-3.5-flash"]
    assert input_rate == 1.50
    assert output_rate == 9.00


def test_gemini_flash_latest_alias_pricing_matches():
    """Alias should match the model it points to."""
    assert PRICING["gemini-flash-latest"] == PRICING["gemini-3.5-flash"]


def test_gemini_2_5_models_priced():
    assert "gemini-2.5-flash" in PRICING
    assert "gemini-2.5-pro" in PRICING


def test_call_record_gemini_cost_computation():
    """1M output tokens at $9 should cost $9; verify the math."""
    rec = CallRecord(
        model="gemini-3.5-flash",
        role="judge",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    # $1.50 in + $9.00 out = $10.50
    assert round(rec.estimated_cost, 4) == 10.50


def test_call_record_thoughts_already_in_output_tokens():
    """Reminder: the adapter rolls thoughtsTokenCount into output_tokens before
    creating the CallRecord, so the cost calculation here just multiplies."""
    rec = CallRecord(
        model="gemini-3.5-flash",
        role="judge",
        input_tokens=100,
        output_tokens=10_000,  # e.g. 500 candidates + 9500 thoughts
    )
    expected = (100 / 1_000_000) * 1.50 + (10_000 / 1_000_000) * 9.00
    assert round(rec.estimated_cost, 6) == round(expected, 6)


def test_unknown_gemini_model_zero_cost():
    """Models not in PRICING return $0 (don't crash); matches existing behavior."""
    rec = CallRecord(model="gemini-9-future", role="judge",
                     input_tokens=1000, output_tokens=1000)
    assert rec.estimated_cost == 0.0


def test_usage_tracker_aggregates_gemini_costs():
    tracker = UsageTracker()
    tracker.record_tokens("gemini-3.5-flash", "judge", 1000, 5000)
    tracker.record_tokens("gemini-3.5-flash", "generator", 500, 2000)
    by_role = tracker.by_role()
    assert by_role["judge"]["calls"] == 1
    assert by_role["generator"]["calls"] == 1
    assert tracker.total_cost > 0
