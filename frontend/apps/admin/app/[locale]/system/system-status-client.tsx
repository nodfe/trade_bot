"use client"

import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  useBotCommandLogs,
  useSyncDailyBars,
  useSyncRuns,
  useTriggerSync,
  type BotCommandLog,
  type SyncJobKind,
  type SyncRun,
} from "@quant/hooks"
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Loader2,
  MessageSquare,
  PlayCircle,
  XCircle,
} from "lucide-react"

const SYNC_JOB_OPTIONS = [
  "daily_bars",
  "dragon_tiger",
  "limit_up",
  "news",
  "stock_list",
] as const

type SyncStatus = "success" | "failed" | "running" | "skipped"

function statusBadgeClass(status: string): string {
  switch (status) {
    case "success":
      return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
    case "failed":
      return "bg-destructive/10 text-destructive border-destructive/30"
    case "running":
      return "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 animate-pulse"
    case "skipped":
      return "bg-muted text-muted-foreground border-muted-foreground/30"
    default:
      return "bg-muted text-muted-foreground border-muted-foreground/30"
  }
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "-"
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const totalSeconds = Math.round(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}m ${seconds}s`
}

function makeDateFormatter(locale: string) {
  const intlLocale = locale === "zh" ? "zh-CN" : "en-US"
  return new Intl.DateTimeFormat(intlLocale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
}

function formatDateTime(iso: string | null | undefined, formatter: Intl.DateTimeFormat): string {
  if (!iso) return "-"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "-"
  return formatter.format(date)
}

function truncate(value: string | null | undefined, max: number): string {
  if (!value) return "-"
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}

type TFunc = ReturnType<typeof useTranslations<"system">>

export function SystemStatusClient() {
  const t = useTranslations("system")
  const locale = useLocale()
  const dateFormatter = makeDateFormatter(locale)

  const [jobFilter, setJobFilter] = useState<string>("")

  const { data: syncRuns, isLoading: isSyncLoading } = useSyncRuns(
    50,
    jobFilter || undefined,
    { retry: false },
  )
  const { data: botLogs, isLoading: isBotLoading } = useBotCommandLogs(50, {
    retry: false,
  })

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Manual Sync Triggers */}
      <ManualSyncCard t={t} />

      <div className="grid gap-6 xl:grid-cols-2">
        {/* Sync Job Runs */}
        <Card className="premium-glass-card border bg-background/30 shadow-md">
          <CardHeader className="pb-3 border-b border-muted/30">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <CardTitle className="font-display text-lg font-bold flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  {t("syncRuns.title")}
                </CardTitle>
                <CardDescription className="text-xs mt-1">
                  {t("syncRuns.empty")}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <label
                  htmlFor="sync-job-filter"
                  className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold"
                >
                  {t("syncRuns.filter.label")}
                </label>
                <select
                  id="sync-job-filter"
                  value={jobFilter}
                  onChange={(event) => setJobFilter(event.target.value)}
                  className="h-8 rounded-md border bg-background/60 px-2 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="">{t("syncRuns.filter.all")}</option>
                  {SYNC_JOB_OPTIONS.map((job) => (
                    <option key={job} value={job}>
                      {job}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            {isSyncLoading ? (
              <div className="h-[280px] rounded-xl border shimmer-loading opacity-60" />
            ) : syncRuns && syncRuns.length > 0 ? (
              <SyncRunsTable runs={syncRuns} t={t} dateFormatter={dateFormatter} />
            ) : (
              <EmptyState message={t("syncRuns.empty")} />
            )}
          </CardContent>
        </Card>

        {/* Bot Command Logs */}
        <Card className="premium-glass-card border bg-background/30 shadow-md">
          <CardHeader className="pb-3 border-b border-muted/30">
            <CardTitle className="font-display text-lg font-bold flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" />
              {t("botLogs.title")}
            </CardTitle>
            <CardDescription className="text-xs mt-1">
              {t("botLogs.empty")}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {isBotLoading ? (
              <div className="h-[280px] rounded-xl border shimmer-loading opacity-60" />
            ) : botLogs && botLogs.length > 0 ? (
              <BotLogsTable logs={botLogs} t={t} dateFormatter={dateFormatter} />
            ) : (
              <EmptyState message={t("botLogs.empty")} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ManualSyncCard({ t }: { t: TFunc }) {
  const [tradeDate, setTradeDate] = useState<string>("")
  const [pendingJob, setPendingJob] = useState<SyncJobKind | null>(null)
  const [lastResult, setLastResult] = useState<{
    job: SyncJobKind | "daily_bars"
    ok: boolean
    message: string
  } | null>(null)

  const [klineCode, setKlineCode] = useState<string>("600519")
  const [klineDays, setKlineDays] = useState<number>(120)

  const trigger = useTriggerSync({
    onMutate: ({ job }) => {
      setPendingJob(job)
      setLastResult(null)
    },
    onSuccess: (data, variables) => {
      setLastResult({ job: variables.job, ok: true, message: data.message })
    },
    onError: (error, variables) => {
      const reason =
        error instanceof Error ? error.message : t("manualSync.errors.unknown")
      setLastResult({ job: variables.job, ok: false, message: reason })
    },
    onSettled: () => {
      setPendingJob(null)
    },
  })

  const klineSync = useSyncDailyBars({
    onMutate: () => {
      setLastResult(null)
    },
    onSuccess: (data) => {
      setLastResult({ job: "daily_bars", ok: true, message: data.message })
    },
    onError: (error) => {
      const reason =
        error instanceof Error ? error.message : t("manualSync.errors.unknown")
      setLastResult({ job: "daily_bars", ok: false, message: reason })
    },
  })

  const jobs: { kind: SyncJobKind; needsDate: boolean }[] = [
    { kind: "stock_list", needsDate: false },
    { kind: "dragon_tiger", needsDate: true },
    { kind: "limit_up", needsDate: true },
    { kind: "news", needsDate: true },
  ]

  return (
    <Card className="premium-glass-card border bg-background/30 shadow-md">
      <CardHeader className="pb-3 border-b border-muted/30">
        <CardTitle className="font-display text-lg font-bold flex items-center gap-2">
          <PlayCircle className="h-4 w-4 text-primary" />
          {t("manualSync.title")}
        </CardTitle>
        <CardDescription className="text-xs mt-1">
          {t("manualSync.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="manual-sync-date"
              className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              {t("manualSync.date.label")}
            </label>
            <input
              id="manual-sync-date"
              type="date"
              value={tradeDate}
              onChange={(event) => setTradeDate(event.target.value)}
              className="h-9 rounded-md border bg-background/60 px-2 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <span className="text-[10px] text-muted-foreground">
              {t("manualSync.date.hint")}
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            {jobs.map(({ kind, needsDate }) => {
              const isPending = pendingJob === kind
              return (
                <Button
                  key={kind}
                  size="sm"
                  variant="outline"
                  disabled={trigger.isPending || klineSync.isPending}
                  onClick={() =>
                    trigger.mutate({
                      job: kind,
                      tradeDate: needsDate && tradeDate ? tradeDate : undefined,
                    })
                  }
                >
                  {isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <PlayCircle className="h-3.5 w-3.5" />
                  )}
                  {t(`manualSync.jobs.${kind}`)}
                </Button>
              )
            })}
          </div>
        </div>

        {/* Daily bars (per-stock) row */}
        <div className="flex flex-wrap items-end gap-3 border-t border-muted/30 pt-4">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="manual-sync-code"
              className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              {t("manualSync.daily.codeLabel")}
            </label>
            <input
              id="manual-sync-code"
              type="text"
              value={klineCode}
              onChange={(event) => setKlineCode(event.target.value.trim())}
              placeholder="600519"
              className="h-9 w-32 rounded-md border bg-background/60 px-2 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label
              htmlFor="manual-sync-days"
              className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold"
            >
              {t("manualSync.daily.daysLabel")}
            </label>
            <input
              id="manual-sync-days"
              type="number"
              min={1}
              max={3650}
              value={klineDays}
              onChange={(event) =>
                setKlineDays(Math.max(1, Math.min(3650, Number(event.target.value) || 1)))
              }
              className="h-9 w-24 rounded-md border bg-background/60 px-2 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={
              trigger.isPending || klineSync.isPending || !klineCode
            }
            onClick={() =>
              klineSync.mutate({ code: klineCode, days: klineDays })
            }
          >
            {klineSync.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <PlayCircle className="h-3.5 w-3.5" />
            )}
            {t("manualSync.daily.button")}
          </Button>
          <span className="text-[10px] text-muted-foreground self-center">
            {t("manualSync.daily.hint")}
          </span>
        </div>

        {lastResult && (
          <div
            className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${
              lastResult.ok
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : "border-destructive/30 bg-destructive/10 text-destructive"
            }`}
          >
            {lastResult.ok ? (
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 mt-0.5 shrink-0" />
            )}
            <span className="font-mono">
              <span className="font-semibold mr-1">
                {t(`manualSync.jobs.${lastResult.job}`)}:
              </span>
              {lastResult.message}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 flex flex-col items-center gap-2">
      <AlertCircle className="h-5 w-5 text-muted-foreground/60" />
      <span>{message}</span>
    </div>
  )
}

function SyncRunsTable({
  runs,
  t,
  dateFormatter,
}: {
  runs: SyncRun[]
  t: TFunc
  dateFormatter: Intl.DateTimeFormat
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-muted/40 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
            <th className="text-left font-semibold py-2 px-2">{t("syncRuns.columns.job")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("syncRuns.columns.target")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("syncRuns.columns.status")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("syncRuns.columns.started")}</th>
            <th className="text-right font-semibold py-2 px-2">{t("syncRuns.columns.duration")}</th>
            <th className="text-right font-semibold py-2 px-2">{t("syncRuns.columns.synced")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("syncRuns.columns.error")}</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              className="border-b border-muted/20 hover:bg-muted/10 transition-colors"
            >
              <td className="py-2 px-2 font-mono text-foreground">{run.job_name}</td>
              <td className="py-2 px-2 text-muted-foreground max-w-[140px] truncate" title={run.target ?? ""}>
                {run.target ?? "-"}
              </td>
              <td className="py-2 px-2">
                <SyncStatusBadge status={run.status} t={t} />
              </td>
              <td className="py-2 px-2 font-mono text-muted-foreground whitespace-nowrap">
                {formatDateTime(run.started_at, dateFormatter)}
              </td>
              <td className="py-2 px-2 font-mono text-right text-muted-foreground">
                {formatDuration(run.duration_ms)}
              </td>
              <td className="py-2 px-2 font-mono text-right text-foreground">
                {run.synced_count ?? "-"}
              </td>
              <td
                className="py-2 px-2 max-w-[200px] truncate text-destructive/90"
                title={run.error ?? ""}
              >
                {run.error ? truncate(run.error, 60) : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SyncStatusBadge({ status, t }: { status: string; t: TFunc }) {
  const knownStatuses: SyncStatus[] = ["success", "failed", "running", "skipped"]
  const isKnown = (knownStatuses as readonly string[]).includes(status)
  const label = isKnown
    ? t(`syncRuns.status.${status as SyncStatus}`)
    : status
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${statusBadgeClass(status)}`}
    >
      {label}
    </span>
  )
}

function BotLogsTable({
  logs,
  t,
  dateFormatter,
}: {
  logs: BotCommandLog[]
  t: TFunc
  dateFormatter: Intl.DateTimeFormat
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-muted/40 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.platform")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.command")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.args")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.chat")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.user")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.status")}</th>
            <th className="text-right font-semibold py-2 px-2">{t("botLogs.columns.duration")}</th>
            <th className="text-left font-semibold py-2 px-2">{t("botLogs.columns.at")}</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr
              key={log.id}
              className="border-b border-muted/20 hover:bg-muted/10 transition-colors"
            >
              <td className="py-2 px-2 font-mono text-foreground uppercase text-[10px]">
                {log.platform}
              </td>
              <td className="py-2 px-2 font-mono text-foreground">{log.command}</td>
              <td
                className="py-2 px-2 font-mono text-muted-foreground max-w-[180px] truncate"
                title={log.args_text ?? ""}
              >
                {log.args_text ? truncate(log.args_text, 40) : "-"}
              </td>
              <td
                className="py-2 px-2 font-mono text-muted-foreground max-w-[120px] truncate"
                title={log.chat_id}
              >
                {truncate(log.chat_id, 12)}
              </td>
              <td
                className="py-2 px-2 font-mono text-muted-foreground max-w-[120px] truncate"
                title={log.user_id ?? ""}
              >
                {log.user_id ? truncate(log.user_id, 12) : "-"}
              </td>
              <td className="py-2 px-2">
                <SyncStatusBadge status={log.status} t={t} />
              </td>
              <td className="py-2 px-2 font-mono text-right text-muted-foreground">
                {formatDuration(log.duration_ms)}
              </td>
              <td className="py-2 px-2 font-mono text-muted-foreground whitespace-nowrap">
                {formatDateTime(log.created_at, dateFormatter)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
