from datetime import date, datetime

from pydantic import BaseModel


class StockOut(BaseModel):
    code: str
    name: str
    industry: str | None
    market: str
    list_date: date | None

    model_config = {"from_attributes": True}


class DailyBarOut(BaseModel):
    code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    turnover: float | None

    model_config = {"from_attributes": True}


class StockQuoteOut(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    turnover: float
    high: float | None = None
    low: float | None = None
    open: float | None = None
    prev_close: float | None = None
    timestamp: datetime
    is_delayed: bool = False


class StockKlineOut(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockAnalysisSummaryOut(BaseModel):
    symbol: str
    latest_close: float
    ma5: float | None
    ma20: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    price_vs_ma5_pct: float | None
    price_vs_ma20_pct: float | None
    return_5d_pct: float | None
    return_20d_pct: float | None
    volume_ratio_5d: float | None
    trend_bias: str
    summary: str
    signals: list[dict[str, str]]
    # Optional limit-up extension fields. Populated by both the live
    # ``screen_stocks`` path and the precomputed walk-forward backtest path.
    pct_change_1d: float | None = None
    is_limit_up_today: bool | None = None
    consec_limit_up_days: int | None = None
    open_gap_pct: float | None = None
    high_60d_ratio: float | None = None
    days_since_last_limit_up: int | None = None
    # Streak ending at the most recent limit-up bar PRIOR to today. Used by
    # the zt_relay screener to gate against late-stage relays. ``None`` when
    # there is no prior limit-up in the visible window.
    prior_consec_limit_up_days: int | None = None


class StockScreenItemOut(BaseModel):
    symbol: str
    name: str
    market: str
    industry: str | None
    latest_close: float
    return_5d_pct: float | None
    return_20d_pct: float | None
    volume_ratio_5d: float | None
    trend_bias: str
    match_reason: str
    is_on_dragon_tiger: bool = False
    is_limit_up_candidate: bool = False
    hot_tags: list[str] = []
    related_news_headlines: list[str] = []
    # Optional limit-up extension fields surfaced for UI ranking.
    consec_limit_up_days: int | None = None
    high_60d_ratio: float | None = None


class StockScreenResultOut(BaseModel):
    screen_type: str
    total: int
    items: list[StockScreenItemOut]


class StockScreenParams(BaseModel):
    limit: int = 10
    min_return_20d_pct: float | None = None
    min_return_5d_pct: float | None = None
    min_volume_ratio: float | None = None
    max_return_5d_pct: float | None = None
    # When True, the volume_breakout screener also requires a positive MACD
    # histogram. Defaults to False so the screener does not silently filter
    # out otherwise-valid breakout candidates.
    require_macd_positive: bool = False
    # Maximum number of candidate stocks to evaluate per scan. Defaults to
    # 1500 (effectively the entire local universe). Lower values make the
    # endpoint snappier when memory or latency constrained.
    max_candidates: int = 1500
    # New strategy params
    min_streak: int | None = None  # leader_streak: required consecutive limit-up days
    max_streak: int | None = None  # zt_relay: cap on prior streak (avoid late chasers)
    max_open_gap_pct: float | None = None  # zt_relay: today's open gap relative to yesterday's close
    max_high_60d_ratio: float | None = None  # first_limit_up_low: latest_close / 60d_high upper bound
    min_quiet_days: int | None = None  # first_limit_up_low: how many trailing days without a limit-up
    # lhb_follow params
    min_net_buy_yi: float | None = None  # 龙虎榜净买入额最低（亿元）
    lhb_lookback_days: int | None = None  # 跟买窗口：最近 N 个交易日上榜即可触发，默认 1
    # Market segment filter. ``None`` or empty list = all 5 boards allowed.
    # Tokens come from MarketSegment in market_data.markets.
    markets: list[str] | None = None
    # When False (default), ST/*ST stocks are filtered out at the candidate
    # stage. Set True to opt them in.
    include_st: bool = False


class MarketOverviewOut(BaseModel):
    stock_count: int
    latest_trade_date: date | None
    latest_dragon_tiger_date: date | None
    latest_limit_up_date: date | None
    latest_news_date: date | None
    latest_dragon_tiger_count: int
    latest_limit_up_count: int
    latest_news_count: int


class DailyBarQuery(BaseModel):
    code: str
    start_date: date | None = None
    end_date: date | None = None


class SyncResult(BaseModel):
    synced: int
    message: str


class DragonTigerOut(BaseModel):
    id: int
    trade_date: date
    code: str
    name: str
    close_price: float
    change_pct: float
    reason: str | None
    buy_amount: float | None
    sell_amount: float | None
    net_buy: float | None

    model_config = {"from_attributes": True}


class LimitUpOut(BaseModel):
    id: int
    trade_date: date
    code: str
    name: str
    close_price: float
    change_pct: float
    limit_up_time: str | None
    open_times: int | None
    turnover: float | None
    reason: str | None

    model_config = {"from_attributes": True}


class NewsOut(BaseModel):
    id: int
    trade_date: date
    title: str
    content: str | None
    source: str | None
    url: str | None
    code: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}
