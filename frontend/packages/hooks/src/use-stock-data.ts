import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "@quant/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** OHLCV bar from the FastAPI backend. */
export interface OHLCVBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** Real-time stock quote. */
export interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  turnover: number;
  high: number | null;
  low: number | null;
  open: number | null;
  prev_close: number | null;
  timestamp: string;
  is_delayed?: boolean;
}

export interface StockSummary {
  code: string;
  name: string;
  industry: string | null;
  market: string;
  list_date: string | null;
}

export interface StockAnalysisSummary {
  symbol: string;
  latest_close: number;
  ma5: number | null;
  ma20: number | null;
  rsi14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  price_vs_ma5_pct: number | null;
  price_vs_ma20_pct: number | null;
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  volume_ratio_5d: number | null;
  trend_bias: "bullish" | "bearish" | "neutral";
  summary: string;
  signals: Array<{ name: string; detail: string }>;
}

export interface StockScreenItem {
  symbol: string;
  name: string;
  market: string;
  industry: string | null;
  latest_close: number;
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  volume_ratio_5d: number | null;
  trend_bias: "bullish" | "bearish" | "neutral";
  match_reason: string;
  is_on_dragon_tiger: boolean;
  is_limit_up_candidate: boolean;
  hot_tags: string[];
  related_news_headlines: string[];
}

export interface StockScreenResult {
  screen_type: string;
  total: number;
  items: StockScreenItem[];
}

export interface WatchlistItem {
  id: string;
  stock_code: string;
  stock_name: string;
  match_reason: string | null;
  hot_tags: string[];
  created_at: string;
}

export interface Watchlist {
  id: string;
  name: string;
  source_screen_type: string | null;
  screen_params_json: string | null;
  auto_refresh: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  last_refreshed_at: string | null;
  items: WatchlistItem[];
}

export interface CreateWatchlistPayload {
  name: string;
  source_screen_type?: string;
  screen_params_json?: string;
  auto_refresh?: string;
  notes?: string;
  items: Array<{
    stock_code: string;
    stock_name: string;
    match_reason?: string;
    hot_tags?: string[];
  }>;
}

export interface StockScreenParams {
  limit?: number;
  min_return_20d_pct?: number;
  min_return_5d_pct?: number;
  min_volume_ratio?: number;
  max_return_5d_pct?: number;
}

export interface MarketOverview {
  stock_count: number;
  latest_trade_date: string | null;
  latest_dragon_tiger_date: string | null;
  latest_limit_up_date: string | null;
  latest_news_date: string | null;
  latest_dragon_tiger_count: number;
  latest_limit_up_count: number;
  latest_news_count: number;
}

export interface DragonTigerItem {
  id: number;
  trade_date: string;
  code: string;
  name: string;
  close_price: number;
  change_pct: number;
  reason: string | null;
  buy_amount: number | null;
  sell_amount: number | null;
  net_buy: number | null;
}

export interface LimitUpItem {
  id: number;
  trade_date: string;
  code: string;
  name: string;
  close_price: number;
  change_pct: number;
  limit_up_time: string | null;
  open_times: number | null;
  turnover: number | null;
  reason: string | null;
}

export interface NewsItem {
  id: number;
  trade_date: string;
  title: string;
  content: string | null;
  source: string | null;
  url: string | null;
  code: string | null;
  published_at: string | null;
}

/** Parameters accepted by the K-line (candlestick) endpoint.
 *
 * Backend currently stores daily bars and resamples server-side for weekly /
 * monthly. Intraday periods are intentionally not supported until intraday
 * ingestion lands. */
export interface StockKlineParams {
  symbol: string;
  period?: "daily" | "weekly" | "monthly";
  start?: string;
  end?: string;
  limit?: number;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const stockKeys = {
  all: ["stocks"] as const,
  stockList: () => ["stocks", "list"] as const,
  stockDetail: (symbol: string) => ["stocks", "detail", symbol] as const,
  stockAnalysis: (symbol: string) => ["stocks", "analysis", symbol] as const,
  stockScreen: (screenType: string, params: StockScreenParams) => ["stocks", "screen", screenType, params] as const,
  watchlists: () => ["watchlists"] as const,
  marketOverview: () => ["market", "overview"] as const,
  dragonTiger: (tradeDate: string) => ["market", "dragon-tiger", tradeDate] as const,
  limitUp: (tradeDate: string) => ["market", "limit-up", tradeDate] as const,
  news: (tradeDate: string, limit: number) => ["market", "news", tradeDate, limit] as const,
  quotes: () => [...stockKeys.all, "quote"] as const,
  quote: (symbol: string) => [...stockKeys.quotes(), symbol] as const,
  kline: (params: StockKlineParams) =>
    [...stockKeys.all, "kline", params] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Fetch K-line (candlestick) data for a given stock symbol and period.
 *
 * A-share convention: positive `change` means up (red), negative means down (green).
 */
export function useStockKline(
  params: StockKlineParams,
  options?: Omit<
    UseQueryOptions<OHLCVBar[], Error, OHLCVBar[], ReturnType<typeof stockKeys.kline>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.kline(params),
    queryFn: () =>
      api.get<OHLCVBar[]>("/stocks/kline", {
        params: {
          symbol: params.symbol,
          period: params.period,
          start: params.start,
          end: params.end,
          limit: params.limit,
        },
      }),
    ...options,
  });
}

export function useMarketOverview(
  options?: Omit<
    UseQueryOptions<MarketOverview, Error, MarketOverview, ReturnType<typeof stockKeys.marketOverview>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.marketOverview(),
    queryFn: () => api.get<MarketOverview>("/market/overview"),
    ...options,
  });
}

export function useStockList(
  options?: Omit<
    UseQueryOptions<StockSummary[], Error, StockSummary[], ReturnType<typeof stockKeys.stockList>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.stockList(),
    queryFn: () => api.get<StockSummary[]>("/stocks"),
    ...options,
  })
}

export function useStockDetail(
  symbol: string,
  options?: Omit<
    UseQueryOptions<StockSummary, Error, StockSummary, ReturnType<typeof stockKeys.stockDetail>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.stockDetail(symbol),
    queryFn: () => api.get<StockSummary>(`/stocks/${symbol}`),
    enabled: !!symbol,
    ...options,
  })
}

export function useStockAnalysis(
  symbol: string,
  options?: Omit<
    UseQueryOptions<StockAnalysisSummary, Error, StockAnalysisSummary, ReturnType<typeof stockKeys.stockAnalysis>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.stockAnalysis(symbol),
    queryFn: () => api.get<StockAnalysisSummary>(`/stocks/${symbol}/analysis`),
    enabled: !!symbol,
    ...options,
  })
}

export function useStockScreen(
  screenType: string,
  params: StockScreenParams = {},
  options?: Omit<
    UseQueryOptions<StockScreenResult, Error, StockScreenResult, ReturnType<typeof stockKeys.stockScreen>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.stockScreen(screenType, params),
    queryFn: () =>
      api.get<StockScreenResult>("/analysis/screen", {
        params: {
          screen_type: screenType,
          limit: params.limit,
          min_return_20d_pct: params.min_return_20d_pct,
          min_return_5d_pct: params.min_return_5d_pct,
          min_volume_ratio: params.min_volume_ratio,
          max_return_5d_pct: params.max_return_5d_pct,
        },
      }),
    enabled: !!screenType,
    ...options,
  })
}

export function useWatchlists(
  options?: Omit<
    UseQueryOptions<Watchlist[], Error, Watchlist[], ReturnType<typeof stockKeys.watchlists>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.watchlists(),
    queryFn: () => api.get<Watchlist[]>("/watchlists"),
    ...options,
  })
}

export async function createWatchlist(payload: CreateWatchlistPayload) {
  return api.post<Watchlist>("/watchlists", payload)
}

export async function refreshWatchlist(watchlistId: string) {
  return api.post<Watchlist>(`/watchlists/${watchlistId}/refresh`)
}

export async function refreshAutoWatchlists() {
  return api.post<Watchlist[]>("/watchlists/refresh/auto")
}

export function useDragonTigerList(
  tradeDate: string,
  options?: Omit<
    UseQueryOptions<DragonTigerItem[], Error, DragonTigerItem[], ReturnType<typeof stockKeys.dragonTiger>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.dragonTiger(tradeDate),
    queryFn: () =>
      api.get<DragonTigerItem[]>("/market/dragon-tiger", {
        params: { trade_date: tradeDate },
      }),
    enabled: !!tradeDate,
    ...options,
  });
}

export function useLimitUpBoard(
  tradeDate: string,
  options?: Omit<
    UseQueryOptions<LimitUpItem[], Error, LimitUpItem[], ReturnType<typeof stockKeys.limitUp>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.limitUp(tradeDate),
    queryFn: () =>
      api.get<LimitUpItem[]>("/market/limit-up", {
        params: { trade_date: tradeDate },
      }),
    enabled: !!tradeDate,
    ...options,
  });
}

export function useMarketNews(
  tradeDate: string,
  limit = 6,
  options?: Omit<
    UseQueryOptions<NewsItem[], Error, NewsItem[], ReturnType<typeof stockKeys.news>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.news(tradeDate, limit),
    queryFn: () =>
      api.get<NewsItem[]>("/market/news", {
        params: { trade_date: tradeDate, limit },
      }),
    enabled: !!tradeDate,
    ...options,
  });
}

/**
 * Fetch a real-time stock quote.
 */
export function useStockQuote(
  symbol: string,
  options?: Omit<
    UseQueryOptions<StockQuote, Error, StockQuote, ReturnType<typeof stockKeys.quote>>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: stockKeys.quote(symbol),
    queryFn: () => api.get<StockQuote>(`/stocks/${symbol}/quote`),
    // Quotes should refresh more often
    staleTime: 10 * 1000, // 10s
    refetchInterval: 15 * 1000, // 15s polling
    enabled: !!symbol,
    ...options,
  });
}
