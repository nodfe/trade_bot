"""Lightweight 5-field cron expression matcher (min hour dom month dow).

Supported features:
- ``*`` wildcard
- comma lists: ``1,15,30``
- ranges: ``1-5``
- step values: ``*/5``, ``0-30/5``
- numeric fields only

Day-of-week: 0=Sunday, 6=Saturday (POSIX convention; ``7`` also accepted as
Sunday for compatibility).

This is intentionally minimal — it covers the schedules we expose to users
through the strategy subscription API (e.g. ``"30 9 * * 1"`` for Monday
09:30) without pulling in a heavyweight cron library.
"""

from __future__ import annotations

from datetime import datetime

_FIELD_RANGES = [
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day-of-month
    (1, 12),  # month
    (0, 6),  # day-of-week
]


class CronParseError(ValueError):
    pass


def _parse_field(token: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in token.split(","):
        if not part:
            raise CronParseError(f"empty cron part in {token!r}")
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError as exc:
                raise CronParseError(f"invalid step in {part!r}") from exc
            if step <= 0:
                raise CronParseError(f"step must be positive in {part!r}")
        else:
            base = part

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError as exc:
                raise CronParseError(f"invalid range {base!r}") from exc
        else:
            try:
                start = int(base)
            except ValueError as exc:
                raise CronParseError(f"invalid value {base!r}") from exc
            end = start

        if start > end:
            raise CronParseError(f"start > end in {base!r}")
        for v in range(start, end + 1, step):
            if v < lo or v > hi:
                # day-of-week=7 means Sunday — normalize.
                if (lo, hi) == (0, 6) and v == 7:
                    out.add(0)
                    continue
                raise CronParseError(f"value {v} out of range [{lo},{hi}] in {token!r}")
            out.add(v)
    return out


def parse_cron(expr: str) -> list[set[int]]:
    """Parse a 5-field cron expression into per-field allowed value sets."""
    parts = expr.strip().split()
    # Accept 6-field (with seconds) by dropping the seconds field.
    if len(parts) == 6:
        parts = parts[1:]
    if len(parts) != 5:
        raise CronParseError(f"cron must have 5 (or 6) space-separated fields, got {len(parts)}")
    fields: list[set[int]] = []
    for token, (lo, hi) in zip(parts, _FIELD_RANGES, strict=True):
        fields.append(_parse_field(token, lo, hi))
    return fields


def cron_matches(expr: str, when: datetime) -> bool:
    """Return True if ``when`` matches the cron expression (minute-precision)."""
    fields = parse_cron(expr)
    minute_ok = when.minute in fields[0]
    hour_ok = when.hour in fields[1]
    dom_ok = when.day in fields[2]
    month_ok = when.month in fields[3]
    # Python's weekday(): Mon=0..Sun=6. POSIX cron: Sun=0..Sat=6.
    py_dow = when.weekday()
    cron_dow = (py_dow + 1) % 7  # Mon -> 1, Sun -> 0
    dow_ok = cron_dow in fields[4]
    return minute_ok and hour_ok and dom_ok and month_ok and dow_ok


def is_due(
    expr: str,
    *,
    now: datetime,
    last_dispatched_at: datetime | None,
    grace_minutes: int = 5,
) -> bool:
    """Whether a job should fire at ``now``.

    The dispatcher beat runs every ``grace_minutes`` minutes; we walk back
    that many minutes (inclusive) and fire if the cron matched any of those
    minutes AND we have not dispatched since that match.
    """
    from datetime import timedelta

    for delta_min in range(0, grace_minutes + 1):
        candidate = now - timedelta(minutes=delta_min)
        # Truncate seconds for matching.
        candidate = candidate.replace(second=0, microsecond=0)
        if cron_matches(expr, candidate):
            if last_dispatched_at is None or last_dispatched_at < candidate:
                return True
    return False
