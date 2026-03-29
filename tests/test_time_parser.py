"""Tests for brimley.utils.time_parser (B09-S3)."""

from __future__ import annotations

import pytest

from brimley.utils.time_parser import RetryIntervalConfig, parse_duration, parse_retry_interval


# ---------------------------------------------------------------------------
# parse_duration — valid inputs
# ---------------------------------------------------------------------------


class TestParseDurationValid:
    def test_seconds_only(self) -> None:
        assert parse_duration("30s") == 30.0

    def test_minutes_only(self) -> None:
        assert parse_duration("5m") == 300.0

    def test_hours_only(self) -> None:
        assert parse_duration("1h") == 3600.0

    def test_milliseconds_only(self) -> None:
        assert parse_duration("500ms") == 0.5

    def test_one_ms(self) -> None:
        assert parse_duration("1ms") == 0.001

    def test_hours_and_minutes(self) -> None:
        assert parse_duration("1h 30m") == 5400.0

    def test_hours_minutes_seconds(self) -> None:
        assert parse_duration("1h 30m 15s") == 5415.0

    def test_hours_minutes_seconds_millis(self) -> None:
        assert parse_duration("1h 30m 15s 500ms") == pytest.approx(5415.5)

    def test_zero_seconds(self) -> None:
        assert parse_duration("0s") == 0.0

    def test_one_second(self) -> None:
        assert parse_duration("1s") == 1.0

    def test_whitespace_variants(self) -> None:
        # Units separated by varying whitespace
        assert parse_duration("1h  30m  15s") == 5415.0

    def test_decimal_seconds(self) -> None:
        assert parse_duration("1.5s") == 1.5

    def test_decimal_minutes(self) -> None:
        assert parse_duration("0.5m") == 30.0

    def test_large_millis(self) -> None:
        assert parse_duration("1000ms") == 1.0

    def test_exact_one_minute(self) -> None:
        assert parse_duration("60s") == 60.0


# ---------------------------------------------------------------------------
# parse_duration — error inputs
# ---------------------------------------------------------------------------


class TestParseDurationErrors:
    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            parse_duration("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            parse_duration("   ")

    def test_unknown_unit(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_duration("5x")

    def test_plain_number(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_duration("30")

    def test_letters_only(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_duration("abc")

    def test_duplicate_unit(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            parse_duration("1s 2s")


# ---------------------------------------------------------------------------
# parse_retry_interval — valid inputs
# ---------------------------------------------------------------------------


class TestParseRetryIntervalValid:
    def test_fixed_seconds(self) -> None:
        result = parse_retry_interval("10s")
        assert result == RetryIntervalConfig(base=10.0, strategy="fixed")

    def test_exponential_suffix(self) -> None:
        result = parse_retry_interval("10s exponential")
        assert result == RetryIntervalConfig(base=10.0, strategy="exponential")

    def test_exponential_short(self) -> None:
        result = parse_retry_interval("10s ex")
        assert result == RetryIntervalConfig(base=10.0, strategy="exponential")

    def test_exponential_case_insensitive(self) -> None:
        result = parse_retry_interval("10s EXPONENTIAL")
        assert result == RetryIntervalConfig(base=10.0, strategy="exponential")

    def test_multiplier(self) -> None:
        result = parse_retry_interval("10s x1.5")
        assert result == RetryIntervalConfig(base=10.0, strategy="multiplier", factor=1.5)

    def test_multiplier_integer(self) -> None:
        result = parse_retry_interval("10s x2")
        assert result == RetryIntervalConfig(base=10.0, strategy="multiplier", factor=2.0)

    def test_base_millis(self) -> None:
        result = parse_retry_interval("500ms")
        assert result == RetryIntervalConfig(base=0.5, strategy="fixed")

    def test_base_minutes(self) -> None:
        result = parse_retry_interval("1m exponential")
        assert result == RetryIntervalConfig(base=60.0, strategy="exponential")

    def test_base_complex(self) -> None:
        result = parse_retry_interval("1h 30m")
        assert result == RetryIntervalConfig(base=5400.0, strategy="fixed")

    def test_zero_base_fixed(self) -> None:
        result = parse_retry_interval("0s")
        assert result == RetryIntervalConfig(base=0.0, strategy="fixed")


# ---------------------------------------------------------------------------
# parse_retry_interval — error inputs
# ---------------------------------------------------------------------------


class TestParseRetryIntervalErrors:
    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            parse_retry_interval("")

    def test_unknown_suffix(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_retry_interval("10s linear")

    def test_plain_number(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_retry_interval("10")

    def test_invalid_multiplier_zero(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            parse_retry_interval("10s x0")
