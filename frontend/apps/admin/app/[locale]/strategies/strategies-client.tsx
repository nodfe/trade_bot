"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
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
  useRunScreenerBacktest,
  useStrategies,
  STRATEGY_FACTOR_TAGS,
  STRATEGY_REGIME_TAGS,
  type ScreenerBacktestRequest,
  type ScreenerBacktestResult,
  type SparklinePoint,
  type Strategy,
  type StrategyFactorTag,
  type StrategyKey,
  type StrategyKpi,
  type StrategyRegimeTag,
  type StrategyTag,
} from "@quant/hooks"
import {
  Activity,
  AlertCircle,
  ArrowRight,
  FlaskConical,
  Loader2,
  Sparkles,
  TrendingUp,
  Volume2,
  X,
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

// ---------------------------------------------------------------------------
// Static metadata (icon, accent) per strategy key — not provided by backend.
// ---------------------------------------------------------------------------

const STRATEGY_ICON: Record<StrategyKey, typeof TrendingUp> = {
  strong_uptrend: TrendingUp,
  volume_breakout: Volume2,
  pullback_watch: Sparkles,
}

const STRATEGY_ACCENT_BG: Record<StrategyKey, string> = {
  strong_uptrend: "bg-stock-up/10 text-stock-up",
  volume_breakout: "bg-primary/10 text-primary",
  pullback_watch: "bg-stock-down/10 text-stock-down",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function formatNumber(value: number | null | undefined, na: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return na
  return value.toFixed(2)
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
function returnColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value))
    return "text-muted-foreground"
  if (value > 0) return "text-stock-up"
  if (value < 0) return "text-stock-down"
  return "text-foreground"
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function StrategiesClient() {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")
  const { data, isLoading, error } = useStrategies()

  const [selectedFactors, setSelectedFactors] = useState<StrategyFactorTag[]>(
    [],
  )
  const [selectedRegimes, setSelectedRegimes] = useState<StrategyRegimeTag[]>(
    [],
  )
  const [drawerStrategy, setDrawerStrategy] = useState<Strategy | null>(null)

  function toggleFactor(tag: StrategyFactorTag) {
    setSelectedFactors((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    )
  }
  function toggleRegime(tag: StrategyRegimeTag) {
    setSelectedRegimes((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    )
  }
  function resetFilters() {
    setSelectedFactors([])
    setSelectedRegimes([])
  }

  const strategies = useMemo(
    () => data?.strategies ?? [],
    [data?.strategies],
  )

  const filtered = useMemo(() => {
    return strategies.filter((s) => {
      if (selectedFactors.length > 0) {
        const ok = selectedFactors.some((tag) =>
          s.tags.includes(tag as StrategyTag),
        )
        if (!ok) return false
      }
      if (selectedRegimes.length > 0) {
        const ok = selectedRegimes.some((tag) =>
          s.tags.includes(tag as StrategyTag),
        )
        if (!ok) return false
      }
      return true
    })
  }, [strategies, selectedFactors, selectedRegimes])

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Catalog Description */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {t("catalog.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("catalog.description")}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Tag filter bar */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardContent className="space-y-3 pt-5">
          <FilterRow
            label={t("tag_groups.factor")}
            tags={STRATEGY_FACTOR_TAGS}
            selected={selectedFactors}
            onToggle={(tag) => toggleFactor(tag as StrategyFactorTag)}
          />
          <FilterRow
            label={t("tag_groups.regime")}
            tags={STRATEGY_REGIME_TAGS}
            selected={selectedRegimes}
            onToggle={(tag) => toggleRegime(tag as StrategyRegimeTag)}
          />
          <div className="pt-1">
            <button
              type="button"
              onClick={resetFilters}
              className={
                "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors " +
                (selectedFactors.length === 0 && selectedRegimes.length === 0
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background/40 text-muted-foreground hover:text-foreground")
              }
            >
              {t("filter.all")}
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Cards grid */}
      {isLoading ? (
        <CardsSkeleton />
      ) : error ? (
        <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none">
          <CardContent className="pt-6 pb-6">
            <div className="flex items-center justify-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span>
                {error instanceof ApiError
                  ? error.message
                  : (error as Error).message}
              </span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((strategy) => (
            <StrategyCard
              key={strategy.key}
              strategy={strategy}
              onOpenDetails={() => setDrawerStrategy(strategy)}
            />
          ))}
          {filtered.length === 0 ? (
            <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none md:col-span-2 xl:col-span-3">
              <CardContent className="pt-6 pb-6 text-center text-xs text-muted-foreground">
                {tScreeners("candidates.no_candidates")}
              </CardContent>
            </Card>
          ) : null}
        </div>
      )}

      {/* Custom strategies — coming soon */}
      <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground/70" />
            {t("custom.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("custom.description")}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Detail drawer */}
      {drawerStrategy ? (
        <StrategyDetailDrawer
          strategy={drawerStrategy}
          onClose={() => setDrawerStrategy(null)}
        />
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tag filter row
// ---------------------------------------------------------------------------

function FilterRow({
  label,
  tags,
  selected,
  onToggle,
}: {
  label: string
  tags: readonly StrategyTag[]
  selected: readonly StrategyTag[]
  onToggle: (tag: StrategyTag) => void
}) {
  const t = useTranslations("strategies.tags")
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mr-2">
        {label}
      </span>
      {tags.map((tag) => {
        const active = selected.includes(tag)
        return (
          <button
            key={tag}
            type="button"
            onClick={() => onToggle(tag)}
            className={
              "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors " +
              (active
                ? "bg-primary/15 text-primary border-primary/40"
                : "bg-background/40 text-muted-foreground hover:text-foreground")
            }
          >
            {t(tag)}
          </button>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategy card
// ---------------------------------------------------------------------------

function StrategyCard({
  strategy,
  onOpenDetails,
}: {
  strategy: Strategy
  onOpenDetails: () => void
}) {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")
  const tTags = useTranslations("strategies.tags")
  const tKpi = useTranslations("strategies.kpi")
  const Icon = STRATEGY_ICON[strategy.key] ?? Sparkles
  const accentClass =
    STRATEGY_ACCENT_BG[strategy.key] ?? "bg-primary/10 text-primary"
  const na = "—"
  const kpi = strategy.kpi

  return (
    <Card className="premium-glass-card premium-glass-hover border bg-background/30 shadow-md flex flex-col">
      <CardHeader className="pb-3 border-b border-muted/30">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className={
                "inline-flex h-9 w-9 items-center justify-center rounded-xl " +
                accentClass
              }
            >
              <Icon className="h-4 w-4" />
            </span>
            <div>
              <CardTitle className="text-base font-bold font-display">
                {tScreeners(`options.${strategy.key}.label`)}
              </CardTitle>
              <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground mt-1">
                {tScreeners(`options.${strategy.key}.badge`)}
              </span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col flex-1 gap-4 pt-4">
        {/* Tag chips */}
        <div className="flex flex-wrap gap-1.5">
          {strategy.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded-full border bg-background/30 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground"
            >
              {tTags(tag)}
            </span>
          ))}
        </div>

        {/* Sparkline */}
        <Sparkline kpi={kpi} sparklineId={`spark-${strategy.key}`} />

        {/* KPI grid 2x2 */}
        <div className="grid grid-cols-2 gap-2">
          <KpiCell
            label={tKpi("annualized_return")}
            value={formatPct(kpi?.annualized_return_pct, na)}
            valueClass={returnColorClass(kpi?.annualized_return_pct)}
          />
          <KpiCell
            label={tKpi("sharpe")}
            value={formatNumber(kpi?.sharpe_ratio, na)}
            valueClass="text-foreground"
          />
          <KpiCell
            label={tKpi("max_drawdown")}
            value={
              kpi?.max_drawdown_pct != null
                ? `-${Math.abs(kpi.max_drawdown_pct).toFixed(2)}%`
                : na
            }
            valueClass={
              kpi?.max_drawdown_pct != null
                ? "text-stock-down"
                : "text-muted-foreground"
            }
          />
          <KpiCell
            label={tKpi("win_rate")}
            value={
              kpi?.win_rate_pct != null
                ? `${kpi.win_rate_pct.toFixed(2)}%`
                : na
            }
            valueClass="text-foreground"
          />
        </div>

        {/* As of caption */}
        <div className="text-[10px] text-muted-foreground/80">
          {kpi ? tKpi("as_of", { date: kpi.as_of_date }) : tKpi("no_data")}
        </div>

        {/* Description */}
        <CardDescription className="text-xs leading-5">
          {tScreeners(`options.${strategy.key}.description`)}
        </CardDescription>

        {/* Default params */}
        <details className="rounded-xl border bg-background/20 p-3 group">
          <summary className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 cursor-pointer">
            {t("card.defaults_title")}
          </summary>
          <div className="space-y-1.5 text-xs font-mono pt-2">
            {Object.entries(strategy.default_params).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3">
                <span className="text-muted-foreground">
                  {paramLabel(t, key)}
                </span>
                <span className="font-semibold text-foreground">
                  {formatParamValue(key, value)}
                </span>
              </div>
            ))}
          </div>
        </details>

        {/* CTAs */}
        <div className="mt-auto pt-2 flex flex-col sm:flex-row gap-2">
          <Link
            href={`/backtests?mode=screener&screen=${strategy.key}`}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/95 px-4 py-2 text-xs font-semibold transition-colors"
          >
            {t("card.backtest_cta")}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          <button
            type="button"
            onClick={onOpenDetails}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border bg-background/40 hover:bg-background/60 px-4 py-2 text-xs font-semibold text-foreground transition-colors"
          >
            {t("card.detail_cta")}
          </button>
        </div>
      </CardContent>
    </Card>
  )
}

function paramLabel(t: ReturnType<typeof useTranslations>, key: string): string {
  // Known param keys are translated; unknown keys fall back to the raw name.
  try {
    return t(`params.${key}`)
  } catch {
    return key
  }
}

function formatParamValue(key: string, value: number): string {
  if (key.endsWith("_pct")) return `${value}%`
  if (key.endsWith("_ratio")) return `${value}x`
  return String(value)
}

function KpiCell({
  label,
  value,
  valueClass,
}: {
  label: string
  value: string
  valueClass: string
}) {
  return (
    <div className="rounded-xl border bg-background/20 p-2.5 space-y-1">
      <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
        {label}
      </div>
      <div className={`text-sm font-bold font-mono ${valueClass}`}>{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sparkline
// ---------------------------------------------------------------------------

function Sparkline({
  kpi,
  sparklineId,
}: {
  kpi: StrategyKpi | null
  sparklineId: string
}) {
  const t = useTranslations("strategies.kpi")
  if (!kpi || kpi.equity_sparkline.length === 0) {
    return (
      <div className="h-[60px] w-full flex items-center justify-center rounded-lg border border-dashed bg-background/10 text-[10px] text-muted-foreground">
        {t("no_data")}
      </div>
    )
  }
  // A-share 红涨绿跌: positive total_return → up (red), negative → down (green)
  const isUp = (kpi.total_return_pct ?? 0) >= 0
  const colorVar = isUp ? "var(--color-stock-up)" : "var(--color-stock-down)"
  return (
    <div className="h-[60px] w-full">
      <ResponsiveContainer>
        <AreaChart
          data={kpi.equity_sparkline}
          margin={{ top: 2, right: 0, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id={sparklineId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colorVar} stopOpacity={0.4} />
              <stop offset="100%" stopColor={colorVar} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={colorVar}
            strokeWidth={1.75}
            fill={`url(#${sparklineId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------

function CardsSkeleton() {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <Card
          key={i}
          className="premium-glass-card border bg-background/30 shadow-md flex flex-col"
        >
          <CardHeader className="pb-3 border-b border-muted/30">
            <div className="flex items-center gap-2">
              <div className="h-9 w-9 rounded-xl bg-muted animate-pulse" />
              <div className="space-y-1.5">
                <div className="h-4 w-32 bg-muted animate-pulse rounded" />
                <div className="h-3 w-20 bg-muted/70 animate-pulse rounded" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col flex-1 gap-4 pt-4">
            <div className="flex gap-1.5">
              <div className="h-5 w-16 bg-muted/60 animate-pulse rounded-full" />
              <div className="h-5 w-20 bg-muted/60 animate-pulse rounded-full" />
            </div>
            <div className="h-[60px] bg-muted/40 animate-pulse rounded" />
            <div className="grid grid-cols-2 gap-2">
              {[0, 1, 2, 3].map((k) => (
                <div
                  key={k}
                  className="h-14 bg-muted/40 animate-pulse rounded-xl"
                />
              ))}
            </div>
            <div className="h-3 w-2/3 bg-muted/50 animate-pulse rounded" />
            <div className="h-9 bg-muted/40 animate-pulse rounded-lg" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail drawer (custom right-side overlay; the project does not ship a Sheet
// primitive, so we render an accessible focus-trapless overlay).
// ---------------------------------------------------------------------------

function StrategyDetailDrawer({
  strategy,
  onClose,
}: {
  strategy: Strategy
  onClose: () => void
}) {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")
  const tTags = useTranslations("strategies.tags")

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
      />
      {/* Panel */}
      <div className="relative h-full w-full max-w-2xl overflow-y-auto border-l bg-background shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b bg-background/95 backdrop-blur p-5">
          <div>
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
              {t("drawer.title")}
            </div>
            <h2 className="text-xl font-bold font-display">
              {tScreeners(`options.${strategy.key}.label`)}
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              {t("drawer.description")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border bg-background/40 p-1.5 text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-5 p-5">
          {/* Tag chips */}
          <div className="flex flex-wrap gap-1.5">
            {strategy.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center rounded-full border bg-background/30 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground"
              >
                {tTags(tag)}
              </span>
            ))}
          </div>

          {/* Description */}
          <p className="text-sm leading-6 text-foreground/90">
            {tScreeners(`options.${strategy.key}.description`)}
          </p>

          {/* Default parameters */}
          <Card className="premium-glass-card border bg-background/30 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">
                {t("drawer.params_title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
                {Object.entries(strategy.default_params).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex justify-between gap-3 rounded-lg border bg-background/20 px-3 py-2"
                  >
                    <dt className="text-muted-foreground">
                      {paramLabel(t, key)}
                    </dt>
                    <dd className="font-semibold text-foreground">
                      {formatParamValue(key, value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>

          {/* Embedded backtest */}
          <Card className="premium-glass-card border bg-background/30 shadow-sm">
            <CardHeader className="pb-2 border-b border-muted/30">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                {t("drawer.backtest_section_title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <EmbeddedBacktest strategyKey={strategy.key} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Embedded backtest panel — slim form using `useRunScreenerBacktest` directly,
// pre-filled with reasonable defaults (180 days, weekly rebalance, top_n=10,
// equal weight). Renders only KPIs + the equity sparkline.
// ---------------------------------------------------------------------------

function EmbeddedBacktest({ strategyKey }: { strategyKey: StrategyKey }) {
  const t = useTranslations("backtests")
  const tBtScreener = useTranslations("backtests.screener")
  const locale = useLocale()
  const { mutate, data, error, isPending, reset } = useRunScreenerBacktest()

  const initialPayload: ScreenerBacktestRequest = useMemo(
    () => ({
      screen_type: strategyKey,
      start_date: isoDaysAgo(180),
      end_date: todayIso(),
      rebalance: "weekly",
      top_n: 10,
      weighting: "equal",
      initial_capital: 100_000,
      commission_rate: 0.00025,
      stamp_duty_rate: 0.001,
      slippage_rate: 0.001,
      stop_loss_pct: null,
      take_profit_pct: null,
      benchmark: "universe_buy_hold",
    }),
    [strategyKey],
  )

  function handleRun() {
    reset()
    mutate(initialPayload)
  }

  const errorMessage = error
    ? error instanceof ApiError
      ? error.message || t("errors.request_failed")
      : t("errors.request_failed")
    : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] text-muted-foreground">
          {tBtScreener("subtitle")}
        </div>
        <Button
          type="button"
          onClick={handleRun}
          disabled={isPending}
          className="gap-2"
        >
          {isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {tBtScreener("form.running")}
            </>
          ) : (
            <>
              <FlaskConical className="h-3.5 w-3.5" />
              {tBtScreener("form.submit")}
            </>
          )}
        </Button>
      </div>

      {errorMessage ? (
        <div className="flex items-center gap-2 text-xs text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {data ? (
        <EmbeddedBacktestResults result={data} locale={locale} />
      ) : !isPending ? (
        <div className="rounded-xl border border-dashed bg-background/20 p-4 text-center text-xs text-muted-foreground">
          {t("empty")}
        </div>
      ) : null}
    </div>
  )
}

function EmbeddedBacktestResults({
  result,
  locale,
}: {
  result: ScreenerBacktestResult
  locale: string
}) {
  const t = useTranslations("backtests")
  const na = t("results.na")

  const kpis: { label: string; value: string; valueClass: string }[] = [
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
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="rounded-xl border bg-background/20 p-3 space-y-1"
          >
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
              {kpi.label}
            </div>
            <div className={`text-base font-bold font-mono ${kpi.valueClass}`}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border bg-background/20 p-3">
        <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mb-2 flex items-center gap-2">
          <Activity className="h-3.5 w-3.5" />
          {t("results.equity_title")}
        </div>
        <div className="h-[200px] w-full">
          <ResponsiveContainer>
            <AreaChart
              data={result.equity_curve}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient
                  id="strategy-embed-equity"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor="var(--color-primary)"
                    stopOpacity={0.4}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--color-primary)"
                    stopOpacity={0.05}
                  />
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
                fill="url(#strategy-embed-equity)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
