import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { api, ApiError } from "@quant/api-client";

// ---------------------------------------------------------------------------
// Types — mirror backend Pydantic schemas exactly.
// Source of truth: backend/app/modules/strategies/schemas.py
// ---------------------------------------------------------------------------

export type StrategyKey =
  | "strong_uptrend"
  | "volume_breakout"
  | "pullback_watch";

/** Fixed enum of taxonomy tags exposed by the backend strategies endpoint. */
export type StrategyFactorTag =
  | "trend_following"
  | "momentum"
  | "mean_reversion"
  | "volume";

export type StrategyRegimeTag =
  | "trending_market"
  | "ranging_market"
  | "volatile_market";

export type StrategyTag = StrategyFactorTag | StrategyRegimeTag;

export const STRATEGY_FACTOR_TAGS: StrategyFactorTag[] = [
  "trend_following",
  "momentum",
  "mean_reversion",
  "volume",
];

export const STRATEGY_REGIME_TAGS: StrategyRegimeTag[] = [
  "trending_market",
  "ranging_market",
  "volatile_market",
];

export interface SparklinePoint {
  date: string;
  value: number;
}

export interface StrategyKpi {
  as_of_date: string;
  lookback_days: number;
  annualized_return_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  win_rate_pct: number | null;
  total_return_pct: number | null;
  trade_count: number;
  equity_sparkline: SparklinePoint[];
}

export interface Strategy {
  key: StrategyKey;
  tags: StrategyTag[];
  default_params: Record<string, number>;
  kpi: StrategyKpi | null;
}

export interface StrategiesResponse {
  strategies: Strategy[];
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fetch the catalog of built-in strategies with their risk-adjusted KPIs and
 * equity sparklines. KPIs may be null if the backend has not yet computed them.
 */
export function useStrategies(
  options?: Omit<
    UseQueryOptions<StrategiesResponse, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<StrategiesResponse, Error>({
    queryKey: ["strategies", "catalog"],
    queryFn: () => api.get<StrategiesResponse>("/strategies"),
    staleTime: 5 * 60 * 1000, // 5 min
    ...options,
  });
}

export { ApiError };
