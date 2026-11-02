from datetime import date, timedelta
import math
import pytest
from metrics import calculate, shift_months


def test_horizons_and_full_history_volatility():
    rows = [('2025-12-31', 100), ('2026-01-02', 110), ('2026-01-05', 99)]
    result = calculate(rows)
    assert result['1d'] == pytest.approx(-10)
    assert result['ytd'] == pytest.approx(-1)
    assert result['all'] == pytest.approx(-1)
    assert result['5d'] is None
    assert result['volatility'] == pytest.approx(math.sqrt(0.02) * math.sqrt(252) * 100)


def test_calendar_end_and_missing_boundary():
    assert shift_months(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert calculate([('2026-02-03', 20), ('2026-03-01', 22)])['1mo'] is None


def test_full_year_extremes_and_nonpositive_baselines():
    result = calculate([('2025-01-01', 1), ('2025-10-01', 5), ('2025-12-31', -1)])
    assert result['high52'] == 5
    assert result['low52'] == -1
    assert result['all'] is None
    assert result['1d'] is None
    assert calculate([('2026-01-01', 1)])['high52'] is None
