"""
Pure tests for app.modules.rewards.service._period_bounds — the
month-boundary logic behind reward eligibility queries.
"""
from datetime import datetime

import pytest

from app.core.errors import AppError
from app.modules.rewards.service import _period_bounds


def test_mid_year_month_bounds():
    start, end = _period_bounds("2026-03")
    assert start == datetime(2026, 3, 1)
    assert end == datetime(2026, 4, 1)


def test_december_rolls_over_to_next_year():
    start, end = _period_bounds("2026-12")
    assert start == datetime(2026, 12, 1)
    assert end == datetime(2027, 1, 1)


def test_january_bounds():
    start, end = _period_bounds("2026-01")
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2026, 2, 1)


def test_malformed_period_is_rejected():
    with pytest.raises(AppError) as exc_info:
        _period_bounds("not-a-period")
    assert exc_info.value.error_code == "INVALID_PERIOD"


def test_out_of_range_month_is_rejected():
    with pytest.raises(AppError) as exc_info:
        _period_bounds("2026-13")
    assert exc_info.value.error_code == "INVALID_PERIOD"
