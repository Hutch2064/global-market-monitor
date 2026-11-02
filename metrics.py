"""Calculations for observations in a single instrument's native units."""
from datetime import date, timedelta
from math import isfinite, sqrt
from statistics import stdev
import calendar


def shift_months(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def calculate(observations):
    """Take (ISO date, value) pairs; return close-based history statistics.

    A percentage is undefined when either endpoint is non-positive.  Volatility
    uses consecutive valid observations, annualized using 252 trading days.
    """
    by_day = {}
    for day, value in observations:
        if value is not None and isfinite(float(value)):
            by_day[date.fromisoformat(day)] = float(value)
    rows = sorted(by_day.items())
    keys = ('latest', 'date', 'high52', 'low52', '1d', '5d', '1mo', '3mo', '6mo', '12mo', 'ytd', 'all', 'volatility')
    result = dict.fromkeys(keys)
    if not rows:
        return result
    today, latest = rows[-1]
    result.update(latest=latest, date=today.isoformat())

    def percent(old):
        return (latest / old - 1) * 100 if old is not None and old > 0 and latest > 0 else None

    for n in (1, 5):
        result[f'{n}d'] = percent(rows[-n - 1][1]) if len(rows) > n else None
    for months in (1, 3, 6, 12):
        boundary = shift_months(today, months)
        previous = [value for day, value in rows if day <= boundary]
        result[f'{months}mo'] = percent(previous[-1] if previous else None)
    prior_year = [value for day, value in rows if day < date(today.year, 1, 1)]
    result['ytd'] = percent(prior_year[-1] if prior_year else None)
    result['all'] = percent(rows[0][1])
    cutoff = today - timedelta(days=364)
    if rows[0][0] <= cutoff:
        window = [value for day, value in rows if cutoff <= day <= today]
        result['high52'], result['low52'] = max(window), min(window)
    changes = [b / a - 1 for (_, a), (_, b) in zip(rows, rows[1:]) if a > 0 and b > 0]
    if len(changes) >= 2:
        result['volatility'] = stdev(changes) * sqrt(252) * 100
    return result
