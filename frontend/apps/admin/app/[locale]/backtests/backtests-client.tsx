"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
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
  ApiError,
  useEligibleBacktestCodes,
  useRunBacktest,
  useRunScreenerBacktest,
  useScreenerPreview,
  useStockKline,
  type BacktestResult,
  type BacktestTrade,
  type BenchmarkMode,
  type EligibleCode,
  type RebalanceCadence,
  type RebalanceTradeReason,
  type ScreenerBacktestRequest,
  type ScreenerBacktestResult,
  type ScreenerBacktestTrade,
  type ScreenerType,
  type WeightingMode,
} from "@quant/hooks"
import { KLineChart, type KLineMarker } from "@quant/charts"
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Coins,
  FlaskConical,
  Layers,
  LineChart as LineChartIcon,
  Loader2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
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

type Mode = "single" | "screener"

export function BacktestsClient() {
  const t = useTranslations("backtests")
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialMode = (searchParams?.get("mode") === "screener" ? "screener" : "single") as Mode
  const [mode, setMode] = useState<Mode>(initialMode)

  // Sync URL ?mode=
  useEffect(() => {
    const current = searchParams?.get("mode")
    if (current !== mode) {
      const params = new URLSearchParams(searchParams?.toString() ?? "")
      params.set("mode", mode)
      router.replace(`?${params.toString()}`, { scroll: false })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {mode === "screener" ? t("screener.subtitle") : t("subtitle")}
        </p>
      </div>

      {/* Tabs */}
      <div className="inline-flex rounded-lg border bg-background/30 p-1 shadow-sm">
        <TabButton active={mode === "single"} onClick={() => setMode("single")}>
          {t("tabs.single")}
        </TabButton>
        <TabButton
          active={mode === "screener"}
          onClick={() => setMode("screener")}
        >
          {t("tabs.screener")}
        </TabButton>
      </div>

      {mode === "single" ? <SingleBacktestPanel /> : <ScreenerBacktestPanel />}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-4 py-1.5 text-sm font-medium rounded-md transition-all " +
        (active
          ? "bg-primary text-primary-foreground shadow"
          : "text-muted-foreground hover:text-foreground")
      }
    >
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Single Stock Backtest Panel (existing behavior preserved)
// ---------------------------------------------------------------------------

function SingleBacktestPanel() {
  const t = useTranslations("backtests")
  const locale = useLocale()

  const [code, setCode] = useState("600519")
  const [startDate, setStartDate] = useState(isoDaysAgo(120))
  const [endDate, setEndDate] = useState(todayIso())
  const [fastPeriod, setFastPeriod] = useState(5)
  const [slowPeriod, setSlowPeriod] = useState(20)
  const [initialCapital, setInitialCapital] = useState(100_000)
  const [validationError, setValidationError] = useState<string | null>(null)

  const { mutate, data, error, isPending, reset } = useRunBacktest()
  const { data: eligibleCodes, isLoading: eligibleLoading } =
    useEligibleBacktestCodes()

  const userEditedCodeRef = useRef(false)
  useEffect(() => {
    if (userEditedCodeRef.current) return
    if (!eligibleCodes || eligibleCodes.length === 0) return
    const first = eligibleCodes[0]
    if (first && first.code !== code) {
      setCode(first.code)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eligibleCodes])

  const eligibleByCode = useMemo(() => {
    const map = new Map<string, EligibleCode>()
    if (eligibleCodes) {
      for (const item of eligibleCodes) {
        map.set(item.code, item)
      }
    }
    return map
  }, [eligibleCodes])

  const resolvedName = eligibleByCode.get(code.trim())?.name ?? null

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

  const isInsufficientBars =
    error instanceof ApiError && error.status === 404
  const errorMessage = error
    ? isInsufficientBars
      ? t("errors.insufficient_bars")
      : t("errors.request_failed")
    : null

  return (
    <>
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
                  onChange={(e) => {
                    userEditedCodeRef.current = true
                    setCode(e.target.value)
                  }}
                  placeholder={t("form.code_placeholder")}
                  list="bt-eligible-codes"
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
                {eligibleCodes && eligibleCodes.length > 0 ? (
                  <datalist id="bt-eligible-codes">
                    {eligibleCodes.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.name}
                      </option>
                    ))}
                  </datalist>
                ) : null}
                {!eligibleLoading ? (
                  <div className="flex items-center justify-between gap-2 pt-1 text-[10px] text-muted-foreground/80">
                    {eligibleCodes && eligibleCodes.length > 0 ? (
                      <span>
                        {t("form.code_eligible_count", {
                          count: eligibleCodes.length,
                        })}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <span>{t("form.code_eligible_empty")}</span>
                        <Link
                          href={`/${locale}/system`}
                          className="underline underline-offset-2 hover:text-primary"
                        >
                          {t("form.code_eligible_link")}
                        </Link>
                      </span>
                    )}
                    {resolvedName ? (
                      <span className="truncate text-foreground/70">
                        {t("form.code_resolved_name", { name: resolvedName })}
                      </span>
                    ) : null}
                  </div>
                ) : null}
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
                  aria-disabled="true"
                  title={t("form.strategy_locked_hint")}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm cursor-not-allowed opacity-70"
                >
                  <option value="ma_cross">{t("form.strategy_ma_cross")}</option>
                </select>
                <div className="pt-1 text-[10px] text-muted-foreground/80">
                  {t("form.strategy_locked_hint")}
                </div>
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

            {errorMessage ? (
              <div className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{errorMessage}</span>
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
        <BacktestResults
          result={data}
          locale={locale}
          resolvedName={eligibleByCode.get(data.code)?.name ?? null}
        />
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
    </>
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
  resolvedName,
}: {
  result: BacktestResult
  locale: string
  resolvedName: string | null
}) {
  const t = useTranslations("backtests")
  const na = t("results.na")

  const titleText = resolvedName
    ? t("results.title_with_name", { name: resolvedName, code: result.code })
    : t("results.title")

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
      {/* No-trades banner */}
      {result.trade_count === 0 ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="text-sm font-semibold text-amber-700 dark:text-amber-300">
              {t("results.no_trades_banner_title")}
            </div>
            <div className="text-xs text-amber-700/90 dark:text-amber-200/80 leading-relaxed">
              {t("results.no_trades_banner_hint")}
            </div>
          </div>
        </div>
      ) : null}

      {/* KPI grid */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            {titleText}
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

// ---------------------------------------------------------------------------
// Screener Backtest Panel
// ---------------------------------------------------------------------------

const SCREENER_TYPES: ScreenerType[] = [
  "strong_uptrend",
  "volume_breakout",
  "pullback_watch",
  "first_limit_up_low",
  "leader_streak",
  "zt_relay",
  "lhb_follow",
]
const REBALANCE_OPTIONS: RebalanceCadence[] = [
  "daily",
  "weekly",
  "biweekly",
  "monthly",
]
const WEIGHTING_OPTIONS: WeightingMode[] = ["equal", "score"]
const BENCHMARK_OPTIONS: BenchmarkMode[] = ["none", "universe_buy_hold"]

function ScreenerBacktestPanel() {
  const t = useTranslations("backtests")
  const tScreeners = useTranslations("screeners")
  const locale = useLocale()

  const [screenType, setScreenType] = useState<ScreenerType>("strong_uptrend")
  const [startDate, setStartDate] = useState(isoDaysAgo(180))
  const [endDate, setEndDate] = useState(todayIso())
  const [rebalance, setRebalance] = useState<RebalanceCadence>("weekly")
  const [topN, setTopN] = useState(10)
  const [weighting, setWeighting] = useState<WeightingMode>("equal")
  const [initialCapital, setInitialCapital] = useState(100_000)
  const [stopLoss, setStopLoss] = useState<string>("")
  const [takeProfit, setTakeProfit] = useState<string>("")
  // Decimal cost rates (e.g. 0.00025); UI display shows ×100.
  const [commissionRate, setCommissionRate] = useState(0.00025)
  const [stampDutyRate, setStampDutyRate] = useState(0.001)
  const [slippageRate, setSlippageRate] = useState(0.001)
  const [benchmark, setBenchmark] = useState<BenchmarkMode>("universe_buy_hold")
  const [markets, setMarkets] = useState<string[]>([])
  const [includeSt, setIncludeSt] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const { mutate, data, error, isPending, reset } = useRunScreenerBacktest()

  const previewQuery = useScreenerPreview(screenType, endDate, true)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setValidationError(null)
    if (!startDate || !endDate) {
      setValidationError(t("errors.dates_required"))
      return
    }
    if (startDate >= endDate) {
      setValidationError(t("errors.dates_invalid"))
      return
    }
    reset()
    const payload: ScreenerBacktestRequest = {
      screen_type: screenType,
      start_date: startDate,
      end_date: endDate,
      rebalance,
      top_n: topN,
      weighting,
      initial_capital: initialCapital,
      commission_rate: commissionRate,
      stamp_duty_rate: stampDutyRate,
      slippage_rate: slippageRate,
      stop_loss_pct: stopLoss ? Number(stopLoss) : null,
      take_profit_pct: takeProfit ? Number(takeProfit) : null,
      benchmark,
      ...((markets.length > 0 || includeSt)
        ? {
            screen_params_override: {
              ...(markets.length > 0 ? { markets } : {}),
              ...(includeSt ? { include_st: true } : {}),
            },
          }
        : {}),
    }
    mutate(payload)
  }

  const errorMessage = error
    ? error instanceof ApiError
      ? error.message || t("errors.request_failed")
      : t("errors.request_failed")
    : null

  return (
    <>
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {t("form.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("screener.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <FieldLabel label={t("screener.form.strategy")}>
                <select
                  value={screenType}
                  onChange={(e) => setScreenType(e.target.value as ScreenerType)}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm"
                >
                  {SCREENER_TYPES.map((opt) => (
                    <option key={opt} value={opt}>
                      {tScreeners(`options.${opt}.label`)}
                    </option>
                  ))}
                </select>
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
              <FieldLabel label={t("screener.form.rebalance")}>
                <select
                  value={rebalance}
                  onChange={(e) =>
                    setRebalance(e.target.value as RebalanceCadence)
                  }
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm"
                >
                  {REBALANCE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {t(`screener.form.rebalance_options.${opt}`)}
                    </option>
                  ))}
                </select>
              </FieldLabel>
              <FieldLabel label={t("screener.form.top_n")}>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={topN}
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("screener.form.weighting")}>
                <select
                  value={weighting}
                  onChange={(e) =>
                    setWeighting(e.target.value as WeightingMode)
                  }
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm"
                >
                  {WEIGHTING_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {t(`screener.form.weighting_options.${opt}`)}
                    </option>
                  ))}
                </select>
              </FieldLabel>
              <FieldLabel label={t("screener.form.initial_capital")}>
                <input
                  type="number"
                  min={1000}
                  step={1000}
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                />
              </FieldLabel>
              <FieldLabel label={t("screener.form.benchmark")}>
                <select
                  value={benchmark}
                  onChange={(e) => setBenchmark(e.target.value as BenchmarkMode)}
                  className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm"
                >
                  {BENCHMARK_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {t(`screener.form.benchmark_options.${opt}`)}
                    </option>
                  ))}
                </select>
              </FieldLabel>
            </div>

            {/* Market segment filter */}
            <div className="rounded-xl border bg-background/20 p-3 space-y-3">
              <div className="text-[11px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                {t("screener.form.markets_section_title")}
              </div>
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    { key: "main_sh", value: "main_sh" },
                    { key: "main_sz", value: "main_sz" },
                    { key: "chinext", value: "chinext" },
                    { key: "star", value: "star" },
                    { key: "bse", value: "bse" },
                  ] as const
                ).map((opt) => {
                  const checked = markets.includes(opt.value)
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() =>
                        setMarkets((prev) =>
                          prev.includes(opt.value)
                            ? prev.filter((m) => m !== opt.value)
                            : [...prev, opt.value],
                        )
                      }
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        checked
                          ? "border-primary bg-primary/15 text-primary"
                          : "border-border bg-background/40 text-muted-foreground hover:bg-background/60"
                      }`}
                    >
                      {t(`screener.form.markets.${opt.key}`)}
                    </button>
                  )
                })}
                <button
                  type="button"
                  onClick={() => setIncludeSt((v) => !v)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                    includeSt
                      ? "border-primary bg-primary/15 text-primary"
                      : "border-border bg-background/40 text-muted-foreground hover:bg-background/60"
                  }`}
                >
                  {t("screener.form.markets.st")}
                </button>
              </div>
              <div className="text-[11px] text-muted-foreground/80">
                {t("screener.form.markets_hint")}
              </div>
            </div>

            {/* Risk controls (optional) */}
            <div className="rounded-xl border bg-background/20 p-3 space-y-3">
              <div className="text-[11px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                {t("screener.form.risk_section_title")}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <FieldLabel
                  label={`${t("screener.form.stop_loss")} ${t("screener.form.optional_hint")}`}
                >
                  <input
                    type="number"
                    min={0.5}
                    max={50}
                    step={0.5}
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                  />
                </FieldLabel>
                <FieldLabel
                  label={`${t("screener.form.take_profit")} ${t("screener.form.optional_hint")}`}
                >
                  <input
                    type="number"
                    min={0.5}
                    max={200}
                    step={0.5}
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(e.target.value)}
                    className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                  />
                </FieldLabel>
              </div>
            </div>

            {/* Cost model */}
            <details className="rounded-xl border bg-background/20 p-3 space-y-3">
              <summary className="text-[11px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 cursor-pointer">
                {t("screener.form.cost_advanced_title")}
              </summary>
              <div className="pt-3 grid gap-4 md:grid-cols-3">
                <FieldLabel label={t("screener.form.commission_rate")}>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.001}
                    value={(commissionRate * 100).toFixed(4)}
                    onChange={(e) =>
                      setCommissionRate(Number(e.target.value) / 100)
                    }
                    className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                  />
                </FieldLabel>
                <FieldLabel label={t("screener.form.stamp_duty_rate")}>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={(stampDutyRate * 100).toFixed(4)}
                    onChange={(e) =>
                      setStampDutyRate(Number(e.target.value) / 100)
                    }
                    className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                  />
                </FieldLabel>
                <FieldLabel label={t("screener.form.slippage_rate")}>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={(slippageRate * 100).toFixed(4)}
                    onChange={(e) =>
                      setSlippageRate(Number(e.target.value) / 100)
                    }
                    className="w-full rounded-md border bg-background/40 px-3 py-2 text-sm font-mono"
                  />
                </FieldLabel>
              </div>
              <p className="pt-2 text-[10px] text-muted-foreground/80">
                {t("screener.form.cost_advanced_hint")}
              </p>
            </details>

            {/* Preview chips */}
            <ScreenerPreviewRow query={previewQuery} />

            {validationError ? (
              <div className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{validationError}</span>
              </div>
            ) : null}

            {errorMessage ? (
              <div className="flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{errorMessage}</span>
              </div>
            ) : null}

            <div className="flex justify-end">
              <Button type="submit" disabled={isPending} className="gap-2">
                {isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {t("screener.form.running")}
                  </>
                ) : (
                  <>
                    <FlaskConical className="h-3.5 w-3.5" />
                    {t("screener.form.submit")}
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {data ? (
        <ScreenerBacktestResults result={data} locale={locale} />
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
    </>
  )
}

function ScreenerPreviewRow({
  query,
}: {
  query: ReturnType<typeof useScreenerPreview>
}) {
  const t = useTranslations("backtests.screener.preview")
  const items = query.data ?? []
  return (
    <div className="rounded-xl border bg-background/20 p-3 space-y-2">
      <div className="text-[11px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
        {t("title")}
      </div>
      {query.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>{t("loading")}</span>
        </div>
      ) : items.length === 0 ? (
        <div className="text-xs text-muted-foreground">{t("empty")}</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.slice(0, 5).map((it) => (
            <span
              key={it.symbol}
              className="inline-flex items-center gap-1.5 rounded-full border bg-background/40 px-2.5 py-1 text-[11px] font-mono"
            >
              <span className="font-semibold">{it.symbol}</span>
              <span className="text-muted-foreground">{it.name}</span>
              {it.return_20d_pct != null ? (
                <span className={returnColorClass(it.return_20d_pct)}>
                  {formatPct(it.return_20d_pct, "")}
                </span>
              ) : null}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ScreenerBacktestResults({
  result,
  locale,
}: {
  result: ScreenerBacktestResult
  locale: string
}) {
  const t = useTranslations("backtests")
  const tScreeners = useTranslations("screeners")
  const na = t("results.na")

  const strategyLabel = useMemo(() => {
    try {
      return tScreeners(`options.${result.screen_type}.label`)
    } catch {
      return result.screen_type
    }
  }, [result.screen_type, tScreeners])

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

  // Equity + benchmark merged for chart consumption.
  const equityChartData = useMemo(() => {
    const benchByDate = new Map<string, number>()
    if (result.benchmark_curve) {
      for (const p of result.benchmark_curve) {
        benchByDate.set(p.date, p.value)
      }
    }
    return result.equity_curve.map((p) => ({
      date: p.date,
      strategy: p.value,
      benchmark: benchByDate.get(p.date) ?? null,
    }))
  }, [result.equity_curve, result.benchmark_curve])

  const holdingsTimeline = useMemo(
    () =>
      result.holdings_history.map((s) => ({
        date: s.date,
        count: s.holdings.length,
      })),
    [result.holdings_history],
  )

  return (
    <div className="space-y-6">
      {/* KPI grid */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            {strategyLabel}
            <span className="text-muted-foreground/70 font-normal">
              · {result.rebalance} · top {result.top_n}
            </span>
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

      {/* Equity curve + benchmark */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            {t("results.equity_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {result.benchmark_curve
              ? t("results.equity_description")
              : t("screener.results.no_benchmark")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="h-[300px] w-full">
            <ResponsiveContainer>
              <AreaChart
                data={equityChartData}
                margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="bt-screener-equity-fill" x1="0" y1="0" x2="0" y2="1">
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
                  formatter={(value: number, name: string) => {
                    if (value == null) return ["-", name]
                    return [formatCurrency(value, locale), name]
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="strategy"
                  name={t("screener.results.strategy_label")}
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  fill="url(#bt-screener-equity-fill)"
                />
                {result.benchmark_curve ? (
                  <Area
                    type="monotone"
                    dataKey="benchmark"
                    name={t("screener.results.benchmark_label")}
                    stroke="currentColor"
                    strokeOpacity={0.45}
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    fill="transparent"
                  />
                ) : null}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Drawdown */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-stock-down" />
            {t("screener.results.drawdown_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("screener.results.drawdown_desc")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="h-[200px] w-full">
            <ResponsiveContainer>
              <AreaChart
                data={result.drawdown_curve}
                margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="bt-screener-dd-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-stock-down)" stopOpacity={0.05} />
                    <stop offset="100%" stopColor="var(--color-stock-down)" stopOpacity={0.4} />
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
                  tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => [
                    `${value.toFixed(2)}%`,
                    t("results.max_drawdown"),
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="drawdown_pct"
                  stroke="var(--color-stock-down)"
                  strokeWidth={1.5}
                  fill="url(#bt-screener-dd-fill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Holdings timeline */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            {t("screener.results.holdings_timeline_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("screener.results.holdings_timeline_desc")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="h-[200px] w-full">
            <ResponsiveContainer>
              <LineChart
                data={holdingsTimeline}
                margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  minTickGap={32}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Cost breakdown */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Coins className="h-4 w-4 text-primary" />
            {t("screener.results.costs_title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <CostStat
              label={t("screener.results.total_commission")}
              value={formatCurrency(result.costs.total_commission, locale)}
            />
            <CostStat
              label={t("screener.results.total_stamp_duty")}
              value={formatCurrency(result.costs.total_stamp_duty, locale)}
            />
            <CostStat
              label={t("screener.results.total_slippage")}
              value={formatCurrency(result.costs.total_slippage_cost, locale)}
            />
            <CostStat
              label={t("screener.results.cost_drag")}
              value={`${result.costs.cost_drag_pct.toFixed(2)}%`}
              valueClass="text-stock-down"
            />
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
        </CardHeader>
        <CardContent className="pt-4">
          {result.trades.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center text-xs text-muted-foreground bg-muted/10">
              {t("results.no_trades")}
            </div>
          ) : (
            <ScreenerTradesTable trades={result.trades} />
          )}
        </CardContent>
      </Card>

      {/* Holdings history accordion */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            {t("screener.results.holdings_history_title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 space-y-2">
          {result.holdings_history.map((snap) => (
            <HoldingsAccordionItem key={snap.date} snapshot={snap} locale={locale} />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

function CostStat({
  label,
  value,
  valueClass = "text-foreground",
}: {
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div className="rounded-xl border bg-background/20 p-3 space-y-1">
      <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
        {label}
      </div>
      <div className={`text-lg font-bold font-mono ${valueClass}`}>{value}</div>
    </div>
  )
}

const EXIT_REASON_BADGE: Record<RebalanceTradeReason, string> = {
  screener_pick: "bg-muted text-muted-foreground",
  screener_drop: "bg-blue-500/20 text-blue-700 dark:text-blue-300",
  stop_loss: "bg-red-500/20 text-red-700 dark:text-red-300",
  take_profit: "bg-green-500/20 text-green-700 dark:text-green-300",
  final_close: "bg-muted/60 text-muted-foreground",
}

function ExitReasonBadge({ reason }: { reason: RebalanceTradeReason }) {
  const t = useTranslations("backtests.screener.exit_reason")
  return (
    <span
      className={
        "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold " +
        (EXIT_REASON_BADGE[reason] ?? "bg-muted text-muted-foreground")
      }
    >
      {t(reason)}
    </span>
  )
}

function ScreenerTradesTable({ trades }: { trades: ScreenerBacktestTrade[] }) {
  const t = useTranslations("backtests.results.columns")
  const tCols = useTranslations("backtests.screener.results.trades_columns")
  const tHint = useTranslations("backtests.screener.results")
  const [openTrade, setOpenTrade] = useState<ScreenerBacktestTrade | null>(null)
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-dashed bg-background/20 px-3 py-2 text-[11px] text-muted-foreground">
        {tHint("fill_model_hint")}
      </div>
      <div className="overflow-x-auto rounded-lg border bg-background/20">
        <table className="w-full text-xs">
          <thead className="bg-muted/30">
            <tr className="text-left text-[10px] uppercase tracking-[0.12em] text-muted-foreground/80">
              <th className="px-3 py-2 font-semibold">
                {t("entry_date")}
                <span className="ml-1 text-muted-foreground/60 normal-case tracking-normal">
                  (T+1 09:30)
                </span>
              </th>
              <th className="px-3 py-2 font-semibold">code</th>
              <th className="px-3 py-2 font-semibold">{tCols("name")}</th>
              <th className="px-3 py-2 font-semibold text-right">{t("entry_price")}</th>
              <th className="px-3 py-2 font-semibold">{t("exit_date")}</th>
              <th className="px-3 py-2 font-semibold text-right">{t("exit_price")}</th>
              <th className="px-3 py-2 font-semibold text-right">{t("return")}</th>
              <th className="px-3 py-2 font-semibold text-right">{t("holding_days")}</th>
              <th className="px-3 py-2 font-semibold">{tCols("exit_reason")}</th>
              <th className="px-3 py-2 font-semibold text-center">{tCols("chart")}</th>
            </tr>
          </thead>
          <tbody>
          {trades.map((trade, idx) => (
            <tr
              key={`${trade.code}-${trade.entry_date}-${trade.exit_date}-${idx}`}
              className="border-t border-muted/20 font-mono"
            >
              <td className="px-3 py-2">{trade.entry_date}</td>
              <td className="px-3 py-2">{trade.code}</td>
              <td className="px-3 py-2 font-sans">{trade.name}</td>
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
              <td className="px-3 py-2 font-sans">
                <ExitReasonBadge reason={trade.exit_reason} />
              </td>
              <td className="px-3 py-2 text-center">
                <button
                  type="button"
                  onClick={() => setOpenTrade(trade)}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md border bg-background/50 text-muted-foreground hover:text-foreground hover:bg-muted/40"
                  title={tCols("chart")}
                >
                  <LineChartIcon className="h-3.5 w-3.5" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {openTrade ? (
        <TradeChartDialog
          trade={openTrade}
          onClose={() => setOpenTrade(null)}
        />
      ) : null}
    </div>
  )
}

/**
 * Modal showing a daily K-line chart for a backtest trade with B (entry) and
 * S (exit) markers. Window covers [entry_date - 20 trading days, exit_date +
 * 5 trading days] approximated via calendar days (~ × 1.5) so weekends/
 * holidays don't truncate the visible context.
 */
function TradeChartDialog({
  trade,
  onClose,
}: {
  trade: ScreenerBacktestTrade
  onClose: () => void
}) {
  const t = useTranslations("backtests.screener.results.chart_dialog")

  const { startIso, endIso } = useMemo(() => {
    const entry = new Date(`${trade.entry_date}T00:00:00`)
    const exit_ = new Date(`${trade.exit_date}T00:00:00`)
    const start = new Date(entry)
    start.setDate(start.getDate() - 30) // ~20 trading days back
    const end = new Date(exit_)
    end.setDate(end.getDate() + 7) // ~5 trading days forward
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return { startIso: fmt(start), endIso: fmt(end) }
  }, [trade.entry_date, trade.exit_date])

  const klineQuery = useStockKline({
    symbol: trade.code,
    period: "daily",
    start: startIso,
    end: endIso,
  })

  const bars = useMemo(
    () =>
      (klineQuery.data ?? []).map((b) => ({
        timestamp: b.timestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
        volume: b.volume,
      })),
    [klineQuery.data],
  )

  const markers: KLineMarker[] = useMemo(
    () => [
      {
        date: trade.entry_date,
        side: "buy",
        text: `B @${trade.entry_price.toFixed(2)}`,
      },
      {
        date: trade.exit_date,
        side: "sell",
        text: `S @${trade.exit_price.toFixed(2)}`,
      },
    ],
    [trade.entry_date, trade.exit_date, trade.entry_price, trade.exit_price],
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden rounded-xl border bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b p-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
              {t("title")}
            </div>
            <h3 className="text-base font-bold font-display">
              {trade.name}{" "}
              <span className="font-mono text-muted-foreground">
                {trade.code}
              </span>
            </h3>
            <p className="text-[11px] text-muted-foreground mt-1 font-mono">
              {trade.entry_date} → {trade.exit_date} ·{" "}
              <span className={returnColorClass(trade.return_pct)}>
                {trade.return_pct > 0 ? "+" : ""}
                {trade.return_pct.toFixed(2)}%
              </span>{" "}
              · {trade.holding_days}d
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4">
          {klineQuery.isLoading ? (
            <div className="flex h-[360px] items-center justify-center text-xs text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {t("loading")}
            </div>
          ) : klineQuery.error ? (
            <div className="flex h-[360px] items-center justify-center text-xs text-destructive">
              {t("error")}
            </div>
          ) : bars.length === 0 ? (
            <div className="flex h-[360px] items-center justify-center text-xs text-muted-foreground">
              {t("empty")}
            </div>
          ) : (
            <>
              <KLineChart data={bars} markers={markers} height={400} />
              <div className="mt-3 rounded-md border border-dashed bg-muted/10 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
                <div>
                  <span className="font-semibold text-foreground/80">B：</span>
                  {t("fill_buy_note")}
                </div>
                <div className="mt-1">
                  <span className="font-semibold text-foreground/80">S：</span>
                  {trade.exit_reason === "stop_loss"
                    ? t("fill_sell_stop_loss_note")
                    : trade.exit_reason === "take_profit"
                      ? t("fill_sell_take_profit_note")
                      : t("fill_sell_rebalance_note")}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function HoldingsAccordionItem({
  snapshot,
  locale,
}: {
  snapshot: { date: string; cash: number; equity: number; holdings: { code: string; name: string; shares: number; market_value: number; weight_pct: number }[] }
  locale: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border bg-background/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-mono hover:bg-muted/20"
      >
        <span className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          <span className="font-semibold">{snapshot.date}</span>
          <span className="text-muted-foreground">
            ({snapshot.holdings.length})
          </span>
        </span>
        <span className="text-muted-foreground">
          {formatCurrency(snapshot.equity, locale)}
        </span>
      </button>
      {open ? (
        <div className="border-t px-3 py-2">
          {snapshot.holdings.length === 0 ? (
            <div className="text-[11px] text-muted-foreground">—</div>
          ) : (
            <table className="w-full text-[11px] font-mono">
              <thead>
                <tr className="text-left text-muted-foreground/80">
                  <th className="py-1 pr-2 font-semibold">code</th>
                  <th className="py-1 pr-2 font-semibold">name</th>
                  <th className="py-1 pr-2 font-semibold text-right">shares</th>
                  <th className="py-1 pr-2 font-semibold text-right">value</th>
                  <th className="py-1 pr-2 font-semibold text-right">weight</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.holdings.map((h) => (
                  <tr key={h.code} className="border-t border-muted/20">
                    <td className="py-1 pr-2">{h.code}</td>
                    <td className="py-1 pr-2 font-sans">{h.name}</td>
                    <td className="py-1 pr-2 text-right">{h.shares}</td>
                    <td className="py-1 pr-2 text-right">
                      {formatCurrency(h.market_value, locale)}
                    </td>
                    <td className="py-1 pr-2 text-right">
                      {h.weight_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}
    </div>
  )
}
