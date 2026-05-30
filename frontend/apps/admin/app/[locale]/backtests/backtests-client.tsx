"use client"

import { useMemo, useState } from "react"
import { useLocale, useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  useRunBacktest,
  type BacktestResult,
  type BacktestTrade,
} from "@quant/hooks"
import {
  Activity,
  AlertCircle,
  BarChart3,
  FlaskConical,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function formatPct(value: number | null | undefined, na: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return na
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

function formatCurrency(value: number, locale: string): string {
  try {
    return new Intl.NumberFormat(locale === "zh" ? "zh-CN" : "en-US", {
      style: "currency",
      currency: "CNY",
      maximumFractionDigits: 0,
    }).format(value)
  } catch {
    return value.toFixed(2)
  }
}

// A-share 红涨绿跌
function returnColorClass(value: number | null): string {
  if (value === null || value === undefined) return "text-muted-foreground"
  if (value > 0) return "text-stock-up"
  if (value < 0) return "text-stock-down"
  return "text-foreground"
}

export function BacktestsClient() {
  const t = useTranslations("backtests")
  const locale = useLocale()

  const [code, setCode] = useState("600519")
  const [startDate, setStartDate] = useState(isoDaysAgo(365))
  const [endDate, setEndDate] = useState(todayIso())
  const [fastPeriod, setFastPeriod] = useState(5)
  const [slowPeriod, setSlowPeriod] = useState(20)
  const [initialCapital, setInitialCapital] = useState(100_000)
  const [validationError, setValidationError] = useState<string | null>(null)

  const { mutate, data, error, isPending, reset } = useRunBacktest()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setValidationError(null)
    if (!code.trim()) {
      setValidationError(t("errors.code_required"))
      return
    }
    if (!startDate || !endDate) {
      setValidationError(t("errors.dates_required"))
      return
    }
    if (startDate >= endDate) {
      setValidationError(t("errors.dates_invalid"))
      return
    }
    if (fastPeriod >= slowPeriod) {
      setValidationError(t("errors.periods_invalid"))
      return
    }
    reset()
    mutate({
      code: code.trim(),
      start_date: startDate,
      end_date: endDate,
      strategy: "ma_cross",
      fast_period: fastPeriod,
      slow_period: slowPeriod,
      initial_capital: initialCapital,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Configuration Form */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {t("form.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("form.description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <FieldLabel label={t("form.code")}>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder={t("form.code_placeholder")}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("form.start_date")}>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("form.end_date")}>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("form.strategy")}>
                <select
                  value="ma_cross"
                  disabled
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm"
                >
                  <option value="ma_cross">{t("form.strategy_ma_cross")}</option>
                </select>
              </FieldLabel>
              <FieldLabel label={t("form.fast_period")}>
                <input
                  type="number"
                  min={2}
                  max={120}
                  value={fastPeriod}
                  onChange={(e) => setFastPeriod(Number(e.target.value))}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("form.slow_period")}>
                <input
                  type="number"
                  min={3}
                  max={250}
                  value={slowPeriod}
                  onChange={(e) => setSlowPeriod(Number(e.target.value))}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("form.initial_capital")}>
                <input
                  type="number"
                  min={1000}
                  step={1000}
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
            </div>

            {validationError ? (
              <div className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{validationError}</span>
              </div>
            ) : null}

            {error ? (
              <div className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{t("errors.request_failed")}</span>
              </div>
            ) : null}

            <div className="flex justify-end">
              <Button type="submit" disabled={isPending} className="gap-2">
                {isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {t("form.running")}
                  </>
                ) : (
                  <>
                    <FlaskConical className="h-3.5 w-3.5" />
                    {t("form.submit")}
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {data ? (
        <BacktestResults result={data} locale={locale} />
      ) : !isPending ? (
        <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none">
          <CardContent className="pt-6 pb-6">
            <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <BarChart3 className="h-4 w-4" />
              <span>{t("empty")}</span>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function FieldLabel({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <label className="space-y-1.5 block">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
        {label}
      </span>
      {children}
    </label>
  )
}

function BacktestResults({
  result,
  locale,
}: {
  result: BacktestResult
  locale: string
}) {
  const t = useTranslations("backtests")
  const na = t("results.na")

  const kpis: { label: string; value: string; valueClass: string }[] = useMemo(
    () => [
      {
        label: t("results.total_return"),
        value: formatPct(result.total_return_pct, na),
        valueClass: returnColorClass(result.total_return_pct),
      },
      {
        label: t("results.annualized_return"),
        value: formatPct(result.annualized_return_pct, na),
        valueClass: returnColorClass(result.annualized_return_pct),
      },
      {
        label: t("results.win_rate"),
        value: `${result.win_rate_pct.toFixed(2)}%`,
        valueClass: "text-foreground",
      },
      {
        label: t("results.max_drawdown"),
        value: `-${result.max_drawdown_pct.toFixed(2)}%`,
        valueClass: "text-stock-down",
      },
      {
        label: t("results.trade_count"),
        value: String(result.trade_count),
        valueClass: "text-foreground",
      },
      {
        label: t("results.final_equity"),
        value: formatCurrency(result.final_equity, locale),
        valueClass: "text-foreground",
      },
      {
        label: t("results.initial_capital"),
        value: formatCurrency(result.initial_capital, locale),
        valueClass: "text-muted-foreground",
      },
    ],
    [result, locale, na, t],
  )

  return (
    <div className="space-y-6">
      {/* KPI grid */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            {t("results.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {kpis.map((kpi) => (
              <div
                key={kpi.label}
                className="rounded-xl border bg-background/20 p-3 space-y-1"
              >
                <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                  {kpi.label}
                </div>
                <div className={`text-lg font-bold font-mono ${kpi.valueClass}`}>
                  {kpi.value}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Equity curve */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            {t("results.equity_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("results.equity_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="h-[280px] w-full">
            <ResponsiveContainer>
              <AreaChart
                data={result.equity_curve}
                margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="bt-equity-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  minTickGap={32}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  domain={["auto", "auto"]}
                  tickFormatter={(v: number) =>
                    v >= 10_000 ? `${(v / 10_000).toFixed(1)}w` : v.toFixed(0)
                  }
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => [
                    formatCurrency(value, locale),
                    t("results.final_equity"),
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  fill="url(#bt-equity-fill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Trades */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-primary" />
            {t("results.trades_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("results.trades_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          {result.trades.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center text-xs text-muted-foreground bg-muted/10">
              {t("results.no_trades")}
            </div>
          ) : (
            <TradesTable trades={result.trades} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  const t = useTranslations("backtests.results.columns")
  return (
    <div className="overflow-x-auto rounded-lg border bg-background/20">
      <table className="w-full text-xs">
        <thead className="bg-muted/30">
          <tr className="text-left text-[10px] uppercase tracking-[0.12em] text-muted-foreground/80">
            <th className="px-3 py-2 font-semibold">{t("entry_date")}</th>
            <th className="px-3 py-2 font-semibold text-right">{t("entry_price")}</th>
            <th className="px-3 py-2 font-semibold">{t("exit_date")}</th>
            <th className="px-3 py-2 font-semibold text-right">{t("exit_price")}</th>
            <th className="px-3 py-2 font-semibold text-right">{t("return")}</th>
            <th className="px-3 py-2 font-semibold text-right">{t("holding_days")}</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, idx) => (
            <tr
              key={`${trade.entry_date}-${trade.exit_date}-${idx}`}
              className="border-t border-muted/20 font-mono"
            >
              <td className="px-3 py-2">{trade.entry_date}</td>
              <td className="px-3 py-2 text-right">{trade.entry_price.toFixed(2)}</td>
              <td className="px-3 py-2">{trade.exit_date}</td>
              <td className="px-3 py-2 text-right">{trade.exit_price.toFixed(2)}</td>
              <td
                className={`px-3 py-2 text-right font-semibold ${returnColorClass(trade.return_pct)}`}
              >
                {trade.return_pct > 0 ? "+" : ""}
                {trade.return_pct.toFixed(2)}%
              </td>
              <td className="px-3 py-2 text-right">{trade.holding_days}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
