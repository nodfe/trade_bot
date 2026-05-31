import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api, ApiError } from "@quant/api-client";
import type { ScreenerBacktestResult } from "./use-backtests";

// ---------------------------------------------------------------------------
// Types — mirror backend Pydantic schemas exactly.
// Source of truth: backend/app/modules/strategies/schemas.py
// ---------------------------------------------------------------------------

/** Built-in strategy keys. Custom strategies use `custom:{uuid}` form. */
export type BuiltInStrategyKey =
  | "strong_uptrend"
  | "volume_breakout"
  | "pullback_watch"
  | "first_limit_up_low"
  | "leader_streak"
  | "zt_relay"
  | "lhb_follow";

export type StrategyKey = BuiltInStrategyKey | string;

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

export interface MonthlyReturnPoint {
  year: number;
  month: number;
  return_pct: number;
}

export interface YearlyReturnPoint {
  year: number;
  return_pct: number;
}

export interface SectorExposurePoint {
  sector: string;
  weight_pct: number;
}

export interface MarketCapBucketPoint {
  bucket: string;
  weight_pct: number;
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
  sortino_ratio?: number | null;
  calmar_ratio?: number | null;
  turnover_pct?: number | null;
  alpha_pct?: number | null;
  monthly_returns?: MonthlyReturnPoint[] | Record<string, unknown>[];
  benchmark_equity_sparkline?: SparklinePoint[];
}

export interface Strategy {
  key: StrategyKey;
  tags: StrategyTag[];
  default_params: Record<string, number>;
  kpi: StrategyKpi | null;
  name?: string | null;
  base_template?: string | null;
  description?: string | null;
  is_custom?: boolean;
}

export interface StrategiesResponse {
  strategies: Strategy[];
}

export interface StrategyAttribution {
  key: string;
  lookback_days: number;
  sector_exposure: SectorExposurePoint[];
  market_cap_buckets: MarketCapBucketPoint[];
  monthly_returns: MonthlyReturnPoint[];
  yearly_returns: YearlyReturnPoint[];
}

export interface StrategyRunBacktestRequest {
  params?: Record<string, number | null> | null;
  top_n?: number | null;
  rebalance?: string | null;
  weighting?: string | null;
  fee_bps?: number | null;
  stop_loss_pct?: number | null;
  stop_profit_pct?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  benchmark?: string | null;
  initial_capital?: number | null;
}

// Custom (user) strategies
export interface UserStrategy {
  id: string;
  name: string;
  base_template: BuiltInStrategyKey;
  params: Record<string, number>;
  description: string | null;
  owner: string;
  catalog_key: string;
  kpi: StrategyKpi | null;
}

export interface UserStrategyCreate {
  name: string;
  base_template: BuiltInStrategyKey;
  params: Record<string, number>;
  description?: string | null;
  owner?: string;
}

export interface UserStrategyUpdate {
  name?: string;
  params?: Record<string, number>;
  description?: string | null;
}

// Combo
export interface StrategyComboItem {
  strategy_key: BuiltInStrategyKey;
  weight: number;
  params_override?: Record<string, number> | null;
}

export interface StrategyComboRequest {
  items: StrategyComboItem[];
  rebalance: "daily" | "weekly" | "biweekly" | "monthly";
  start_date: string;
  end_date: string;
  top_n: number;
  weighting: "equal" | "score";
  initial_capital?: number;
}

export interface StrategyComboKpi {
  total_return_pct: number;
  annualized_return_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  max_drawdown_pct: number;
}

export interface PerStrategyCurve {
  strategy_key: string;
  weight_normalized: number;
  equity_curve: { date: string; value: number }[];
}

export interface StrategyComboResponse {
  composite_equity_curve: { date: string; value: number }[];
  per_strategy_curves: PerStrategyCurve[];
  correlation_matrix: Record<string, Record<string, number>>;
  kpi: StrategyComboKpi;
  start_date: string;
  end_date: string;
  rebalance: string;
  initial_capital: number;
}

// Subscriptions
export interface Subscription {
  id: string;
  user_id: string;
  strategy_key: string;
  params: Record<string, unknown> | null;
  bot_channel_id: string;
  schedule: string;
  enabled: boolean;
  last_dispatched_at: string | null;
  created_at: string;
}

export interface SubscriptionCreate {
  user_id: string;
  strategy_key: string;
  params?: Record<string, unknown> | null;
  bot_channel_id: string;
  schedule?: string;
  enabled?: boolean;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export const strategyKeys = {
  all: ["strategies"] as const,
  catalog: () => [...strategyKeys.all, "catalog"] as const,
  detail: (key: string) => [...strategyKeys.all, "detail", key] as const,
  attribution: (key: string, lookback: number) =>
    [...strategyKeys.all, "attribution", key, lookback] as const,
  custom: () => [...strategyKeys.all, "custom"] as const,
  subscriptions: (userId?: string | null) =>
    [...strategyKeys.all, "subscriptions", userId ?? "all"] as const,
};

export function useStrategies(
  options?: Omit<
    UseQueryOptions<StrategiesResponse, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<StrategiesResponse, Error>({
    queryKey: strategyKeys.catalog(),
    queryFn: () => api.get<StrategiesResponse>("/strategies"),
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

export function useStrategy(
  key: string | null | undefined,
  options?: Omit<UseQueryOptions<Strategy, Error>, "queryKey" | "queryFn" | "enabled">,
) {
  return useQuery<Strategy, Error>({
    queryKey: strategyKeys.detail(key ?? ""),
    queryFn: () => api.get<Strategy>(`/strategies/${encodeURIComponent(key as string)}`),
    enabled: Boolean(key),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function useRunStrategyBacktest(
  strategyKey: string,
  options?: Omit<
    UseMutationOptions<ScreenerBacktestResult, Error, StrategyRunBacktestRequest>,
    "mutationFn"
  >,
) {
  return useMutation<ScreenerBacktestResult, Error, StrategyRunBacktestRequest>({
    mutationFn: (req) =>
      api.post<ScreenerBacktestResult>(
        `/strategies/${encodeURIComponent(strategyKey)}/run-backtest`,
        req,
      ),
    ...options,
  });
}

export function useStrategyAttribution(
  key: string | null | undefined,
  lookbackDays = 180,
  options?: Omit<
    UseQueryOptions<StrategyAttribution, Error>,
    "queryKey" | "queryFn" | "enabled"
  >,
) {
  return useQuery<StrategyAttribution, Error>({
    queryKey: strategyKeys.attribution(key ?? "", lookbackDays),
    queryFn: () =>
      api.get<StrategyAttribution>(
        `/strategies/${encodeURIComponent(key as string)}/attribution?lookback_days=${lookbackDays}`,
      ),
    enabled: Boolean(key),
    staleTime: 60 * 1000,
    ...options,
  });
}

// Custom strategies CRUD
export function useCustomStrategies(
  options?: Omit<UseQueryOptions<UserStrategy[], Error>, "queryKey" | "queryFn">,
) {
  return useQuery<UserStrategy[], Error>({
    queryKey: strategyKeys.custom(),
    queryFn: () => api.get<UserStrategy[]>("/strategies/custom"),
    staleTime: 60 * 1000,
    ...options,
  });
}

export function useCreateCustomStrategy() {
  const qc = useQueryClient();
  return useMutation<UserStrategy, Error, UserStrategyCreate>({
    mutationFn: (payload) =>
      api.post<UserStrategy>("/strategies/custom", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategyKeys.custom() });
      qc.invalidateQueries({ queryKey: strategyKeys.catalog() });
    },
  });
}

export function useUpdateCustomStrategy() {
  const qc = useQueryClient();
  return useMutation<
    UserStrategy,
    Error,
    { id: string; payload: UserStrategyUpdate }
  >({
    mutationFn: ({ id, payload }) =>
      api.put<UserStrategy>(`/strategies/custom/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategyKeys.custom() });
      qc.invalidateQueries({ queryKey: strategyKeys.catalog() });
    },
  });
}

export function useDeleteCustomStrategy() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/strategies/custom/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategyKeys.custom() });
      qc.invalidateQueries({ queryKey: strategyKeys.catalog() });
    },
  });
}

// Combo
export function useRunStrategyCombo(
  options?: Omit<
    UseMutationOptions<StrategyComboResponse, Error, StrategyComboRequest>,
    "mutationFn"
  >,
) {
  return useMutation<StrategyComboResponse, Error, StrategyComboRequest>({
    mutationFn: (req) =>
      api.post<StrategyComboResponse>("/strategies/combo", req),
    ...options,
  });
}

// Subscriptions
export function useSubscriptions(
  userId?: string | null,
  options?: Omit<
    UseQueryOptions<Subscription[], Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<Subscription[], Error>({
    queryKey: strategyKeys.subscriptions(userId),
    queryFn: () => {
      const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
      return api.get<Subscription[]>(`/strategies/subscriptions${qs}`);
    },
    staleTime: 30 * 1000,
    ...options,
  });
}

export function useCreateSubscription() {
  const qc = useQueryClient();
  return useMutation<Subscription, Error, SubscriptionCreate>({
    mutationFn: (payload) =>
      api.post<Subscription>("/strategies/subscriptions", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategyKeys.all });
    },
  });
}

export function useDeleteSubscription() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/strategies/subscriptions/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategyKeys.all });
    },
  });
}

// Favorites — purely client-side persistence in localStorage.
const FAVORITES_KEY = "trade_bot.favorite_strategies";

export function readFavoriteStrategies(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(FAVORITES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function writeFavoriteStrategies(keys: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(keys));
  } catch {
    /* ignore */
  }
}

export { ApiError };
