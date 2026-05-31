# Algorithm review: limit-up strategies

Scope: read-only review of `first_limit_up_low`, `leader_streak`, and `zt_relay`
as added to `_match_screen` / `_sort_screen_matches` in
`backend/app/modules/market_data/service.py`, plus the supporting field
derivations in `_derive_limit_up_fields` (live) and `PrecomputedScreenSeries`
(walk-forward backtest).

All file/line citations are from the working tree at the time of review.

---

## TL;DR

- **first_limit_up_low** — Warning. Logic is roughly right but the "low base"
  uses **closing-price 60d high** instead of intraday high, the "quiet" check
  ignores 大涨 (non-zt big-up days), and there is no resumption / 新股
  filtering. Default `0.85` cap is sensible but easily defeated by a tail of
  flat closes.
- **leader_streak** — Warning. `streak ≥ 2` is **not** what 龙头 means in
  practice (a 2 连板 is just "二板"); there is no relative-leadership check
  vs sector peers, and the displayed reason ("已连板 N 天，量比 X 配合") will
  confidently mis-label any 二板 as 龙头. Otherwise the indicators it
  consumes are correct.
- **zt_relay** — Flawed (semantic). Acknowledged in the code: cannot inspect
  yesterday's streak length, so `max_streak` is a no-op. Worse, it triggers on
  *every* T+1 after any prior limit-up regardless of whether yesterday was the
  streak's first board or its tenth — which inverts the very risk the
  parameter exists to manage.

Field derivation and live↔precompute parity are mostly clean, with two
non-trivial divergences worth fixing (60d-window edge case; threshold
tolerance comment vs reality) and one missing-asset class hazard (ST ±5%).

---

## Strategy: first_limit_up_low

### What it should do

Common 中国 A 股 retail definition of "低位首板":
1. Stock just printed its **first** limit-up after a long quiet stretch
   (typically 30–60 trading days with no zt and no large >7% rallies).
2. Price is at a **low base** — i.e. close is well below the recent ~3–6 month
   intraday high (commonly ≤ 70–80% of 60-day high).
3. Today's volume confirms (量能温和放大, not exhausting).
4. Optional: ex-ST, ex-新股 (typically need ≥ 60 trading days of history),
   not in halt-resumption, not gap-down to ZT (一字板 unfilled).

The play is to enter at close T0 (or T+1 open) anticipating second-board
follow-through.

### What the code does

`service.py:861–885` — match logic:
- Requires `analysis.is_limit_up_today` (`service.py:863`).
- Requires `days_since_last_limit_up >= min_quiet_days` (default 20) **or**
  `None` (no prior zt in the 60-bar window) — `service.py:865–874`.
- Requires `high_60d_ratio <= max_high_60d_ratio` (default 0.85) —
  `service.py:875–884`.

Sort: `service.py:984–992` — primary key `-return_5d_pct` (less prior bounce
first), secondary `-volume_ratio_5d`.

Default params: `catalog.py:50–56` — `min_quiet_days=20`,
`max_high_60d_ratio=0.85`.

### Issues found

**Major — 60d high uses closes, not highs** (`service.py:471–473`,
`service.py:1313–1315`). Both `_derive_limit_up_fields` and
`PrecomputedScreenSeries.build` compute `high_60d_ratio` as
`latest_close / max(close[-60:])`. Real 60d high is the max **intraday high**,
so the denominator here is systematically lower than what a trader sees on a
chart. Effect: stocks that touched a high but pulled back to close lower will
look closer to their "60d high" than they really are, biasing the gate
against marginal candidates. Tighter than the trader expects.

**Major — only the 60-bar fetch window is consulted** (`service.py:201–204`).
The live path fetches at most 60 bars, so `bars[-60:]` is just `bars`. There
is no actual look-back beyond 60 sessions; in particular `min_quiet_days=20`
caps out at "20 days" but `min_quiet_days=80` silently degrades to ~"≤ 60
days". `_derive_limit_up_fields` returns `days_since=None` whenever no zt is
visible, and `_match_screen` treats `None` as "fresh enough" — this is fine
for the default but quietly ceilinged.

**Major — "quiet" only excludes prior limit-ups, not 大涨**. A common abuse
case: a stock rallies 9.7% (one tick under threshold) day after day — under
this definition it remains "quiet" indefinitely. Real 低位首板 strategies
also exclude any single bar with `pct_change_1d >= ~7%` in the look-back.

**Major — no 新股 / 复牌 / ST filter**. Three concrete failure modes:
- 新股 with < 60 sessions: `high_60d_ratio` is computed against whatever
  history exists (live: `bars[-60:] if n >= 60 else bars`; precomputed:
  `min_periods=5`). A stock that listed two weeks ago and just printed its
  second 首日 zt can match. (See line 471 and 1314.)
- 复牌 (long suspension): the trade-date gap is invisible to the screener
  because the bar list is dense over *trading* dates only. A stock halted for
  6 months and resuming with a zt will appear to have a "perfect quiet 60d
  base" — false positive.
- ST stocks: limit threshold is ±5%, but `_limit_up_threshold_pct` returns
  9.8 (`service.py:407–414`). An ST stock at +5% will *not* be flagged as zt
  (false negative), and an ST stock at +9.8% would be flagged but can't
  legally have happened — so this is a quiet false-negative, not a false-
  positive.

**Minor — 0.85 default is permissive**. With closes-based 60d high (which
already runs lower than intraday high), 0.85 will admit stocks within ~10%
of their absolute high — not what most traders mean by "low base" (typical
threshold is 0.7–0.75 against intraday high, equivalent to ~0.65–0.7 against
closes).

**Minor — sort key contradicts docstring**. The comment at
`service.py:985` claims "Lowest 60d-high ratio first (most depressed) then
highest volume." but the actual key
(`service.py:988–991`) is `(-return_5d_pct, -volume_ratio_5d)` — it sorts by
*5-day return* descending, not by `high_60d_ratio` ascending. Two stocks both
passing the 0.85 gate will be ranked by which one has bounced more in the
last 5 days, the opposite of the stated intent.

**Minor — `is_limit_up_candidate` not aligned**. `is_limit_up_candidate` on
`StockScreenItemOut` (`schemas.py:95`) is set from a separate
`limit_up_item` lookup (`service.py:393`) rather than from
`analysis.is_limit_up_today`. For this strategy in particular, both should
agree by construction; if they don't, the upstream `limit_up` table is the
ground truth and the derived flag is decorative — worth flagging in the UI
contract.

### Recommended fixes (description only — do not implement)

1. Switch `high_60d_ratio` to use bar.high (intraday) for the rolling max,
   in both `_derive_limit_up_fields` (`service.py:472`) and
   `PrecomputedScreenSeries.build` (`service.py:1314`). Keep the divisor in
   `closes[-1]`. Reset default `max_high_60d_ratio` to ~0.75.
2. Add a "no big-up day in look-back" guard in addition to "no zt": e.g.
   `max(pct_change in look-back excluding today) < 7`.
3. Pass through a longer fetch window (e.g. 80–120 bars) when the strategy
   needs `min_quiet_days > 30`, or refuse silently-clipped values.
4. Filter ST names and stocks with `n_bars < min_quiet_days + 5` (新股) at
   the candidate-list stage. ST detection requires the stock metadata
   (e.g., `name.startswith("ST") or name.startswith("*ST")`).
5. Detect 复牌 via the trade_date deltas: if the gap between the latest bar
   and the bar at the start of the quiet window spans > N calendar days for
   ≤ N trading days, treat as suspect.
6. Fix the sort key to actually rank by `high_60d_ratio` (most depressed
   first) — the data is on the analysis object but not surfaced on
   `StockScreenItemOut`; surfacing `high_60d_ratio` (and the streak length)
   on the screener item would also help the UI.

---

## Strategy: leader_streak

### What it should do

"龙头战法" requires three things absent from this implementation:
1. **Relative leadership** — the stock is the *highest* connected board in
   its 题材 / 板块 (sector). A 二板 in a sector with a 五板 leader is a
   follower, not the leader.
2. **A meaningful streak height** — typically `streak ≥ 3` (三连板) or higher
   to qualify as 龙头 candidate; `≥ 2` is just "二板", not 龙头.
3. **Strong demand confirmation** — sealed 封单 (limit-up bid stack) or
   minimal 炸板 events; volume should expand without exhaustion.

The trade is to ride the leading name as long as it keeps making higher
highs, exiting on first failure (断板).

### What the code does

`service.py:887–908`:
- `consec_limit_up_days >= min_streak` (default `min_streak=2` —
  `catalog.py:60–63`).
- `volume_ratio_5d >= min_volume_ratio` (default 1.2).
- `trend_bias == "bullish"`.
- Reason text labels the result as "龙头连板".

Sort: `service.py:994–1004` — `(return_5d_pct, volume_ratio_5d)` descending.

### Issues found

**Major — `min_streak=2` mis-labels 二板 as 龙头**. The product copy says
"已连板 N 天" which is technically accurate, but combined with the strategy
key `leader_streak` and the 龙头 tag (`catalog.py:59`) it will produce
hundreds of false positives on any active session — in 2024–2025 typical
sessions show dozens of 二板, of which only one or two are sector leaders.
Correct default is `min_streak >= 3`; even then, 龙头 status requires
relative-leadership check, not just absolute streak length.

**Major — no relative leadership / sector context**. The screener does not
look at peers' streaks. A stock could be "the only 二板" in a niche sector
(real 龙头 candidate) or "the 17th 二板 in a CPO craze" (definitively a
follower) — both score identically here. Industry is available on the
`Stock` row (`schemas.py:9`) and the `limit_up` table has `reason` (题材)
which would be the natural grouping key.

**Major — `volume_ratio_5d` on a zt day is a poor signal**. On a 一字板
(open-high-low-close all at limit, with sealed 封单), volume can collapse to
near zero (no sellers willing to part with shares); on a 烂板 (limit-up
that opened repeatedly), volume balloons. The current rule rewards the
*latter* (volume ratio ≥ 1.2 needed), which is the **weaker** of the two
patterns — exactly inverted. A real 龙头 filter wants either: (a) high
volume + strong close, OR (b) tiny volume + big sealed 封单 (一字板). The
former needs to bound 量比 below an exhaustion ceiling too (e.g. 1.2–4x).

**Minor — `trend_bias=="bullish"` is partially redundant**. A stock on a
2+ board streak almost certainly has price > MA5 and recent return > 0, so
this gate filters very few candidates; mostly it just suppresses post-
limit-down rebounds where a single zt happens to land near MA5. Acceptable,
but noisy.

**Minor — sort doesn't surface streak length**. Sort uses
`(return_5d_pct, volume_ratio_5d)` (`service.py:999–1003`). A 5 连板 will
typically have higher 5d return than a 2 连板, so this *roughly* surfaces
longer streaks first — but only as a side effect. Direct sort by
`consec_limit_up_days desc` would be more honest. The screener item type
does not currently expose `consec_limit_up_days`; the in-code comment at
`service.py:996` acknowledges this.

### Recommended fixes (description only)

1. Raise `min_streak` default to 3.
2. Surface `consec_limit_up_days` on `StockScreenItemOut` and use it as the
   primary sort key.
3. After the first-pass filter, group survivors by sector (industry or
   limit-up `reason`) and keep only the top-streak member per group; tie-
   break by sealed-volume / 封单 metric if available.
4. Add a 量比 upper bound (e.g. ≤ 4x) to exclude exhaustion / 烂板 cases.
5. Rename the user-facing label or split into "leader_streak" (with sector
   filter) vs "streak_followup" (any N+ board) — the current rule is
   really the latter.

---

## Strategy: zt_relay

### What it should do

"涨停接力" buys T+1 a stock that limit-up'd on T0, hoping for a second
board. Common gates:
1. T0 was a limit-up (often specifically the **first** board — 新晋首板接力).
2. T+1 opens with a small positive gap (commonly 0% < gap < ~3%); a too-
   large gap means chasers have already bid it up; a gap-down is a sell
   signal.
3. T+1 holds above prior close in the early session; volume confirms.
4. Cap the prior streak — late-stage relays (4 板 → 5 板) carry far worse
   risk-reward than early-stage (1 板 → 2 板).

### What the code does

`service.py:910–961`:
- `consec_limit_up_days is not None`.
- `is_limit_up_today` is False.
- `days_since_last_limit_up == 1` (i.e. yesterday was the most recent zt).
- `open_gap_pct <= max_open_gap_pct` (default 5.0 — `catalog.py:69`).
- `volume_ratio_5d >= min_volume_ratio` (default 1.0).
- `max_streak` parameter is **explicitly disabled** in the comment block at
  `service.py:931–939`.

Sort: `service.py:1006–1014` — `(volume_ratio_5d, return_20d_pct)` desc.

### Issues found

**Critical — `max_streak` is a no-op**. The code comment at
`service.py:931–939` acknowledges this: `consec_limit_up_days` on T+1 is
always 0 (today is not zt by precondition), and the current
`StockAnalysisSummaryOut` does not carry "consec_limit_up_days as of
yesterday". So a 9 连板 → break day → ZT-relay candidate looks identical to
a 1 连板 → break day candidate. This inverts the strategy's risk profile:
late-stage relays are exactly what `max_streak` was meant to exclude, and
they're the *most* likely to clear the rest of the gates (gap < 5% +
volume ≥ 1 — easy after a multi-board run).

This is fixable with the data already available in `PrecomputedScreenSeries`:
the precomputed path stores `consec_limit_up[i-1]` implicitly (one bar back
from `idx`). Surfacing `prior_streak_at_t_minus_1` on the analysis object
would close the gap. The live path would need a similar one-bar
look-behind in `_derive_limit_up_fields`.

**Major — gap default 5% is loose**. With `max_open_gap_pct=5.0`, a stock
that gaps +5% on T+1 already gives the relayer half of a typical
limit-up's headroom before they enter. Common settings are 0–3%. Worse,
there is no lower bound — a stock that gaps **down** (`open_gap_pct = -3%`)
will pass the `<= 5` gate, which is a counter-signal in 接力 trading.

**Major — `min_volume_ratio=1.0` is meaninglessly loose**. After a
limit-up, T+1 volume nearly always ≥ T0 (because T0 may have been low-
volume sealed 一字板); ratio 1.0 admits almost everything. Practical
thresholds are 1.5–2.0.

**Major — selects on T+1, not T+1 entry-fillable signal**. The screener
runs on the day's close (`as_of_date`-aligned). By T+1 close we already
know whether the relay worked; the strategy concept is specifically about
T+1 *intraday* decisions. The current implementation will only be useful
in walk-forward backtest if entry is modeled at T+2 open — confirm the
backtest engine treats it that way (out of scope of this review file).

**Minor — sort by `return_20d_pct` as secondary**. After volume ratio,
ranking by 20d return prefers stocks that have already run a lot, which
contradicts the spirit of "early relay only".

**Minor — does not exclude 一字板 T0**. A T0 一字板 (open=high=low=close at
zt) is structurally unfillable — there were no sellers; the relay
candidate effectively never had retail entry on T0. Detecting this
requires `bar.open == bar.high == bar.low == bar.close` on the prior bar,
which is not surfaced.

### Recommended fixes (description only)

1. Add `prior_consec_limit_up_days` (the streak as of the most recent zt
   bar) to `StockAnalysisSummaryOut`. In `PrecomputedScreenSeries`, this is
   `consec[idx - 1]` when `days_since_last_zt[idx] == 1`. In the live path,
   it is `streak_through_bars[:-1]`. Then `max_streak` becomes meaningful.
2. Tighten gap gate to `0 <= open_gap_pct <= max_open_gap_pct` (default
   ~3); reject gap-downs explicitly.
3. Raise default `min_volume_ratio` to 1.5+.
4. Add a 一字板-on-T0 exclusion using prior bar's open/high/low/close
   equality.
5. Rename strategy or add a `relay_phase` param ("first_board_relay" vs
   "any_relay") to make the streak constraint explicit in the UI.

---

## Field derivation (shared)

Two implementations: live (`_derive_limit_up_fields`, `service.py:416–488`)
and precomputed (`PrecomputedScreenSeries`, `service.py:1236–1436`). Both
must agree, since the live screener and walk-forward backtester compare
against each other.

### Threshold logic

Live `_limit_up_threshold_pct` (`service.py:407–414`) and precomputed
counterpart (`service.py:1266–1280`) are byte-identical:
- `300xxx` / `688xxx` / `8…` / `4…` → 19.8
- everything else → 9.8

**Issue — ST not handled (major)**. ST and *ST stocks have ±5% caps. They
will register as zt only if they happen to print +9.8% (legally
impossible). This is a silent false-negative for the entire ST universe.
Severity is bounded because ST names rarely match the bullish trend
biases anyway.

**Issue — exhaustiveness (minor)**. 北交所 (BSE) prefixes are matched as
`code.startswith(("8", "4"))`, which covers `8x` (BSE) and `43`/`83`
historical codes. Modern BSE codes are `83xxxx`, `87xxxx`, `92xxxx` — `92`
is **not** matched. Outdated 三板 (`400…`, `420…`) is matched but those
have different limits anyway.

**Issue — comment vs code mismatch (minor)**. The docstring at
`service.py:1271–1273` claims a 0.2 pct tolerance ("9.97% close still
counts"). Looking at the actual threshold value `9.8`, that's a 0.2 pct
*lower bound* under 10%, so the comment's intent is borne out. But the
real-world A-share zt is computed as `round(prev_close * 1.10, 2)`, which
on low-priced stocks (close ≈ 5.00) yields exact +10.00%, while on others
(close ≈ 5.05) yields +9.90%. The 9.8 threshold is wide enough to absorb
this rounding, **but it will also accept genuine non-zt 9.81% closes** as
zt. Acceptable approximation; flag for awareness.

### `is_zt` per bar

Both implementations use `chg >= threshold` with `prev_close > 0` guard:
- Live: `service.py:444–445`.
- Precomputed: `service.py:1349–1351` (via `pct_change(1) * 100`).

Both produce a `False` for index 0 (no prior close). Equivalent.

### Trailing streak (`consec_limit_up_days`)

- Live: `service.py:447–452` reverses `is_zt` and counts. O(n).
- Precomputed: `service.py:1352–1358` accumulates forward
  (`consec[i] = consec[i-1] + 1` if zt else 0). O(n) per code.

Both correctly handle 一字板 (a 一字板 still produces `pct_change_1d >= 9.8`
because today's close is +10% from prev_close — so it counts). Both reset
on the first non-zt going backward. **Equivalent.**

### `days_since_last_limit_up` — off-by-one

- Live: `service.py:456–464` — `range(n-2, -1, -1)`, i.e. start at the
  bar **before** the latest. Critically, today's own zt does **not**
  consume the slot. `days_since = (n-1) - last_zt_idx`, so the value is
  the number of trading sessions between today and the last prior zt
  (1 means yesterday).
- Precomputed: `service.py:1360–1368` — accumulates forward, then
  `days_since[i] = i - last_zt_idx` *before* updating
  `last_zt_idx = i if is_zt[i]`. This means if today is itself a zt,
  `days_since[i]` reflects the previous zt's gap — **same semantics as
  the live path**.

**Both agree** that today's zt does not zero out `days_since`. Good. This
is critical for `first_limit_up_low` ("days since prior board").

### `open_gap_pct`

- Live: `service.py:466–469` — `(today.open - bars[-2].close) /
  bars[-2].close * 100`.
- Precomputed: `service.py:1318–1320` — `(open - close.shift(1)) /
  close.shift(1) * 100`.

Equivalent. Both produce `None` / NaN for the first bar.

### `high_60d_ratio` — divergence

- Live: `service.py:471–473`. Window is `bars[-60:]` (or all of `bars` if
  `n < 60`). Uses **close**.
- Precomputed: `service.py:1313–1315` —
  `rolling(window=60, min_periods=5).max()`. Uses **close**.

**Issue — `min_periods` divergence (major)**. The live path always
computes a value as long as `n >= 1`, using whatever bars exist. The
precomputed path requires at least 5 bars for a value. So:
- For `n == 4`, live returns a ratio, precomputed returns None.
- For `5 <= n < 60`, both work but operate on different effective
  windows (live: all bars; precomputed: same — `rolling(60)` with
  `min_periods=5` consumes whatever's in the window). Equivalent for
  this range.
- For `n >= 60`, both look at the trailing 60 — equivalent.

So the actual disagreement is only at `n in {1..4}`, where the live path
produces a ratio that should not be trusted anyway. Cosmetic.

**Issue — close vs intraday high (major; see first_limit_up_low above)**.
Both implementations use closes; should use highs.

### `pct_change_1d`

- Live: `service.py:474–480`.
- Precomputed: `service.py:1305` (`pct_change(1) * 100`).

Equivalent.

### `volume_ratio_5d`

- Live `get_stock_analysis_summary`: `service.py:232–233` —
  `latest / mean(volumes[-6:-1])`. Excludes today.
- Precomputed: `service.py:1309–1311` —
  `vol / shift(1).rolling(5).mean()`. Also excludes today.

Equivalent. Note: the in-memory `_analysis_from_bars` (live walk-forward
fallback at `service.py:490+`) — not re-read for this review, but worth
spot-checking that it uses the same shifted-window definition.

### Parity verdict

The two paths agree on the *meaning* of every limit-up field. The single
behavioral divergence is at very small `n` (`high_60d_ratio` for `n < 5`),
which is unimportant in practice. The shared bugs (close-not-high,
ST-not-handled, BSE-`92` prefix) affect both paths equally — backtests
will agree with live, both wrong in the same way.

### `StockAnalysisSummaryOut` schema staleness (minor)

`schemas.py:73–74` says "Live ``screen_stocks`` does not currently set
these, so they default to None for back-compat." This is **out of date** —
`get_stock_analysis_summary` (`service.py:273`) now splats
`_derive_limit_up_fields(...)` into the output. The fields are populated
on the live path. Update the docstring.

---

## Suggested test cases

Concrete cases to add under `tests/modules/market_data/`:

### Limit-up threshold detection

1. **Main board zt exact**: code `600519`, prev_close `1500.00`,
   today_close `1650.00` (+10.0%). Expect `is_limit_up_today = True`.
2. **Main board near-miss**: prev_close `100.00`, today_close `109.79`
   (+9.79%). Expect `is_limit_up_today = False` (just under 9.8 threshold).
3. **Main board rounding-floor edge**: prev_close `100.00`, today_close
   `109.81` (+9.81%). Expect `True` (the 0.2pct tolerance accepts).
4. **ChiNext zt**: code `300001`, prev_close `10.00`, today_close `12.00`
   (+20%). Expect `True` with threshold 19.8.
5. **STAR zt**: code `688981`, +20%. Expect `True`.
6. **BSE `83…`**: code `831010`, +30%. Expect `True` (threshold 19.8 is
   passed, even though real BSE limit is ±30 on day-1 / ±30%; the gate is
   a lower bound so this is fine).
7. **BSE `92…`**: code `920001`, +25%. Expect `True` — but **currently
   fails** because `code.startswith(("8", "4"))` does not include `9`.
   (Documents the bug.)
8. **ST stock at +5%**: name `ST海马`, prev_close `2.00`, today_close
   `2.10` (+5%). Expect: real-world this IS a limit-up, but the screener
   currently records `is_limit_up_today = False`. (Documents the bug.)

### Streak counting

9. **Single zt**: a 60-bar series where only the last bar is zt. Expect
   `consec_limit_up_days = 1`.
10. **3 连板**: last 3 bars all zt. Expect `consec = 3`.
11. **Broken streak**: zt zt non-zt zt. Expect `consec = 1` (only today).
12. **All non-zt**: expect `consec = 0`, `is_limit_up_today = False`.
13. **一字板 streak**: a 5-bar series where each bar is open=high=low=close
    and each close is +10% from prev. Expect `consec = 5`.

### `days_since_last_limit_up` semantics

14. **Today is zt, yesterday was zt**: `days_since` should be 1 (not 0).
15. **Today is zt, prior zt was 30 days ago**: `days_since = 30`.
16. **Today is zt, no prior zt in window**: `days_since = None`.
17. **Today not zt, yesterday was zt**: `days_since = 1` — this is the
    `zt_relay` precondition.
18. **Today not zt, no prior zt**: `days_since = None`.

### first_limit_up_low

19. **Happy path**: 60 bars flat at `10.00` close, today opens `10.00`,
    closes `11.00` (+10%). Expect match. `high_60d_ratio = 11/11 = 1.0`
    — wait, `max_close = 11`, `latest_close / max = 1.0`, **fails the
    0.85 gate**. (Demonstrates the close-not-high bug fixing direction.)
20. **Low base + zt**: 60 bars stepping down from `15.00` to `10.00`,
    today closes at `11.00` (+10%). Max prior close = 15.00; ratio
    = 11/15 ≈ 0.73 → passes.
21. **30-bar 新股 with zt**: should this match? Document expected
    behavior. Currently it can match if it has zero prior zt in the
    window.
22. **Recently-resumed stock**: 30 bars halt-suspended (no rows),
    resumes with zt. Currently matches; arguably should not.
23. **Daily +9% rallies, then zt**: prior 20 bars all `pct_change ≈
    +9%`, today zt. Currently matches (no big-up gate); should likely
    not.
24. **ST stock +5% after long quiet**: zt under real rules, but the
    screener does not detect it.

### leader_streak

25. **2 连板, bullish, vol_ratio 1.5**: matches with default `min_streak=2`.
    Confirm `match_reason` text.
26. **2 连板, bearish trend_bias**: rejected.
27. **5 连板, vol_ratio 0.8**: rejected (volume gate fails).
28. **5 连板 with 一字板 (vol_ratio < 1)**: currently rejected. Document
    that real 龙头 may have low volume on 一字板.
29. **Two stocks with same streak, different sectors**: confirm both
    match (no sector dedup currently).

### zt_relay

30. **T0 zt, T+1 gap +2%, vol 1.5**: matches.
31. **T0 zt, T+1 gap +6%**: rejected by gap gate.
32. **T0 zt, T+1 gap -2%**: currently matches (gap ≤ 5). Document that
    this is likely wrong.
33. **T0 zt as 9-board, T+1 break**: currently matches with no streak
    penalty — `max_streak` is a no-op. Add a test that asserts this is
    the current (broken) behavior so the fix can be validated.
34. **T0 was 2 days ago (`days_since = 2`)**: rejected by `!= 1` gate.
35. **T0 一字板, T+1 gap +1%**: currently matches; arguably the candidate
    set should exclude 一字板 T0.

### Parity (live vs precomputed)

For each of cases 9–18, build the same series and assert that
`_derive_limit_up_fields(code, bars)[k] == PrecomputedScreenSeries
.build(code, bars, trend_fn).analysis_at(code, bars[-1].trade_date).k`
for every k in `{is_limit_up_today, consec_limit_up_days,
days_since_last_limit_up, open_gap_pct, high_60d_ratio, pct_change_1d}`.

### Edge cases

36. **Empty bars**: live returns all-None; precomputed returns None
    analysis (no bars to bisect). Confirm.
37. **Single bar**: live `is_zt = False`, `days_since = None`,
    `open_gap_pct = None`. Confirm.
38. **n=4 boundary for `high_60d_ratio`**: live returns a value,
    precomputed returns None — assert and decide which behavior is
    canonical.
39. **prev_close = 0** (corrupt data): both paths must not divide by
    zero. Live guards explicitly (`service.py:441–443`); precomputed
    relies on pandas producing inf/NaN — verify it doesn't leak `inf`
    into `pct_change_1d`.
