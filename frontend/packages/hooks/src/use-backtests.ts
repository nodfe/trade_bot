import {
  useMutation,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { api } from "@quant/api-client";

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
