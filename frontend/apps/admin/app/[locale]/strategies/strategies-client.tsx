"use client"

import { useEffect, useMemo, useState } from "react"
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
  useCreateCustomStrategy,
  useCreateSubscription,
  useCustomStrategies,
  useDeleteCustomStrategy,
  useDeleteSubscription,
  useRunStrategyBacktest,
  useStrategies,
  useStrategyAttribution,
  useSubscriptions,
  useUpdateCustomStrategy,
  STRATEGY_FACTOR_TAGS,
  STRATEGY_REGIME_TAGS,
  readFavoriteStrategies,
  writeFavoriteStrategies,
  type AttributionOut,
  type BuiltInStrategyKey,
  type MonthlyReturn,
  type ScreenerBacktestResult,
  type Strategy,
  type StrategyAttribution,
  type StrategyFactorTag,
  type StrategyKey,
  type StrategyKpi,
  type StrategyRegimeTag,
  type StrategyRunBacktestRequest,
  type StrategyTag,
  type Subscription,
  type UserStrategy,
} from "@quant/hooks"
import { useEChartsTheme } from "@quant/charts"
import ReactECharts from "echarts-for-react"
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Crown,
  FlaskConical,
  Flame,
  Loader2,
  Pencil,
  Plus,
  Rocket,
  Search,
  Sparkles,
  Star,
  Trash2,
  TrendingUp,
  Volume2,
  X,
} from "lucide-react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

// ---------------------------------------------------------------------------
// Static visual metadata
// ---------------------------------------------------------------------------

const BUILTIN_KEYS: BuiltInStrategyKey[] = [
  "strong_uptrend",
  "volume_breakout",
  "pullback_watch",
  "first_limit_up_low",
  "leader_streak",
  "zt_relay",
  "lhb_follow",
]

const STRATEGY_ICON: Record<string, typeof TrendingUp> = {
  strong_uptrend: TrendingUp,
  volume_breakout: Volume2,
  pullback_watch: Sparkles,
  first_limit_up_low: Rocket,
  leader_streak: Crown,
  zt_relay: Flame,
  lhb_follow: Activity,
}

const STRATEGY_ACCENT_BG: Record<string, string> = {
  strong_uptrend: "bg-stock-up/10 text-stock-up",
  volume_breakout: "bg-primary/10 text-primary",
  pullback_watch: "bg-stock-down/10 text-stock-down",
  first_limit_up_low: "bg-stock-up/10 text-stock-up",
  leader_streak: "bg-stock-up/10 text-stock-up",
  zt_relay: "bg-primary/10 text-primary",
  lhb_follow: "bg-primary/10 text-primary",
}

const SORT_KEYS = [
  "sort_sharpe",
  "sort_annualized",
  "sort_drawdown",
  "sort_sortino",
] as const
type SortKey = (typeof SORT_KEYS)[number]

const PIE_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-stock-up)",
  "var(--color-stock-down)",
  "var(--color-primary)",
]

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

function returnColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value))
    return "text-muted-foreground"
  if (value > 0) return "text-stock-up"
  if (value < 0) return "text-stock-down"
  return "text-foreground"
}

function strategyDisplayName(
  s: Strategy,
  tScreeners: ReturnType<typeof useTranslations>,
): string {
  if (s.is_custom && s.name) return s.name
  try {
    return tScreeners(`options.${s.key}.label`)
  } catch {
    return s.name ?? s.key
  }
}

function strategyDescription(
  s: Strategy,
  tScreeners: ReturnType<typeof useTranslations>,
): string {
  if (s.is_custom && s.description) return s.description
  try {
    return tScreeners(`options.${s.key}.description`)
  } catch {
    return s.description ?? ""
  }
}

function paramLabel(t: ReturnType<typeof useTranslations>, key: string): string {
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

export function compareByKpi(
  a: Strategy,
  b: Strategy,
  sortKey: SortKey,
): number {
  const akpi = a.kpi
  const bkpi = b.kpi
  function get(k: StrategyKpi | null): number {
    if (!k) return -Infinity
    if (sortKey === "sort_sharpe") return k.sharpe_ratio ?? -Infinity
    if (sortKey === "sort_annualized") return k.annualized_return_pct ?? -Infinity
    if (sortKey === "sort_drawdown") {
      // lower drawdown is better — invert sign so descending sort puts best first
      return k.max_drawdown_pct == null ? -Infinity : -Math.abs(k.max_drawdown_pct)
    }
    if (sortKey === "sort_sortino") return k.sortino_ratio ?? -Infinity
    return -Infinity
  }
  return get(bkpi) - get(akpi)
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function StrategiesClient() {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")
  const { data, isLoading, error } = useStrategies()
  const { data: customList } = useCustomStrategies()

  const [tab, setTab] = useState<"catalog" | "combo">("catalog")
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<SortKey>("sort_sharpe")
  const [selectedFactors, setSelectedFactors] = useState<StrategyFactorTag[]>([])
  const [selectedRegimes, setSelectedRegimes] = useState<StrategyRegimeTag[]>([])
  const [drawerStrategy, setDrawerStrategy] = useState<Strategy | null>(null)
  const [favorites, setFavorites] = useState<string[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [editStrategy, setEditStrategy] = useState<UserStrategy | null>(null)

  useEffect(() => {
    setFavorites(readFavoriteStrategies())
  }, [])

  function toggleFavorite(key: string) {
    setFavorites((prev) => {
      const next = prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key]
      writeFavoriteStrategies(next)
      return next
    })
  }

  function toggleFactor(tag: StrategyFactorTag) {
    setSelectedFactors((prev) =>
      prev.includes(tag) ? prev.filter((x) => x !== tag) : [...prev, tag],
    )
  }
  function toggleRegime(tag: StrategyRegimeTag) {
    setSelectedRegimes((prev) =>
      prev.includes(tag) ? prev.filter((x) => x !== tag) : [...prev, tag],
    )
  }
  function resetFilters() {
    setSelectedFactors([])
    setSelectedRegimes([])
    setSearch("")
  }

  const strategies = useMemo(() => data?.strategies ?? [], [data?.strategies])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    let list = strategies.filter((s) => {
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
      if (q.length > 0) {
        const name = strategyDisplayName(s, tScreeners).toLowerCase()
        const inName = name.includes(q)
        const inTag = s.tags.some((tag) => tag.toLowerCase().includes(q))
        const inKey = String(s.key).toLowerCase().includes(q)
        if (!inName && !inTag && !inKey) return false
      }
      return true
    })

    list = [...list].sort((a, b) => compareByKpi(a, b, sortKey))

    // Pin favorites to the top.
    list.sort((a, b) => {
      const af = favorites.includes(String(a.key)) ? 0 : 1
      const bf = favorites.includes(String(b.key)) ? 0 : 1
      return af - bf
    })
    return list
  }, [strategies, selectedFactors, selectedRegimes, search, sortKey, favorites, tScreeners])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="default"
            onClick={() => setCreateOpen(true)}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            {t("toolbar.new_strategy")}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b">
        <TabBtn
          active={tab === "catalog"}
          onClick={() => setTab("catalog")}
          label={t("toolbar.tab_catalog")}
        />
        <Link
          href="/strategies/combo"
          className="inline-flex items-center px-4 py-2 text-sm font-semibold border-b-2 border-transparent text-muted-foreground hover:text-foreground"
        >
          {t("toolbar.tab_combo")}
        </Link>
      </div>

      {/* Toolbar */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardContent className="space-y-3 pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder={t("toolbar.search_placeholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-2 text-xs rounded-md border bg-background/40 focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">
                {t("toolbar.sort_by")}:
              </span>
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              >
                {SORT_KEYS.map((k) => (
                  <option key={k} value={k}>
                    {t(`toolbar.${k}`)}
                  </option>
                ))}
              </select>
            </div>
          </div>

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
              className="inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold bg-background/40 text-muted-foreground hover:text-foreground"
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
              key={String(strategy.key)}
              strategy={strategy}
              isFavorite={favorites.includes(String(strategy.key))}
              onToggleFavorite={() => toggleFavorite(String(strategy.key))}
              onOpenDetails={() => setDrawerStrategy(strategy)}
              onEdit={
                strategy.is_custom
                  ? () => {
                      const cs = (customList ?? []).find(
                        (c) => c.catalog_key === strategy.key,
                      )
                      if (cs) setEditStrategy(cs)
                    }
                  : undefined
              }
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

      {drawerStrategy ? (
        <StrategyDetailDrawer
          strategy={drawerStrategy}
          onClose={() => setDrawerStrategy(null)}
        />
      ) : null}

      {createOpen ? (
        <CustomStrategyDialog
          mode="create"
          onClose={() => setCreateOpen(false)}
        />
      ) : null}

      {editStrategy ? (
        <CustomStrategyDialog
          mode="edit"
          existing={editStrategy}
          onClose={() => setEditStrategy(null)}
        />
      ) : null}
    </div>
  )
}

function TabBtn({
  active,
  onClick,
  label,
}: {
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "inline-flex items-center px-4 py-2 text-sm font-semibold border-b-2 transition-colors " +
        (active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground")
      }
    >
      {label}
    </button>
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
  isFavorite,
  onToggleFavorite,
  onOpenDetails,
  onEdit,
}: {
  strategy: Strategy
  isFavorite: boolean
  onToggleFavorite: () => void
  onOpenDetails: () => void
  onEdit?: () => void
}) {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")
  const tTags = useTranslations("strategies.tags")
  const tKpi = useTranslations("strategies.kpi")
  const Icon = STRATEGY_ICON[String(strategy.key)] ?? Sparkles
  const accentClass =
    STRATEGY_ACCENT_BG[String(strategy.key)] ?? "bg-primary/10 text-primary"
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
                {strategyDisplayName(strategy, tScreeners)}
              </CardTitle>
              <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground mt-1">
                {strategy.is_custom ? "Custom" : (() => {
                  try { return tScreeners(`options.${strategy.key}.badge`) } catch { return strategy.base_template ?? "" }
                })()}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onToggleFavorite}
              aria-label={isFavorite ? t("toolbar.unfavorite") : t("toolbar.favorite")}
              className={
                "rounded-md p-1.5 transition-colors " +
                (isFavorite
                  ? "text-stock-up"
                  : "text-muted-foreground hover:text-foreground")
              }
            >
              <Star
                className={"h-4 w-4 " + (isFavorite ? "fill-current" : "")}
              />
            </button>
            {onEdit ? (
              <button
                type="button"
                onClick={onEdit}
                className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
                aria-label="Edit"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col flex-1 gap-4 pt-4">
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

        <Sparkline kpi={kpi} sparklineId={`spark-${String(strategy.key).replace(/[^A-Za-z0-9]/g, "_")}`} />

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

        {/* Extended KPI strip */}
        <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
          <span>
            {tKpi("sortino")}:{" "}
            <span className="text-foreground font-semibold font-mono">
              {formatNumber(kpi?.sortino_ratio, na)}
            </span>
          </span>
          <span>
            {tKpi("calmar")}:{" "}
            <span className="text-foreground font-semibold font-mono">
              {formatNumber(kpi?.calmar_ratio, na)}
            </span>
          </span>
          <span>
            {tKpi("turnover")}:{" "}
            <span className="text-foreground font-semibold font-mono">
              {kpi?.turnover_pct != null
                ? `${kpi.turnover_pct.toFixed(1)}%`
                : na}
            </span>
          </span>
        </div>

        <div className="text-[10px] text-muted-foreground/80">
          {kpi ? tKpi("as_of", { date: kpi.as_of_date }) : tKpi("no_data")}
        </div>

        <CardDescription className="text-xs leading-5">
          {strategyDescription(strategy, tScreeners)}
        </CardDescription>

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
                  {formatParamValue(key, value as number)}
                </span>
              </div>
            ))}
          </div>
        </details>

        <div className="mt-auto pt-2 flex flex-col sm:flex-row gap-2">
          <Link
            href={`/backtests?mode=screener&screen=${encodeURIComponent(String(strategy.key))}`}
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
          <Tooltip
            cursor={{ stroke: colorVar, strokeOpacity: 0.4, strokeDasharray: "3 3" }}
            wrapperStyle={{ outline: "none" }}
            contentStyle={{
              backgroundColor: "var(--color-popover)",
              color: "var(--color-popover-foreground)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 11,
              padding: "6px 8px",
              lineHeight: 1.4,
            }}
            labelStyle={{ fontSize: 10, opacity: 0.7, marginBottom: 2 }}
            formatter={(value: number, _name, item) => {
              const data = kpi.equity_sparkline
              const base = data[0]?.value ?? value
              const delta = base ? ((value - base) / base) * 100 : 0
              const sign = delta >= 0 ? "+" : ""
              return [
                `${value.toLocaleString()} (${sign}${delta.toFixed(2)}%)`,
                String(item?.payload?.date ?? ""),
              ] as [string, string]
            }}
            labelFormatter={() => ""}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

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
            <div className="h-[60px] bg-muted/40 animate-pulse rounded" />
            <div className="grid grid-cols-2 gap-2">
              {[0, 1, 2, 3].map((k) => (
                <div
                  key={k}
                  className="h-14 bg-muted/40 animate-pulse rounded-xl"
                />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Drawer with three tabs (Backtest / Attribution / Subscription)
// ---------------------------------------------------------------------------

type DrawerTab = "backtest" | "attribution" | "subscription"

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
  const [tab, setTab] = useState<DrawerTab>("backtest")

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
      />
      <div className="relative h-full w-full max-w-3xl overflow-y-auto border-l bg-background shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b bg-background/95 backdrop-blur p-5">
          <div>
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
              {t("drawer.title")}
            </div>
            <h2 className="text-xl font-bold font-display">
              {strategyDisplayName(strategy, tScreeners)}
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              {t("drawer.description")}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {strategy.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center rounded-full border bg-background/30 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground"
                >
                  {tTags(tag)}
                </span>
              ))}
            </div>
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

        <div className="flex border-b sticky top-[100px] bg-background z-10">
          {(["backtest", "attribution", "subscription"] as DrawerTab[]).map(
            (tk) => (
              <TabBtn
                key={tk}
                active={tab === tk}
                onClick={() => setTab(tk)}
                label={t(`drawer.tab_${tk}`)}
              />
            ),
          )}
        </div>

        <div className="space-y-5 p-5">
          {tab === "backtest" ? (
            <BacktestTab strategy={strategy} />
          ) : tab === "attribution" ? (
            <AttributionTab strategyKey={String(strategy.key)} />
          ) : (
            <SubscriptionTab strategyKey={String(strategy.key)} />
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Backtest tab: full param form, run-backtest, results
// ---------------------------------------------------------------------------

function BacktestTab({ strategy }: { strategy: Strategy }) {
  const t = useTranslations("strategies.backtest_form")
  const tStrat = useTranslations("strategies")
  const tBt = useTranslations("backtests")
  const locale = useLocale()
  const { mutate, data, error, isPending, reset } = useRunStrategyBacktest(
    String(strategy.key),
  )

  const initialParams = useMemo(
    () => ({ ...strategy.default_params }),
    [strategy.default_params],
  )
  const [params, setParams] = useState<Record<string, number>>(initialParams)
  const [topN, setTopN] = useState<number>(10)
  const [rebalance, setRebalance] = useState<string>("weekly")
  const [weighting, setWeighting] = useState<string>("equal")
  const [feeBps, setFeeBps] = useState<number>(35)
  const [stopLoss, setStopLoss] = useState<number | "">("")
  const [stopProfit, setStopProfit] = useState<number | "">("")
  const [startDate, setStartDate] = useState<string>(isoDaysAgo(180))
  const [endDate, setEndDate] = useState<string>(todayIso())
  const [benchmark, setBenchmark] = useState<string>("hs300")

  function handleRun() {
    reset()
    const payload: StrategyRunBacktestRequest = {
      params,
      top_n: topN,
      rebalance,
      weighting,
      fee_bps: feeBps,
      stop_loss_pct: stopLoss === "" ? null : Number(stopLoss),
      stop_profit_pct: stopProfit === "" ? null : Number(stopProfit),
      start_date: startDate,
      end_date: endDate,
      benchmark,
    }
    mutate(payload)
  }

  const errorMessage = error
    ? error instanceof ApiError
      ? error.message || tBt("errors.request_failed")
      : tBt("errors.request_failed")
    : null

  return (
    <div className="space-y-4">
      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("params_section")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <NumField label={t("top_n")} value={topN} onChange={setTopN} />
            <SelectField
              label={t("rebalance")}
              value={rebalance}
              onChange={setRebalance}
              options={["daily", "weekly", "biweekly", "monthly"]}
            />
            <SelectField
              label={t("weighting")}
              value={weighting}
              onChange={setWeighting}
              options={["equal", "score"]}
            />
            <NumField label={t("fee_bps")} value={feeBps} onChange={setFeeBps} />
            <NumField
              label={t("stop_loss_pct")}
              value={stopLoss}
              onChange={(v) => setStopLoss(Number.isNaN(v) ? "" : v)}
              allowEmpty
            />
            <NumField
              label={t("stop_profit_pct")}
              value={stopProfit}
              onChange={(v) => setStopProfit(Number.isNaN(v) ? "" : v)}
              allowEmpty
            />
            <DateField
              label={t("start_date")}
              value={startDate}
              onChange={setStartDate}
            />
            <DateField
              label={t("end_date")}
              value={endDate}
              onChange={setEndDate}
            />
            <SelectField
              label={t("benchmark")}
              value={benchmark}
              onChange={setBenchmark}
              options={["hs300", "universe_buy_hold", "none"]}
            />
          </div>

          {Object.keys(params).length > 0 ? (
            <div className="pt-2 border-t border-muted/30">
              <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mb-2">
                {t("params_section")}
              </div>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(params).map(([k, v]) => (
                  <NumField
                    key={k}
                    label={paramLabel(tStrat, k)}
                    value={v}
                    onChange={(nv) =>
                      setParams((prev) => ({ ...prev, [k]: Number(nv) }))
                    }
                  />
                ))}
              </div>
            </div>
          ) : null}

          <div className="pt-2 flex justify-end">
            <Button onClick={handleRun} disabled={isPending} className="gap-2">
              {isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {t("running")}
                </>
              ) : (
                <>
                  <FlaskConical className="h-3.5 w-3.5" />
                  {t("run")}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {errorMessage ? (
        <div className="flex items-center gap-2 text-xs text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {data ? <BacktestResults result={data} locale={locale} /> : null}
    </div>
  )
}

// react-hooks: NumField etc. are pure inputs.

function NumField({
  label,
  value,
  onChange,
  allowEmpty,
}: {
  label: string
  value: number | ""
  onChange: (v: number) => void
  allowEmpty?: boolean
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <input
        type="number"
        value={value === "" ? "" : value}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === "" && allowEmpty) {
            // Sentinel for "no value" — bridge as NaN; caller can detect.
            onChange(Number.NaN)
            return
          }
          const n = Number(raw)
          if (Number.isFinite(n)) onChange(n)
        }}
        className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
      />
    </label>
  )
}

function DateField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
      />
    </label>
  )
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}

// ---------------------------------------------------------------------------
// Backtest results: dual-line chart, KPI cards, monthly heatmap
// ---------------------------------------------------------------------------

function BacktestResults({
  result,
  locale,
}: {
  result: ScreenerBacktestResult
  locale: string
}) {
  const t = useTranslations("strategies.backtest_form")
  const tBt = useTranslations("backtests")
  const tKpi = useTranslations("strategies.kpi")
  const na = tBt("results.na")

  // Merge equity_curve and benchmark_curve into single data array for Recharts.
  const merged = useMemo(() => {
    const map = new Map<
      string,
      { date: string; strategy?: number; benchmark?: number }
    >()
    for (const p of result.equity_curve) {
      map.set(p.date, { date: p.date, strategy: p.value })
    }
    for (const p of result.benchmark_curve ?? []) {
      const cur = map.get(p.date) ?? { date: p.date }
      cur.benchmark = p.value
      map.set(p.date, cur)
    }
    return Array.from(map.values()).sort((a, b) =>
      a.date.localeCompare(b.date),
    )
  }, [result.equity_curve, result.benchmark_curve])

  const kpis: { label: string; value: string; valueClass: string }[] = [
    {
      label: tBt("results.total_return"),
      value: formatPct(result.total_return_pct, na),
      valueClass: returnColorClass(result.total_return_pct),
    },
    {
      label: tBt("results.annualized_return"),
      value: formatPct(result.annualized_return_pct, na),
      valueClass: returnColorClass(result.annualized_return_pct),
    },
    {
      label: tKpi("sharpe"),
      value: formatNumber(result.sharpe_ratio, na),
      valueClass: "text-foreground",
    },
    {
      label: tKpi("sortino"),
      value: formatNumber(result.sortino_ratio, na),
      valueClass: "text-foreground",
    },
    {
      label: tKpi("calmar"),
      value: formatNumber(result.calmar_ratio, na),
      valueClass: "text-foreground",
    },
    {
      label: tKpi("turnover"),
      value:
        result.turnover_pct != null
          ? `${result.turnover_pct.toFixed(1)}%`
          : na,
      valueClass: "text-foreground",
    },
    {
      label: tBt("results.max_drawdown"),
      value: `-${result.max_drawdown_pct.toFixed(2)}%`,
      valueClass: "text-stock-down",
    },
    {
      label: tBt("results.win_rate"),
      value: `${result.win_rate_pct.toFixed(2)}%`,
      valueClass: "text-foreground",
    },
  ]

  return (
    <div className="space-y-4">
      {result.alpha_pct != null ? (
        <div className="rounded-xl border bg-background/20 p-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{t("alpha")}</span>
          <span
            className={`text-base font-bold font-mono ${returnColorClass(result.alpha_pct)}`}
          >
            {formatPct(result.alpha_pct, na)}
          </span>
        </div>
      ) : null}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="rounded-xl border bg-background/20 p-3 space-y-1"
          >
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
              {kpi.label}
            </div>
            <div className={`text-sm font-bold font-mono ${kpi.valueClass}`}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border bg-background/20 p-3">
        <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mb-2 flex items-center gap-2">
          <Activity className="h-3.5 w-3.5" />
          {t("equity_vs_benchmark")}
        </div>
        <div className="h-[260px] w-full">
          <ResponsiveContainer>
            <LineChart
              data={merged}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
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
                cursor={{ stroke: "var(--color-muted-foreground)", strokeOpacity: 0.5, strokeDasharray: "3 3" }}
                wrapperStyle={{ outline: "none" }}
                contentStyle={{
                  backgroundColor: "var(--color-popover)",
                  color: "var(--color-popover-foreground)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                  fontSize: 12,
                  padding: "8px 10px",
                  lineHeight: 1.55,
                  boxShadow: "0 6px 20px rgba(0,0,0,0.18)",
                }}
                labelStyle={{ fontSize: 11, opacity: 0.7, marginBottom: 4 }}
                labelFormatter={(d) => String(d)}
                formatter={(value: number, name: string) => {
                  const baseStrat = merged[0]?.strategy ?? value
                  const baseBench = merged[0]?.benchmark ?? value
                  const base = name === "Benchmark" ? baseBench : baseStrat
                  const delta = base ? ((value - (base as number)) / (base as number)) * 100 : 0
                  const sign = delta >= 0 ? "+" : ""
                  return [
                    `${Number(value).toLocaleString(locale)}  ${sign}${delta.toFixed(2)}%`,
                    name,
                  ] as [string, string]
                }}
              />
              <Line
                type="monotone"
                dataKey="strategy"
                stroke="var(--color-stock-up)"
                strokeWidth={2}
                dot={false}
                name="Strategy"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="benchmark"
                stroke="var(--color-muted-foreground)"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                name="Benchmark"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <MonthlyReturnsHeatmap monthly={result.monthly_returns ?? []} />
    </div>
  )
}

function MonthlyReturnsHeatmap({ monthly }: { monthly: MonthlyReturn[] }) {
  const t = useTranslations("strategies.backtest_form")
  const theme = useEChartsTheme()
  const data = useMemo(() => {
    const yearSet = new Set<number>()
    const cells: { x: number; y: number; v: number }[] = []
    for (const m of monthly) {
      const [yStr, mStr] = m.period.split("-")
      const y = Number(yStr)
      const mo = Number(mStr)
      if (!Number.isFinite(y) || !Number.isFinite(mo)) continue
      yearSet.add(y)
      cells.push({ x: mo - 1, y, v: m.return_pct })
    }
    const years = Array.from(yearSet).sort()
    const yearIdx = new Map(years.map((y, i) => [y, i]))
    return {
      years,
      months: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
      cells: cells.map((c) => [c.x, yearIdx.get(c.y) ?? 0, Number(c.v.toFixed(2))]),
    }
  }, [monthly])

  if (data.cells.length === 0) return null

  const option = {
    tooltip: {
      position: "top",
      formatter: (p: { value: number[] }) => {
        const monthIdx = p.value[0]
        const yearIdx = p.value[1]
        const v = p.value[2]
        const year = data.years[yearIdx]
        const mo = String(monthIdx + 1).padStart(2, "0")
        const sign = v >= 0 ? "+" : ""
        const color = v >= 0 ? "#ef4444" : "#22c55e"
        return `<div style="font-size:12px;line-height:1.5">
          <div style="opacity:.7;font-size:11px">${year}-${mo}</div>
          <div style="color:${color};font-weight:600">${sign}${v.toFixed(2)}%</div>
        </div>`
      },
    },
    grid: { left: 50, right: 10, top: 10, bottom: 30 },
    xAxis: { type: "category", data: data.months, splitArea: { show: true } },
    yAxis: {
      type: "category",
      data: data.years.map(String),
      splitArea: { show: true },
    },
    visualMap: {
      min: -10,
      max: 10,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: {
        color: ["#22c55e", "#e5e7eb", "#ef4444"],
      },
    },
    series: [
      {
        name: "Monthly",
        type: "heatmap",
        data: data.cells,
        label: { show: true, formatter: (p: { value: number[] }) => p.value[2] + "%" },
      },
    ],
    backgroundColor: theme.backgroundColor,
    textStyle: theme.textStyle,
  }

  return (
    <div className="rounded-xl border bg-background/20 p-3">
      <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mb-2">
        {t("monthly_heatmap")}
      </div>
      <div style={{ height: 220 }}>
        <ReactECharts
          option={option}
          style={{ height: "100%", width: "100%" }}
          notMerge
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Attribution tab
// ---------------------------------------------------------------------------

function AttributionTab({ strategyKey }: { strategyKey: string }) {
  const t = useTranslations("strategies.attribution")
  const { data, isLoading, error } = useStrategyAttribution(strategyKey, 180)

  if (isLoading) {
    return (
      <div className="text-xs text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading...
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="text-xs text-muted-foreground">{t("no_data")}</div>
    )
  }
  return <AttributionPanels data={data} />
}

function AttributionPanels({
  data,
}: {
  data: StrategyAttribution | AttributionOut
}) {
  const t = useTranslations("strategies.attribution")
  const sectorData = (data.sector_exposure ?? []).map((s) => ({
    name: s.sector,
    value: Math.abs(s.weight_pct),
  }))
  const capData = (data.market_cap_buckets ?? []).map((b) => ({
    name: b.bucket,
    value: b.weight_pct,
  }))
  const monthly = (data.monthly_returns ?? []) as MonthlyReturn[]
  const yearly = (data.yearly_returns ?? []) as { period: string; return_pct: number }[]

  return (
    <div className="space-y-4">
      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("sector_exposure")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          {sectorData.length === 0 ? (
            <div className="text-xs text-muted-foreground">{t("no_data")}</div>
          ) : (
            <div className="h-[240px] w-full">
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={sectorData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={(p: { name: string; value: number }) =>
                      `${p.name} ${p.value.toFixed(1)}%`
                    }
                  >
                    {sectorData.map((_, i) => (
                      <Cell
                        key={i}
                        fill={PIE_COLORS[i % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--color-popover)",
                      color: "var(--color-popover-foreground)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      fontSize: 12,
                      padding: "6px 8px",
                    }}
                    formatter={(value: number, _n, item) => {
                      const total = sectorData.reduce((acc, d) => acc + d.value, 0)
                      const pct = total > 0 ? (value / total) * 100 : 0
                      return [
                        `${value.toFixed(2)}% (占 ${pct.toFixed(1)}%)`,
                        String(item?.payload?.name ?? ""),
                      ] as [string, string]
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("market_cap")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          {capData.length === 0 ? (
            <div className="text-xs text-muted-foreground">{t("no_data")}</div>
          ) : (
            <div className="h-[200px] w-full">
              <ResponsiveContainer>
                <BarChart data={capData}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "currentColor", opacity: 0.6 }}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--color-muted)", opacity: 0.15 }}
                    contentStyle={{
                      backgroundColor: "var(--color-popover)",
                      color: "var(--color-popover-foreground)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      fontSize: 12,
                      padding: "6px 8px",
                    }}
                    formatter={(value: number, _n, item) => [
                      `${value.toFixed(2)}%`,
                      String(item?.payload?.name ?? ""),
                    ]}
                  />
                  <Bar dataKey="value" fill="var(--color-primary)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("monthly")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 text-xs">
            {monthly.map((m) => (
              <div
                key={m.period}
                className="rounded-lg border bg-background/20 px-3 py-2 flex justify-between"
              >
                <span className="text-muted-foreground">{m.period}</span>
                <span
                  className={`font-mono font-semibold ${returnColorClass(m.return_pct)}`}
                >
                  {formatPct(m.return_pct, "—")}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{t("yearly")}</CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 text-xs">
            {yearly.map((m) => (
              <div
                key={m.period}
                className="rounded-lg border bg-background/20 px-3 py-2 flex justify-between"
              >
                <span className="text-muted-foreground">{m.period}</span>
                <span
                  className={`font-mono font-semibold ${returnColorClass(m.return_pct)}`}
                >
                  {formatPct(m.return_pct, "—")}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subscription tab
// ---------------------------------------------------------------------------

function SubscriptionTab({ strategyKey }: { strategyKey: string }) {
  const t = useTranslations("strategies.subscription")
  const { data: all, isLoading } = useSubscriptions(undefined)
  const create = useCreateSubscription()
  const remove = useDeleteSubscription()

  const subs = useMemo(
    () => (all ?? []).filter((s) => s.strategy_key === strategyKey),
    [all, strategyKey],
  )

  const [channelId, setChannelId] = useState("")
  const [schedule, setSchedule] = useState("0 30 9 * * 1")
  const [submitError, setSubmitError] = useState<string | null>(null)

  function handleCreate() {
    setSubmitError(null)
    if (!channelId.trim()) {
      setSubmitError(t("channel_required"))
      return
    }
    create.mutate(
      {
        user_id: "default",
        strategy_key: strategyKey,
        bot_channel_id: channelId.trim(),
        schedule: schedule || undefined,
        enabled: true,
      },
      {
        onSuccess: () => {
          setChannelId("")
        },
        onError: (err) => {
          setSubmitError(
            err instanceof ApiError ? err.message : (err as Error).message,
          )
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{t("create")}</CardTitle>
        </CardHeader>
        <CardContent className="pt-2 space-y-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{t("channel_id")}</span>
            <input
              type="text"
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              placeholder="oc_xxx..."
              className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{t("schedule")}</span>
            <input
              type="text"
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
              className="rounded-md border bg-background/40 px-2 py-1.5 text-xs font-mono"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSchedule("0 30 9 * * 1")}
              className="rounded-full border bg-background/40 px-3 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground"
            >
              {t("preset_weekly")}
            </button>
            <button
              type="button"
              onClick={() => setSchedule("0 5 15 * * 1-5")}
              className="rounded-full border bg-background/40 px-3 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground"
            >
              {t("preset_daily_close")}
            </button>
          </div>
          {submitError ? (
            <div className="text-xs text-destructive">{submitError}</div>
          ) : null}
          <div className="flex justify-end">
            <Button
              onClick={handleCreate}
              disabled={create.isPending}
              className="gap-2"
            >
              {create.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {t("creating")}
                </>
              ) : (
                <>
                  <Plus className="h-3.5 w-3.5" />
                  {t("create")}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">{t("title")}</CardTitle>
        </CardHeader>
        <CardContent className="pt-2 space-y-2">
          {isLoading ? (
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading...
            </div>
          ) : subs.length === 0 ? (
            <div className="text-xs text-muted-foreground">
              {t("no_subscriptions")}
            </div>
          ) : (
            subs.map((s: Subscription) => (
              <div
                key={s.id}
                className="rounded-lg border bg-background/20 px-3 py-2 flex items-center justify-between text-xs"
              >
                <div className="space-y-0.5">
                  <div className="font-mono">{s.bot_channel_id}</div>
                  <div className="text-muted-foreground font-mono">
                    {s.schedule}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove.mutate(s.id)}
                  className="rounded-md border bg-background/40 p-1.5 text-destructive hover:bg-destructive/10"
                  aria-label={t("delete")}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom strategy create/edit dialog
// ---------------------------------------------------------------------------

function CustomStrategyDialog({
  mode,
  existing,
  onClose,
}: {
  mode: "create" | "edit"
  existing?: UserStrategy
  onClose: () => void
}) {
  const t = useTranslations("strategies.custom_form")
  const tStrat = useTranslations("strategies")
  const { data: catalog } = useStrategies()
  const create = useCreateCustomStrategy()
  const update = useUpdateCustomStrategy()
  const remove = useDeleteCustomStrategy()

  const [name, setName] = useState(existing?.name ?? "")
  const [description, setDescription] = useState(existing?.description ?? "")
  const [baseTemplate, setBaseTemplate] = useState<BuiltInStrategyKey>(
    (existing?.base_template as BuiltInStrategyKey) ?? "strong_uptrend",
  )

  const templateDefaults = useMemo(() => {
    const found = (catalog?.strategies ?? []).find(
      (s) => s.key === baseTemplate,
    )
    return found?.default_params ?? {}
  }, [catalog?.strategies, baseTemplate])

  const [params, setParams] = useState<Record<string, number>>(
    existing?.params ?? templateDefaults,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // When base template changes (in create mode), reset params to that template's defaults.
    if (mode === "create") {
      setParams({ ...templateDefaults })
    }
  }, [baseTemplate, templateDefaults, mode])

  function handleSubmit() {
    setError(null)
    if (!name.trim()) {
      setError(t("name_required"))
      return
    }
    if (mode === "create") {
      create.mutate(
        {
          name: name.trim(),
          base_template: baseTemplate,
          params,
          description: description.trim() || null,
        },
        {
          onSuccess: () => onClose(),
          onError: (err) =>
            setError(
              err instanceof ApiError ? err.message : (err as Error).message,
            ),
        },
      )
    } else if (existing) {
      update.mutate(
        {
          id: existing.id,
          payload: {
            name: name.trim(),
            params,
            description: description.trim() || null,
          },
        },
        {
          onSuccess: () => onClose(),
          onError: (err) =>
            setError(
              err instanceof ApiError ? err.message : (err as Error).message,
            ),
        },
      )
    }
  }

  function handleDelete() {
    if (!existing) return
    if (typeof window !== "undefined" && !window.confirm(t("delete_confirm")))
      return
    remove.mutate(existing.id, {
      onSuccess: () => onClose(),
    })
  }

  const submitting = create.isPending || update.isPending

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
      <div className="relative w-full max-w-lg rounded-xl border bg-background shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-base font-bold font-display">
            {mode === "create" ? t("title") : t("edit_title")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3 p-4">
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{t("name")}</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded-md border bg-background/40 px-2 py-1.5 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{t("description")}</span>
            <textarea
              value={description ?? ""}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
            />
          </label>
          {mode === "create" ? (
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("base_template")}</span>
              <select
                value={baseTemplate}
                onChange={(e) =>
                  setBaseTemplate(e.target.value as BuiltInStrategyKey)
                }
                className="rounded-md border bg-background/40 px-2 py-1.5 text-sm"
              >
                {BUILTIN_KEYS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="pt-2 border-t border-muted/30">
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80 mb-2">
              {t("params_section")}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(params).map(([k, v]) => (
                <NumField
                  key={k}
                  label={paramLabel(tStrat, k)}
                  value={v}
                  onChange={(nv) =>
                    setParams((prev) => ({ ...prev, [k]: Number(nv) }))
                  }
                />
              ))}
            </div>
          </div>

          {error ? <div className="text-xs text-destructive">{error}</div> : null}
        </div>
        <div className="flex items-center justify-between gap-2 p-4 border-t bg-background/40">
          <div>
            {mode === "edit" ? (
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={remove.isPending}
                className="gap-2"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {t("delete")}
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} className="gap-2">
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {t("submitting")}
                </>
              ) : (
                t("submit")
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
