"""A股 board / segment classification by code prefix.

Single source of truth for grouping stocks into the buckets the screener
filter exposes:

    - ``main_sh``  沪市主板  (600 / 601 / 603 / 605)
    - ``main_sz``  深市主板  (000 / 001 / 002 / 003) — 002/003 was 中小板,
                              merged into 主板 in 2021-04
    - ``chinext``  创业板    (300 / 301)
    - ``star``     科创板    (688 / 689 含 CDR)
    - ``bse``      北交所    (43xxxx / 8xxxxx / 92xxxx)

ST/*ST is an *overlay* dimension (any board can be ST), so it is gated by
``is_st(name)`` rather than being a board itself.
"""

from typing import Literal

MarketSegment = Literal["main_sh", "main_sz", "chinext", "star", "bse"]

ALL_SEGMENTS: tuple[MarketSegment, ...] = (
    "main_sh",
    "main_sz",
    "chinext",
    "star",
    "bse",
)


def classify_market(code: str) -> MarketSegment | None:
    """Return the board segment for ``code``, or ``None`` if unrecognised."""
    if not code:
        return None
    c = code.strip()
    if c.startswith(("600", "601", "603", "605")):
        return "main_sh"
    if c.startswith(("000", "001", "002", "003")):
        return "main_sz"
    if c.startswith(("300", "301")):
        return "chinext"
    if c.startswith(("688", "689")):
        return "star"
    # 北交所: 43xxxx (老三板转板), 8xxxxx, 92xxxx (2023+ 新发)
    if c.startswith(("4", "8", "92")):
        return "bse"
    return None


def is_st(name: str | None) -> bool:
    """Return True if ``name`` is an ST / *ST stock."""
    if not name:
        return False
    n = name.strip().upper().replace(" ", "")
    return n.startswith("ST") or n.startswith("*ST")


def passes_market_filter(
    code: str,
    name: str | None,
    markets: list[str] | None,
    include_st: bool,
) -> bool:
    """Apply the (markets, include_st) gate to a (code, name) pair.

    - ``markets`` is None or empty → all 5 boards allowed.
    - ``include_st`` False → reject ST/*ST regardless of board.
    - Codes that don't classify into any known segment are rejected.
    """
    if is_st(name) and not include_st:
        return False
    segment = classify_market(code)
    if segment is None:
        return False
    if markets:
        return segment in markets
    return True
