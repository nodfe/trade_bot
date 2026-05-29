import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "@quant/api-client";
import { stockKeys } from "./use-stock-data";

// ---------------------------------------------------------------------------
// Types — mirror backend Pydantic schemas exactly.
// Source of truth: backend/app/modules/sync_runs/schemas.py
// ---------------------------------------------------------------------------

/** A single sync job execution record. Dates are ISO strings. */
export interface SyncRun {
  id: number;
  job_name: string;
  target: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  synced_count: number | null;
  error: string | null;
  meta_json: string | null;
}

/** A single bot command invocation record. */
export interface BotCommandLog {
  id: number;
  platform: string;
  chat_id: string;
  user_id: string | null;
  command: string;
  args_text: string | null;
  status: string;
  error: string | null;
  duration_ms: number | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const systemKeys = {
  all: ["system"] as const,
  syncRuns: (limit: number, jobName?: string) =>
    [...systemKeys.all, "sync-runs", limit, jobName ?? null] as const,
  botCommandLogs: (limit: number) =>
    [...systemKeys.all, "bot-command-logs", limit] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the most recent sync job runs. Optionally filter by job_name.
 * Auto-refreshes every 30s so the page feels live.
 */
export function useSyncRuns(
  limit: number = 50,
  jobName?: string,
  options?: Omit<
    UseQueryOptions<SyncRun[], Error, SyncRun[], ReturnType<typeof systemKeys.syncRuns>>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: systemKeys.syncRuns(limit, jobName),
    queryFn: () =>
      api.get<SyncRun[]>("/system/sync-runs", {
        params: {
          limit,
          job_name: jobName,
        },
      }),
    refetchInterval: 30 * 1000,
    ...options,
  });
}

/**
 * Fetch the most recent bot command invocations. Auto-refreshes every 60s.
 */
export function useBotCommandLogs(
  limit: number = 50,
  options?: Omit<
    UseQueryOptions<BotCommandLog[], Error, BotCommandLog[], ReturnType<typeof systemKeys.botCommandLogs>>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: systemKeys.botCommandLogs(limit),
    queryFn: () =>
      api.get<BotCommandLog[]>("/system/bot-command-logs", {
        params: { limit },
      }),
    refetchInterval: 60 * 1000,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Manual sync triggers
// ---------------------------------------------------------------------------

/** Server response shape for sync endpoints. */
export interface SyncResult {
  synced: number;
  message: string;
}

/** Logical sync job names exposed to the admin UI. */
export type SyncJobKind = "stock_list" | "dragon_tiger" | "limit_up" | "news";

const SYNC_ENDPOINTS: Record<SyncJobKind, string> = {
  stock_list: "/market/sync/stock-list",
  dragon_tiger: "/market/sync/dragon-tiger",
  limit_up: "/market/sync/limit-up",
  news: "/market/sync/news",
};

/**
 * Trigger a daily-bars sync for a single stock. Different shape from
 * `useTriggerSync` because the params are code + days instead of trade_date.
 *
 * On completion we invalidate both:
 *   - `systemKeys.all` so the sync_runs / bot_command_logs tables refresh,
 *   - `stockKeys.all` so any open kline / quote / market-overview view picks
 *     up the freshly synced bars instead of staying on stale data.
 */
export function useSyncDailyBars(
  options?: Omit<
    UseMutationOptions<SyncResult, Error, { code: string; days: number }>,
    "mutationFn"
  >,
) {
  const queryClient = useQueryClient();
  return useMutation<SyncResult, Error, { code: string; days: number }>({
    mutationFn: ({ code, days }) =>
      api.post<SyncResult>(`/market/sync/daily-bars/${code}`, undefined, {
        params: { days },
      }),
    onSettled: (...args) => {
      queryClient.invalidateQueries({ queryKey: systemKeys.all });
      queryClient.invalidateQueries({ queryKey: stockKeys.all });
      options?.onSettled?.(...args);
    },
    ...options,
  });
}

/**
 * Trigger a single sync job from the UI.
 *
 * On completion we invalidate both:
 *   - `systemKeys.all` so the recent-runs table picks up the new row,
 *   - `stockKeys.all` so dashboard / dragon-tiger / limit-up / news views
 *     re-fetch with the freshly synced data instead of showing stale rows.
 *
 * Pass a `tradeDate` (YYYY-MM-DD) for date-bound jobs (dragon_tiger / limit_up
 * / news). The stock_list endpoint ignores it.
 */
export function useTriggerSync(
  options?: Omit<
    UseMutationOptions<
      SyncResult,
      Error,
      { job: SyncJobKind; tradeDate?: string }
    >,
    "mutationFn"
  >,
) {
  const queryClient = useQueryClient();
  return useMutation<
    SyncResult,
    Error,
    { job: SyncJobKind; tradeDate?: string }
  >({
    mutationFn: ({ job, tradeDate }) =>
      api.post<SyncResult>(SYNC_ENDPOINTS[job], undefined, {
        params: tradeDate ? { trade_date: tradeDate } : undefined,
      }),
    onSettled: (...args) => {
      // Refresh both system tables (sync_runs row appears) and stock-data
      // queries (dashboard, dragon-tiger, limit-up, news pick up new rows).
      queryClient.invalidateQueries({ queryKey: systemKeys.all });
      queryClient.invalidateQueries({ queryKey: stockKeys.all });
      options?.onSettled?.(...args);
    },
    ...options,
  });
}
