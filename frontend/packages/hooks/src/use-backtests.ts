import {
  useMutation,
  useQuery,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api, ApiError } from "@quant/api-client";
import type { StockScreenItem } from "./use-stock-data";

// ---------------------------------------------------------------------------
// Types — mirror backend Pydantic schemas exactly.
// Source of truth: backend/app/modules/backtests/schemas.py
// ---------------------------------------------------------------------------

export interface BacktestRequest {
  code: string;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  strategy?: string;
  fast_period?: number;
  slow_period?: number;
  initial_capital?: number;
}

export interface BacktestTrade {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  return_pct: number;
  holding_days: number;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface BacktestResult {
  code: string;
  strategy: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  annualized_return_pct: number | null;
  win_rate_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  final_equity: number;
  initial_capital: number;
  trades: BacktestTrade[];
  equity_curve: EquityPoint[];
}

/** Stock code with locally synced daily bars, returned by the eligibility endpoint. */
export interface EligibleCode {
  code: string;
  name: string;
  bar_count: number;
}

// ---------------------------------------------------------------------------
// Screener walk-forward backtest types
// ---------------------------------------------------------------------------

export type ScreenerType =
  | "strong_uptrend"
  | "volume_breakout"
  | "pullback_watch"
  | "first_limit_up_low"
  | "leader_streak"
  | "zt_relay"
  | "lhb_follow";

export type RebalanceCadence = "daily" | "weekly" | "biweekly" | "monthly";
export type WeightingMode = "equal" | "score";
export type BenchmarkMode = "none" | "universe_buy_hold";

export type RebalanceTradeReason =
  | "screener_pick"
  | "screener_drop"
  | "stop_loss"
  | "take_profit"
  | "final_close";

export interface ScreenerBacktestRequest {
  screen_type: ScreenerType;
  screen_params_override?: {
    limit?: number;
    min_return_20d_pct?: number | null;
    min_return_5d_pct?: number | null;
    min_volume_ratio?: number | null;
    max_return_5d_pct?: number | null;
    markets?: string[] | null;
    include_st?: boolean | null;
  } | null;
  start_date: string;
  end_date: string;
  rebalance: RebalanceCadence;
  top_n: number;
  weighting: WeightingMode;
  initial_capital: number;
  commission_rate: number;
  stamp_duty_rate: number;
  slippage_rate: number;
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  benchmark: BenchmarkMode;
}

export interface HoldingItem {
  code: string;
  name: string;
  shares: number;
  market_value: number;
  weight_pct: number;
}

export interface HoldingSnapshot {
  date: string;
  cash: number;
  equity: number;
  holdings: HoldingItem[];
}

export interface ScreenerBacktestTrade {
  code: string;
  name: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  shares: number;
  return_pct: number;
  holding_days: number;
  exit_reason: RebalanceTradeReason;
}

export interface CostBreakdown {
  total_commission: number;
  total_stamp_duty: number;
  total_slippage_cost: number;
  cost_drag_pct: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown_pct: number;
}

export interface MonthlyReturn {
  period: string; // "YYYY-MM"
  return_pct: number;
}

export interface YearlyReturn {
  period: string; // "YYYY"
  return_pct: number;
}

export interface SectorWeight {
  sector: string;
  weight_pct: number;
}

export interface MarketCapBucket {
  bucket: string;
  weight_pct: number;
}

export interface AttributionOut {
  sector_exposure: SectorWeight[];
  market_cap_buckets: MarketCapBucket[];
  monthly_returns: MonthlyReturn[];
  yearly_returns: YearlyReturn[];
}

export interface ScreenerBacktestResult {
  screen_type: string;
  rebalance: string;
  top_n: number;
  weighting: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  annualized_return_pct: number | null;
  win_rate_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  final_equity: number;
  initial_capital: number;
  sortino_ratio?: number | null;
  calmar_ratio?: number | null;
  turnover_pct?: number | null;
  sharpe_ratio?: number | null;
  alpha_pct?: number | null;
  equity_curve: EquityPoint[];
  benchmark_curve: EquityPoint[] | null;
  benchmark_kind?: string | null;
  drawdown_curve: DrawdownPoint[];
  rebalance_dates: string[];
  holdings_history: HoldingSnapshot[];
  trades: ScreenerBacktestTrade[];
  costs: CostBreakdown;
  monthly_returns?: MonthlyReturn[];
  yearly_returns?: YearlyReturn[];
  attribution?: AttributionOut | null;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Run a single-stock simple backtest. Pure mutation — the backend writes
 * nothing to the database.
 */
export function useRunBacktest(
  options?: Omit<
    UseMutationOptions<BacktestResult, Error, BacktestRequest>,
    "mutationFn"
  >,
) {
  return useMutation<BacktestResult, Error, BacktestRequest>({
    mutationFn: (req) => api.post<BacktestResult>("/backtests/simple", req),
    ...options,
  });
}

/**
 * Fetch the list of stock codes that have local daily bars available for
 * backtesting. Used to populate the autocomplete datalist on the form.
 */
export function useEligibleBacktestCodes(
  options?: Omit<
    UseQueryOptions<EligibleCode[], Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<EligibleCode[], Error>({
    queryKey: ["backtests", "eligible-codes"],
    queryFn: () => api.get<EligibleCode[]>("/backtests/eligible-codes"),
    staleTime: 60 * 1000,
    ...options,
  });
}

/**
 * Run a screener-based walk-forward portfolio backtest.
 */
export function useRunScreenerBacktest(
  options?: Omit<
    UseMutationOptions<ScreenerBacktestResult, Error, ScreenerBacktestRequest>,
    "mutationFn"
  >,
) {
  return useMutation<ScreenerBacktestResult, Error, ScreenerBacktestRequest>({
    mutationFn: (req) =>
      api.post<ScreenerBacktestResult>("/backtests/screener", req),
    ...options,
  });
}

/**
 * Preview the picks a screener would produce on a specific historical date.
 * Used by the admin UI to let users sanity-check their strategy/date pick
 * before kicking off a full walk-forward backtest.
 */
export function useScreenerPreview(
  screen_type: ScreenerType,
  as_of_date: string | null,
  enabled: boolean = true,
  options?: Omit<
    UseQueryOptions<StockScreenItem[], Error>,
    "queryKey" | "queryFn" | "enabled"
  >,
) {
  return useQuery<StockScreenItem[], Error>({
    queryKey: ["backtests", "screener-preview", screen_type, as_of_date],
    queryFn: () => {
      const params = new URLSearchParams({
        screen_type,
        top_n: "20",
      });
      if (as_of_date) {
        params.set("as_of_date", as_of_date);
      }
      return api.get<StockScreenItem[]>(
        `/backtests/screener/preview?${params.toString()}`,
      );
    },
    enabled: enabled && Boolean(screen_type),
    staleTime: 60 * 1000,
    ...options,
  });
}

export { ApiError };
