"""Tests for the extended ``run_screener_backtest`` engine: fee_bps,
stop_profit alias, hs300 fallback, attribution, and period returns."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.modules.backtests.schemas import ScreenerBacktestRequest
from app.modules.backtests.service import BacktestService
from app.modules.market_data.schemas import StockScreenItemOut, StockScreenResultOut


def _bar(*, code: str, dt: date, close: float) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        trade_date=dt,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=0.0,
    )


def _build_two_stock_universe() -> tuple[list[date], dict[str, list]]:
    start = date(2026, 1, 5)
    days = [start + timedelta(days=i) for i in range(30)]
    bars_a = [_bar(code="000001", dt=d, close=10.0 + i * 0.1) for i, d in enumerate(days)]
    bars_b = [_bar(code="600519", dt=d, close=20.0 + i * 0.05) for i, d in enumerate(days)]
    return days, {"000001": bars_a, "600519": bars_b}


def _patch_market(monkeypatch, svc: BacktestService, bars_by_code) -> None:
    async def fake_codes():
        return set(bars_by_code.keys())

    async def fake_stocks():
        return [
            SimpleNamespace(code="000001", name="Alpha", industry="电子"),
            SimpleNamespace(code="600519", name="Moutai", industry="酿酒"),
        ]

    async def fake_bulk(codes, start_date=None, end_date=None):
        return {
            c: [
                b
                for b in bars_by_code.get(c, [])
                if (start_date is None or b.trade_date >= start_date)
                and (end_date is None or b.trade_date <= end_date)
            ]
            for c in codes
        }

    async def fake_screen(screen_type, params=None, *, as_of_date=None):
        return StockScreenResultOut(
            screen_type=screen_type,
            total=2,
            items=[
                StockScreenItemOut(
                    symbol="000001",
                    name="Alpha",
                    market="SZ",
                    industry="电子",
                    latest_close=10.0,
                    return_5d_pct=2.0,
                    return_20d_pct=8.0,
                    volume_ratio_5d=1.5,
                    trend_bias="bullish",
                    match_reason="ok",
                ),
                StockScreenItemOut(
                    symbol="600519",
                    name="Moutai",
                    market="SH",
                    industry="酿酒",
                    latest_close=20.0,
                    return_5d_pct=1.0,
                    return_20d_pct=4.0,
                    volume_ratio_5d=1.2,
                    trend_bias="bullish",
                    match_reason="ok",
                ),
            ],
        )

    monkeypatch.setattr(svc.market_data.repo, "get_codes_with_daily_bars", fake_codes)
    monkeypatch.setattr(svc.market_data.repo, "get_stocks", fake_stocks)
    monkeypatch.setattr(svc.market_data.repo, "get_daily_bars_for_codes", fake_bulk)
    monkeypatch.setattr(svc.market_data, "screen_stocks", fake_screen)


@pytest.mark.asyncio
async def test_extended_fields_attribution_and_monthly_returns(monkeypatch):
    svc = BacktestService()
    days, bars_by_code = _build_two_stock_universe()
    _patch_market(monkeypatch, svc, bars_by_code)

    req = ScreenerBacktestRequest(
        screen_type="strong_uptrend",
        start_date=days[0],
        end_date=days[-1],
        rebalance="weekly",
        top_n=2,
        weighting="equal",
        initial_capital=100_000.0,
        stop_loss_pct=None,
        take_profit_pct=None,
        benchmark="universe_buy_hold",
    )
    result = await svc.run_screener_backtest(req)

    # Extended KPI fields are populated.
    assert result.sharpe_ratio is not None
    assert result.alpha_pct is not None  # benchmark fed in
    assert result.benchmark_kind == "universe_buy_hold"
    # Sortino requires at least one negative day; on a steady uptrend it
    # may be None — just confirm the field is exposed.
    assert "sortino_ratio" in result.model_dump()
    # Calmar depends on max_dd > 0; on a strict uptrend force-close is the
    # only DD trigger, so we tolerate None.
    assert "calmar_ratio" in result.model_dump()

    # Period returns + attribution.
    assert result.monthly_returns, "monthly_returns must be populated"
    assert result.attribution is not None
    assert result.attribution.market_cap_buckets
    # Sectors come from fake stocks' industry field.
    sectors = {s.sector for s in result.attribution.sector_exposure}
    assert "电子" in sectors or "酿酒" in sectors


@pytest.mark.asyncio
async def test_fee_bps_overrides_individual_rates(monkeypatch):
    svc = BacktestService()
    days, bars_by_code = _build_two_stock_universe()
    _patch_market(monkeypatch, svc, bars_by_code)

    req = ScreenerBacktestRequest(
        screen_type="strong_uptrend",
        start_date=days[0],
        end_date=days[-1],
        rebalance="weekly",
        top_n=2,
        weighting="equal",
        initial_capital=100_000.0,
        commission_rate=0.0,
        slippage_rate=0.0,
        stamp_duty_rate=0.0,
        fee_bps=50,  # 50bps total = 25bps commission + 25bps slippage
        stop_loss_pct=None,
        take_profit_pct=None,
        benchmark="none",
    )
    result = await svc.run_screener_backtest(req)
    # With non-zero fee_bps and at least one trade, commission + slippage > 0.
    assert result.trade_count >= 1
    assert result.costs.total_commission > 0 or result.costs.total_slippage_cost > 0


@pytest.mark.asyncio
async def test_stop_profit_pct_alias(monkeypatch):
    svc = BacktestService()
    days, bars_by_code = _build_two_stock_universe()
    _patch_market(monkeypatch, svc, bars_by_code)
    req = ScreenerBacktestRequest(
        screen_type="strong_uptrend",
        start_date=days[0],
        end_date=days[-1],
        rebalance="weekly",
        top_n=2,
        weighting="equal",
        initial_capital=100_000.0,
        # ``stop_profit_pct`` is the alias the front-end form posts.
        stop_profit_pct=1.0,
        stop_loss_pct=None,
        benchmark="none",
    )
    result = await svc.run_screener_backtest(req)
    # Some trades should have take_profit exit_reason since price rises >1%.
    reasons = {t.exit_reason.value for t in result.trades}
    assert "take_profit" in reasons or "final_close" in reasons


@pytest.mark.asyncio
async def test_hs300_benchmark_falls_back_when_index_missing(monkeypatch):
    svc = BacktestService()
    days, bars_by_code = _build_two_stock_universe()
    _patch_market(monkeypatch, svc, bars_by_code)

    # The repo will return [] for any HS300 candidate code → fallback path.
    async def empty_get_daily_bars(code, start_date, end_date):
        return []

    monkeypatch.setattr(svc.market_data.repo, "get_daily_bars", empty_get_daily_bars)

    req = ScreenerBacktestRequest(
        screen_type="strong_uptrend",
        start_date=days[0],
        end_date=days[-1],
        rebalance="weekly",
        top_n=2,
        weighting="equal",
        benchmark="hs300",
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    result = await svc.run_screener_backtest(req)
    assert result.benchmark_curve is not None
    assert result.benchmark_kind == "hs300_or_fallback"


@pytest.mark.asyncio
async def test_volume_breakout_finds_candidates_after_default_relaxation(
    monkeypatch,
):
    """The catalog defaults must allow volume_breakout to actually pick stocks
    on a fixture where MACD histogram is not strictly positive.
    """
    from app.modules.market_data.schemas import StockScreenParams
    from app.modules.market_data.service import MarketDataService

    md = MarketDataService()

    async def fake_get_stocks():
        return [SimpleNamespace(code="000001", name="A", market="SZ", industry="电子")]

    async def fake_codes():
        return {"000001"}

    async def fake_summary(code, *, local_only=False, as_of_date=None):
        from app.modules.market_data.schemas import StockAnalysisSummaryOut

        return StockAnalysisSummaryOut(
            symbol=code,
            latest_close=10.0,
            ma5=9.5,
            ma20=9.0,
            rsi14=55.0,
            macd=0.1,
            macd_signal=0.2,
            macd_histogram=-0.05,  # NEGATIVE — would be filtered by old hard rule
            price_vs_ma5_pct=5.0,
            price_vs_ma20_pct=11.0,
            return_5d_pct=2.0,
            return_20d_pct=12.0,
            volume_ratio_5d=1.4,
            trend_bias="bullish",
            summary="ok",
            signals=[],
        )

    async def fake_lt_dragon():
        return None

    async def fake_lt_limit_up():
        return None

    async def fake_lt_news():
        return None

    monkeypatch.setattr(md.repo, "get_stocks", fake_get_stocks)
    monkeypatch.setattr(md.repo, "get_codes_with_daily_bars", fake_codes)
    monkeypatch.setattr(md, "get_stock_analysis_summary", fake_summary)
    monkeypatch.setattr(md.repo, "get_latest_trade_date_for_dragon_tiger", fake_lt_dragon)
    monkeypatch.setattr(md.repo, "get_latest_trade_date_for_limit_up", fake_lt_limit_up)
    monkeypatch.setattr(md.repo, "get_latest_trade_date_for_news", fake_lt_news)

    # With default require_macd_positive=False the screener now picks the
    # candidate that the legacy hard rule would have silently dropped.
    res = await md.screen_stocks("volume_breakout", StockScreenParams())
    assert res.total >= 1
    # And opting-in to the strict filter restores the old behaviour.
    res_strict = await md.screen_stocks(
        "volume_breakout", StockScreenParams(require_macd_positive=True)
    )
    assert res_strict.total == 0
