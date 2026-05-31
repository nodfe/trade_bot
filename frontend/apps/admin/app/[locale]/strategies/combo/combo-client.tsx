"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  ApiError,
  useRunStrategyCombo,
  useStrategies,
  type BuiltInStrategyKey,
  type StrategyComboItem,
  type StrategyComboRequest,
  type StrategyComboResponse,
} from "@quant/hooks"
import { useEChartsTheme } from "@quant/charts"
import ReactECharts from "echarts-for-react"
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

const BUILTIN_KEYS: BuiltInStrategyKey[] = [
  "strong_uptrend",
  "volume_breakout",
  "pullback_watch",
  "first_limit_up_low",
  "leader_streak",
  "zt_relay",
  "lhb_follow",
]

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function returnColorClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "text-muted-foreground"
  if (value > 0) return "text-stock-up"
  if (value < 0) return "text-stock-down"
  return "text-foreground"
}

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  return value.toFixed(2)
}

interface ItemDraft {
  strategy_key: BuiltInStrategyKey
  weight: number
}

export function ComboClient() {
  const t = useTranslations("strategies.combo")
  const { data: catalog } = useStrategies()
  const run = useRunStrategyCombo()

  const [items, setItems] = useState<ItemDraft[]>([
    { strategy_key: "strong_uptrend", weight: 1 },
    { strategy_key: "volume_breakout", weight: 1 },
  ])
  const [rebalance, setRebalance] = useState<
    "daily" | "weekly" | "biweekly" | "monthly"
  >("weekly")
  const [topN, setTopN] = useState(10)
  const [weighting, setWeighting] = useState<"equal" | "score">("equal")
  const [startDate, setStartDate] = useState(isoDaysAgo(180))
  const [endDate, setEndDate] = useState(todayIso())

  const totalWeight = useMemo(
    () => items.reduce((s, x) => s + (x.weight > 0 ? x.weight : 0), 0),
    [items],
  )

  function updateItem(idx: number, patch: Partial<ItemDraft>) {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    )
  }
  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx))
  }
  function addItem() {
    setItems((prev) => [
      ...prev,
      { strategy_key: "strong_uptrend", weight: 1 },
    ])
  }

  function handleCompute() {
    if (items.length === 0) return
    const payload: StrategyComboRequest = {
      items: items.map(
        (it): StrategyComboItem => ({
          strategy_key: it.strategy_key,
          weight: it.weight,
        }),
      ),
      rebalance,
      start_date: startDate,
      end_date: endDate,
      top_n: topN,
      weighting,
      initial_capital: 100_000,
    }
    run.mutate(payload)
  }

  const errMsg = run.error
    ? run.error instanceof ApiError
      ? run.error.message
      : (run.error as Error).message
    : null

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Link
          href="/strategies"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("back_to_catalog")}
        </Link>
      </div>

      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">{t("title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.length === 0 ? (
            <div className="text-xs text-muted-foreground">
              {t("no_items")}
            </div>
          ) : (
            items.map((it, idx) => {
              const normalized =
                totalWeight > 0 && it.weight > 0
                  ? (it.weight / totalWeight) * 100
                  : 0
              return (
                <div
                  key={idx}
                  className="grid grid-cols-1 sm:grid-cols-[2fr_1fr_1fr_auto] gap-3 items-end"
                >
                  <label className="flex flex-col gap-1 text-xs">
                    <span className="text-muted-foreground">Strategy</span>
                    <select
                      value={it.strategy_key}
                      onChange={(e) =>
                        updateItem(idx, {
                          strategy_key: e.target.value as BuiltInStrategyKey,
                        })
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
                  <label className="flex flex-col gap-1 text-xs">
                    <span className="text-muted-foreground">{t("weight")}</span>
                    <input
                      type="range"
                      min={0}
                      max={5}
                      step={0.1}
                      value={it.weight}
                      onChange={(e) =>
                        updateItem(idx, { weight: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {it.weight.toFixed(2)}
                    </span>
                  </label>
                  <div className="flex flex-col gap-1 text-xs">
                    <span className="text-muted-foreground">
                      {t("weight_normalized")}
                    </span>
                    <span className="text-sm font-mono font-semibold">
                      {normalized.toFixed(1)}%
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeItem(idx)}
                    className="rounded-md border bg-background/40 p-1.5 text-destructive hover:bg-destructive/10"
                    aria-label={t("remove")}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })
          )}

          <div>
            <Button
              variant="outline"
              onClick={addItem}
              className="gap-2"
              type="button"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("add_item")}
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-muted/30">
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("rebalance")}</span>
              <select
                value={rebalance}
                onChange={(e) =>
                  setRebalance(
                    e.target.value as
                      | "daily"
                      | "weekly"
                      | "biweekly"
                      | "monthly",
                  )
                }
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              >
                {["daily", "weekly", "biweekly", "monthly"].map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("top_n")}</span>
              <input
                type="number"
                value={topN}
                onChange={(e) => setTopN(Number(e.target.value))}
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("weighting")}</span>
              <select
                value={weighting}
                onChange={(e) =>
                  setWeighting(e.target.value as "equal" | "score")
                }
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              >
                {["equal", "score"].map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("start_date")}</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("end_date")}</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded-md border bg-background/40 px-2 py-1.5 text-xs"
              />
            </label>
          </div>

          <div className="flex justify-end pt-2">
            <Button
              onClick={handleCompute}
              disabled={run.isPending || items.length === 0}
              className="gap-2"
            >
              {run.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {t("computing")}
                </>
              ) : (
                t("compute")
              )}
            </Button>
          </div>
          {errMsg ? (
            <div className="flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="h-4 w-4" /> {errMsg}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {run.data ? <ComboResults result={run.data} catalogStrategies={catalog?.strategies ?? []} /> : null}
    </div>
  )
}

function ComboResults({
  result,
  catalogStrategies: _catalog,
}: {
  result: StrategyComboResponse
  catalogStrategies: unknown[]
}) {
  const t = useTranslations("strategies.combo")
  const theme = useEChartsTheme()
  void _catalog

  const chartData = useMemo(() => {
    const map = new Map<string, Record<string, number | string>>()
    for (const p of result.composite_equity_curve) {
      map.set(p.date, { date: p.date, composite: p.value })
    }
    for (const series of result.per_strategy_curves) {
      for (const pt of series.equity_curve) {
        const cur = map.get(pt.date) ?? { date: pt.date }
        cur[series.strategy_key] = pt.value
        map.set(pt.date, cur)
      }
    }
    return Array.from(map.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    )
  }, [result])

  const corrKeys = Object.keys(result.correlation_matrix)
  const heatmapData: [number, number, number][] = []
  corrKeys.forEach((ki, i) => {
    corrKeys.forEach((kj, j) => {
      const v = result.correlation_matrix[ki]?.[kj] ?? 0
      heatmapData.push([j, i, Number(v.toFixed(3))])
    })
  })
  const heatmapOption = {
    tooltip: {
      position: "top",
      formatter: (p: { value: number[] }) => {
        const j = p.value[0]
        const i = p.value[1]
        const v = p.value[2]
        const a = corrKeys[i] ?? ""
        const b = corrKeys[j] ?? ""
        const color = v >= 0 ? "#ef4444" : "#22c55e"
        return `<div style="font-size:12px;line-height:1.5">
          <div style="opacity:.7;font-size:11px">${a} × ${b}</div>
          <div style="color:${color};font-weight:600">ρ = ${v.toFixed(3)}</div>
        </div>`
      },
    },
    grid: { left: 100, right: 10, top: 10, bottom: 60 },
    xAxis: { type: "category", data: corrKeys, splitArea: { show: true } },
    yAxis: { type: "category", data: corrKeys, splitArea: { show: true } },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#22c55e", "#e5e7eb", "#ef4444"] },
    },
    series: [
      {
        type: "heatmap",
        data: heatmapData,
        label: { show: true },
      },
    ],
    backgroundColor: theme.backgroundColor,
    textStyle: theme.textStyle,
  }

  const seriesColors = [
    "var(--color-stock-up)",
    "var(--color-stock-down)",
    "var(--color-chart-1)",
    "var(--color-chart-2)",
    "var(--color-chart-3)",
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <ComboKpiCell
          label={t("kpi_total")}
          value={formatPct(result.kpi.total_return_pct)}
          valueClass={returnColorClass(result.kpi.total_return_pct)}
        />
        <ComboKpiCell
          label={t("kpi_annualized")}
          value={formatPct(result.kpi.annualized_return_pct)}
          valueClass={returnColorClass(result.kpi.annualized_return_pct)}
        />
        <ComboKpiCell
          label={t("kpi_sharpe")}
          value={formatNumber(result.kpi.sharpe_ratio)}
          valueClass="text-foreground"
        />
        <ComboKpiCell
          label={t("kpi_sortino")}
          value={formatNumber(result.kpi.sortino_ratio)}
          valueClass="text-foreground"
        />
        <ComboKpiCell
          label={t("kpi_calmar")}
          value={formatNumber(result.kpi.calmar_ratio)}
          valueClass="text-foreground"
        />
        <ComboKpiCell
          label={t("kpi_max_dd")}
          value={`-${result.kpi.max_drawdown_pct.toFixed(2)}%`}
          valueClass="text-stock-down"
        />
      </div>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("composite")} / {t("per_strategy")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="h-[320px] w-full">
            <ResponsiveContainer>
              <LineChart data={chartData}>
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
                  formatter={(value: number, name: string) => {
                    const base = chartData[0]?.[name as keyof (typeof chartData)[number]] as
                      | number
                      | undefined
                    const delta =
                      typeof base === "number" && base !== 0
                        ? ((value - base) / base) * 100
                        : 0
                    const sign = delta >= 0 ? "+" : ""
                    return [
                      `${Number(value).toLocaleString()}  ${sign}${delta.toFixed(2)}%`,
                      name,
                    ] as [string, string]
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="composite"
                  stroke="var(--color-primary)"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                />
                {result.per_strategy_curves.map((s, i) => (
                  <Line
                    key={s.strategy_key + "_" + i}
                    type="monotone"
                    dataKey={s.strategy_key}
                    stroke={seriesColors[i % seriesColors.length]}
                    strokeWidth={1.25}
                    strokeDasharray="3 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="premium-glass-card border bg-background/30 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {t("correlation")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div style={{ height: 280 }}>
            <ReactECharts
              option={heatmapOption}
              style={{ height: "100%", width: "100%" }}
              notMerge
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function ComboKpiCell({
  label,
  value,
  valueClass,
}: {
  label: string
  value: string
  valueClass: string
}) {
  return (
    <div className="rounded-xl border bg-background/20 p-3 space-y-1">
      <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
        {label}
      </div>
      <div className={`text-sm font-bold font-mono ${valueClass}`}>{value}</div>
    </div>
  )
}
