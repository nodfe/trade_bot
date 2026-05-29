"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { createWatchlist, stockKeys, useStockScreen } from "@quant/hooks"
import { Check, Bookmark, Sliders, Newspaper, Flame, Activity } from "lucide-react"

const screenOptions = [
  {
    value: "strong_uptrend",
    glowClass: "stock-up-glow",
  },
  {
    value: "volume_breakout",
    glowClass: "stock-up-glow",
  },
  {
    value: "pullback_watch",
    glowClass: "stock-down-glow",
  },
] as const

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

type ScreenParams = {
  limit: number | undefined
  min_return_20d_pct: number | undefined
  min_return_5d_pct: number | undefined
  min_volume_ratio: number | undefined
  max_return_5d_pct: number | undefined
}

type ScreenersClientProps = {
  initialScreenType?: string
}

export function ScreenersClient({ initialScreenType }: ScreenersClientProps) {
  const t = useTranslations("screeners")
  const queryClient = useQueryClient()
  const [screenType, setScreenType] = useState("strong_uptrend")
  const [saveStatus, setSaveStatus] = useState<string>("")
  const [watchlistName, setWatchlistName] = useState("")
  const [autoRefresh, setAutoRefresh] = useState("daily")
  const [params, setParams] = useState<ScreenParams>({
    limit: 12,
    min_return_20d_pct: 5,
    min_return_5d_pct: 0,
    min_volume_ratio: 1.3,
    max_return_5d_pct: 15,
  })

  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useStockScreen(
    screenType,
    params,
    {
      retry: false,
    },
  )

  // Track which (screenType, params) combination produced the currently
  // displayed `data`. Save is only allowed when params match what was
  // actually run — otherwise the saved watchlist would not match the
  // displayed candidates.
  const [lastRun, setLastRun] = useState<{
    screenType: string
    paramsKey: string
  } | null>(null)

  const paramsKey = useMemo(() => JSON.stringify(params), [params])

  useEffect(() => {
    if (data && !isFetching) {
      setLastRun({ screenType, paramsKey })
    }
    // We intentionally only sync when the query settles successfully.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataUpdatedAt])

  const paramsMatchLastRun =
    !!lastRun && lastRun.screenType === screenType && lastRun.paramsKey === paramsKey

  useEffect(() => {
    if (!initialScreenType) return

    const matched = screenOptions.find((option) => option.value === initialScreenType)
    if (matched) {
      setScreenType(matched.value)
    }
  }, [initialScreenType])

  const updateParam = (key: keyof ScreenParams, value: string) => {
    // Empty input → undefined (omit the param) rather than 0, which the
    // backend would otherwise treat as a real "min = 0" filter.
    setParams((current) => ({
      ...current,
      [key]: value === "" ? undefined : Number(value),
    }))
  }

  const handleSaveWatchlist = async () => {
    if (!data?.items?.length) {
      setSaveStatus(t("save.no_results"))
      return
    }
    if (!paramsMatchLastRun) {
      setSaveStatus(t("save.params_changed"))
      return
    }

    const payload = {
      name: watchlistName.trim() || `${screenType.toUpperCase()}-${new Date().toISOString().slice(0, 10)}`,
      source_screen_type: screenType,
      screen_params_json: JSON.stringify(params),
      auto_refresh: autoRefresh,
      notes: `Saved from screeners console using: ${screenType}`,
      items: data.items.map((item) => ({
        stock_code: item.symbol,
        stock_name: item.name,
        match_reason: item.match_reason,
        hot_tags: item.hot_tags,
      })),
    }

    try {
      setSaveStatus(t("save.saving"))
      await createWatchlist(payload)
      await queryClient.invalidateQueries({ queryKey: stockKeys.watchlists() })
      setWatchlistName("")
      setSaveStatus(t("save.save_success"))
      setTimeout(() => setSaveStatus(""), 3000)
    } catch {
      setSaveStatus(t("save.save_failed"))
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("subtitle")}
        </p>
      </div>

      {/* Screen Options Grid */}
      <div className="grid gap-4 md:grid-cols-3">
        {screenOptions.map((option) => {
          const isActive = screenType === option.value
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setScreenType(option.value)}
              className={`group relative rounded-2xl border text-left p-5 transition-all duration-300 premium-glass-card premium-glass-hover ${
                isActive 
                  ? "border-primary bg-primary/5 shadow-md shadow-primary/5" 
                  : "bg-background/40 hover:border-primary/30"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                  {t(`options.${option.value}.badge` as any)}
                </span>
                {isActive && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check className="h-3 w-3" />
                  </span>
                )}
              </div>
              <div className="mt-3 font-semibold text-sm text-foreground group-hover:text-primary transition-colors">
                {t(`options.${option.value}.label` as any)}
              </div>
              <div className="mt-2 text-xs text-muted-foreground leading-5">
                {t(`options.${option.value}.description` as any)}
              </div>
            </button>
          )
        })}
      </div>

      {/* Parameters Panel */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Sliders className="h-4 w-4 text-muted-foreground" /> {t("tuning.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("tuning.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 text-xs">
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-muted-foreground">{t("tuning.max_matches")}</span>
            <input
              type="number"
              value={params.limit ?? ""}
              onChange={(e) => updateParam("limit", e.target.value)}
              className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-muted-foreground">{t("tuning.min_return_20d")}</span>
            <input
              type="number"
              value={params.min_return_20d_pct ?? ""}
              onChange={(e) => updateParam("min_return_20d_pct", e.target.value)}
              className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-muted-foreground">{t("tuning.min_return_5d")}</span>
            <input
              type="number"
              value={params.min_return_5d_pct ?? ""}
              onChange={(e) => updateParam("min_return_5d_pct", e.target.value)}
              className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-muted-foreground">{t("tuning.min_volume_ratio")}</span>
            <input
              type="number"
              step="0.1"
              value={params.min_volume_ratio ?? ""}
              onChange={(e) => updateParam("min_volume_ratio", e.target.value)}
              className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-muted-foreground">{t("tuning.max_return_5d")}</span>
            <input
              type="number"
              value={params.max_return_5d_pct ?? ""}
              onChange={(e) => updateParam("max_return_5d_pct", e.target.value)}
              className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
        </CardContent>
      </Card>

      {/* Save Action Workspace */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Bookmark className="h-4 w-4 text-muted-foreground" /> {t("save_workspace.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {isLoading
              ? t("save_workspace.scanning")
              : isError
                ? t("save_workspace.error")
                : t("save_workspace.matches_found", { count: data?.total ?? 0 })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 items-end text-xs">
            <div className="flex flex-col gap-2">
              <span className="font-semibold text-muted-foreground">{t("save_workspace.watchlist_name")}</span>
              <input
                type="text"
                value={watchlistName}
                onChange={(e) => setWatchlistName(e.target.value)}
                placeholder={t("save.name_placeholder")}
                className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
              />
            </div>
            <div className="flex flex-col gap-2">
              <span className="font-semibold text-muted-foreground">{t("save_workspace.auto_sync")}</span>
              <select
                value={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.value)}
                className="w-full rounded-lg border bg-background/50 px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
              >
                <option value="daily">{t("save_workspace.daily_sync")}</option>
                <option value="manual">{t("save_workspace.manual_sync")}</option>
              </select>
            </div>
            <button
              type="button"
              onClick={handleSaveWatchlist}
              disabled={isLoading || !data?.items?.length || !paramsMatchLastRun}
              title={!paramsMatchLastRun ? t("save.params_changed") : undefined}
              className="w-full rounded-lg bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 py-2 h-[34px] transition-colors shadow-sm disabled:opacity-50 disabled:pointer-events-none"
            >
              {t("save_workspace.persist")}
            </button>
          </div>
          {saveStatus && (
            <div className="text-xs text-primary font-semibold flex items-center gap-1 bg-primary/10 p-2.5 rounded-lg border border-primary/20">
              <Activity className="h-3.5 w-3.5 animate-pulse" /> {saveStatus}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Candidate Cards Grid */}
      <Card className="premium-glass-card border bg-background/20 shadow-md">
        <CardHeader className="pb-4 border-b border-muted/30">
          <CardTitle className="font-display text-lg font-bold">
            {t("candidates.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("candidates.subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 pt-6">
          {isLoading ? (
            Array.from({ length: 6 }).map((_, idx) => (
              <div key={idx} className="h-56 rounded-2xl border shimmer-loading opacity-60" />
            ))
          ) : data?.items?.length ? (
            data.items.map((item) => (
              <Link
                key={`${screenType}-${item.symbol}`}
                href={`/stocks/${item.symbol}`}
                className="group relative rounded-2xl border border-muted/50 p-5 bg-background/40 transition-all duration-300 hover:scale-[1.01] hover:border-primary/40 hover:bg-background/60 hover:shadow-lg flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-base text-foreground group-hover:text-primary transition-colors">
                        {item.name}
                      </span>
                      <span className="text-[10px] text-muted-foreground ml-2 font-mono">{item.symbol}</span>
                    </div>
                    <span className="inline-flex h-5 items-center justify-center rounded bg-muted/60 px-2 py-0.5 text-[9px] font-semibold text-muted-foreground">
                      {item.market}
                    </span>
                  </div>
                  
                  {/* Performance Indicators */}
                  <div className="mt-4 grid grid-cols-3 gap-3 border-y border-muted/20 py-2 text-xs">
                    <div>
                      <div className="text-[10px] text-muted-foreground font-semibold">{t("candidates.horizon_5d")}</div>
                      <div className={`mt-1 font-bold font-mono ${(item.return_5d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                        {formatPercent(item.return_5d_pct)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground font-semibold">{t("candidates.horizon_20d")}</div>
                      <div className={`mt-1 font-bold font-mono ${(item.return_20d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                        {formatPercent(item.return_20d_pct)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground font-semibold">{t("candidates.vol_ratio_5d")}</div>
                      <div className="mt-1 font-bold font-mono text-foreground">
                        {item.volume_ratio_5d?.toFixed(2) ?? "-"}x
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 text-xs text-muted-foreground leading-5 min-h-[40px]">
                    {item.match_reason}
                  </div>
                </div>

                <div>
                  {/* Hot Tags capsules */}
                  {!!item.hot_tags.length && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {item.hot_tags.map((tag) => (
                        <span 
                          key={tag} 
                          className="inline-flex items-center gap-1 rounded-full bg-primary/5 border border-primary/10 px-2.5 py-0.5 text-[9px] font-semibold text-primary/95"
                        >
                          <Flame className="h-2.5 w-2.5 text-primary animate-pulse" /> {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* News Headlines expandable */}
                  {!!item.related_news_headlines.length && (
                    <div className="mt-4 rounded-xl bg-muted/30 p-3 text-[10px] text-muted-foreground border border-muted/40">
                      <div className="mb-2 font-semibold uppercase tracking-wider text-muted-foreground/80 flex items-center gap-1">
                        <Newspaper className="h-3 w-3" /> {t("candidates.related_news")}
                      </div>
                      {item.related_news_headlines.map((headline) => (
                        <div key={headline} className="line-clamp-2 leading-relaxed mt-1">
                          • {headline}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Link>
            ))
          ) : (
            <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 md:col-span-2 xl:col-span-3">
              {t("candidates.no_candidates")}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
