"use client"

import Link from "next/link"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Activity, BarChart3, Newspaper, TrendingDown, TrendingUp, Sparkles } from "lucide-react"
import { useDragonTigerList, useLimitUpBoard, useMarketNews, useMarketOverview } from "@quant/hooks"

function formatCompactNumber(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }

  return new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value)
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }

  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

export default function DashboardPage() {
  const t = useTranslations("dashboard")
  const { data, isLoading, isError } = useMarketOverview()
  const latestDragonTigerDate = data?.latest_dragon_tiger_date ?? ""
  const latestLimitUpDate = data?.latest_limit_up_date ?? ""
  const latestNewsDate = data?.latest_news_date ?? ""

  const { data: dragonTigerItems, isLoading: isDTLoading } = useDragonTigerList(latestDragonTigerDate, {
    enabled: !!latestDragonTigerDate,
  })
  const { data: limitUpItems, isLoading: isZTLoading } = useLimitUpBoard(latestLimitUpDate, {
    enabled: !!latestLimitUpDate,
  })
  const { data: newsItems, isLoading: isNewsLoading } = useMarketNews(latestNewsDate, 6, {
    enabled: !!latestNewsDate,
  })

  const upCount = data?.latest_dragon_tiger_count ?? 0
  const downCount = data?.latest_limit_up_count ?? 0
  const totalSentiment = upCount + downCount
  const upPercent = totalSentiment > 0 ? (upCount / totalSentiment) * 100 : 50

  const kpiCards = [
    {
      title: t("kpi.tracked_stocks"),
      value: data?.stock_count?.toLocaleString() ?? "-",
      description: t("kpi.tracked_description"),
      icon: BarChart3,
      glowClass: "",
    },
    {
      title: t("kpi.dragon_tiger_records"),
      value: data?.latest_dragon_tiger_count?.toLocaleString() ?? "-",
      description: t("kpi.dragon_tiger_description"),
      icon: TrendingUp,
      className: "text-stock-up",
      glowClass: "stock-up-glow",
    },
    {
      title: t("kpi.limit_up_records"),
      value: data?.latest_limit_up_count?.toLocaleString() ?? "-",
      description: t("kpi.limit_up_description"),
      icon: TrendingUp,
      className: "text-stock-up",
      glowClass: "stock-up-glow",
    },
    {
      title: t("kpi.news_items"),
      value: data?.latest_news_count?.toLocaleString() ?? "-",
      description: t("kpi.news_description"),
      icon: Activity,
      glowClass: "",
    },
  ]

  return (
    <div className="space-y-6">
      {/* Dashboard Title Banner */}
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>
        
        {/* Real-time sync date badge */}
        {!isLoading && data?.latest_trade_date && (
          <div className="inline-flex items-center gap-2 rounded-full border bg-background/50 px-3 py-1.5 text-xs font-semibold backdrop-blur-md premium-glass-card shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>{t("latest_trade_date", { date: data.latest_trade_date })}</span>
          </div>
        )}
      </div>

      {/* System Status Glass Banner */}
      <Card className="premium-glass-card border bg-background/40 overflow-hidden relative shadow-md">
        <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
          <Sparkles className="h-24 w-24 text-primary" />
        </div>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg font-semibold font-display flex items-center gap-2">
            {t("spine.title")}
          </CardTitle>
          <CardDescription>
            {isLoading
              ? t("spine.connecting")
              : isError
                ? t("spine.error")
                : t("spine.active")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 text-xs md:grid-cols-3">
          <div className="rounded-xl border bg-background/20 p-4 backdrop-blur-md flex flex-col justify-between min-h-[90px] transition-all hover:bg-background/40">
            <div className="uppercase tracking-[0.16em] text-muted-foreground/80 font-semibold">{t("spine.contract_title")}</div>
            <div className="mt-2 text-sm font-medium text-foreground">{t("spine.contract_desc")}</div>
          </div>
          <div className="rounded-xl border bg-background/20 p-4 backdrop-blur-md flex flex-col justify-between min-h-[90px] transition-all hover:bg-background/40">
            <div className="uppercase tracking-[0.16em] text-muted-foreground/80 font-semibold">{t("spine.db_title")}</div>
            <div className="mt-2 text-sm font-medium text-foreground">{t("spine.db_desc")}</div>
          </div>
          <div className="rounded-xl border bg-background/20 p-4 backdrop-blur-md flex flex-col justify-between min-h-[90px] transition-all hover:bg-background/40">
            <div className="uppercase tracking-[0.16em] text-muted-foreground/80 font-semibold">{t("spine.pipeline_title")}</div>
            <div className="mt-2 text-sm font-medium text-foreground">{t("spine.pipeline_desc")}</div>
          </div>
        </CardContent>
      </Card>

      {/* KPI Cards Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, idx) => (
              <div key={idx} className="h-28 rounded-xl border shimmer-loading opacity-70" />
            ))
          : kpiCards.map((card) => (
              <Card 
                key={card.title} 
                className={`premium-glass-card premium-glass-hover bg-background/40 border transition-all ${card.glowClass}`}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">
                    {card.title}
                  </CardTitle>
                  <card.icon className={`h-4 w-4 ${card.className ?? "text-muted-foreground"}`} />
                </CardHeader>
                <CardContent>
                  <div className={`text-3xl font-bold font-display tracking-tight ${card.className ?? ""}`}>
                    {card.value}
                  </div>
                  <CardDescription className="text-xs mt-1 text-muted-foreground/90">{card.description}</CardDescription>
                </CardContent>
              </Card>
            ))}
      </div>

      {/* Market Sentiment Bar */}
      {!isLoading && totalSentiment > 0 && (
        <div className="premium-glass-card bg-background/40 p-4 rounded-xl space-y-3 shadow-md border">
          <div className="flex justify-between items-center text-xs font-semibold uppercase tracking-wider">
            <span className="text-stock-up flex items-center gap-1">
              <TrendingUp className="h-3.5 w-3.5" /> {t("sentiment.title_up", { upCount })}
            </span>
            <span className="text-muted-foreground text-[10px]">{t("sentiment.energy_ratio")}</span>
            <span className="text-stock-down flex items-center gap-1">
              {t("sentiment.title_down", { downCount })} <TrendingDown className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted flex">
            <div className="h-full bg-stock-up transition-all duration-700 ease-out" style={{ width: `${upPercent}%` }} />
            <div className="h-full bg-stock-down transition-all duration-700 ease-out flex-1" />
          </div>
          <div className="text-center text-[10px] text-muted-foreground">
            {t("sentiment.description", { upPercent: upPercent.toFixed(0), downPercent: (100 - upPercent).toFixed(0) })}
          </div>
        </div>
      )}

      {/* Snapshots Grid */}
      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        {/* Dragon Tiger Snapshot */}
        <Card className="premium-glass-card bg-background/30 shadow-md">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 font-display text-lg font-bold">
              <TrendingUp className="h-5 w-5 text-stock-up" />
              {t("snapshots.dragon_tiger_title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {latestDragonTigerDate
                ? t("snapshots.latest_session", { date: latestDragonTigerDate })
                : t("snapshots.sync_required")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isDTLoading ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="h-20 rounded-xl border shimmer-loading opacity-60" />
              ))
            ) : dragonTigerItems?.length ? (
              dragonTigerItems.slice(0, 5).map((item, index) => (
                <Link
                  key={item.id}
                  href={`/stocks/${item.code}`}
                  className="flex items-start justify-between gap-4 rounded-xl border border-muted/50 p-4 transition-all duration-300 hover:scale-[1.01] hover:border-stock-up/40 hover:bg-background/50 hover:shadow-md hover:shadow-stock-up/5"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-stock-up/10 text-[10px] font-bold text-stock-up">
                        {index + 1}
                      </span>
                      <span className="font-semibold text-foreground text-sm">{item.name}</span>
                      <span className="text-xs text-muted-foreground font-mono">{item.code}</span>
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-2 mt-1 leading-5">{item.reason || t("snapshots.no_reason")}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-bold text-stock-up font-display text-base">{formatCompactNumber(item.net_buy)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">{t("snapshots.net_buy")}</div>
                  </div>
                </Link>
              ))
            ) : (
              <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20">
                {t("snapshots.no_dragon_tiger_data")}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Limit Up Board Snapshot */}
        <Card className="premium-glass-card bg-background/30 shadow-md">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 font-display text-lg font-bold">
              <TrendingUp className="h-5 w-5 text-stock-up" />
              {t("snapshots.limit_up_title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {latestLimitUpDate
                ? t("snapshots.latest_session", { date: latestLimitUpDate })
                : t("snapshots.sync_required")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isZTLoading ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="h-20 rounded-xl border shimmer-loading opacity-60" />
              ))
            ) : limitUpItems?.length ? (
              limitUpItems.slice(0, 5).map((item, index) => (
                <Link
                  key={item.id}
                  href={`/stocks/${item.code}`}
                  className="block rounded-xl border border-muted/50 p-4 transition-all duration-300 hover:scale-[1.01] hover:border-stock-up/40 hover:bg-background/50 hover:shadow-md hover:shadow-stock-up/5"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-stock-up/10 text-[10px] font-bold text-stock-up">
                        {index + 1}
                      </span>
                      <div>
                        <span className="font-semibold text-foreground text-sm">{item.name}</span>
                        <span className="text-[10px] text-muted-foreground ml-2 font-mono">{item.code}</span>
                      </div>
                    </div>
                    <div className="text-right text-stock-up font-bold font-display text-sm">
                      {formatPercent(item.change_pct)}
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground border-t border-muted/30 pt-2">
                    <span className="line-clamp-1 flex-1 pr-4">{item.reason || t("snapshots.no_limit_up_reason")}</span>
                    <span className="shrink-0 font-mono text-[10px] bg-muted/50 px-2 py-0.5 rounded">{t("snapshots.open_times", { times: item.open_times ?? 0 })}</span>
                  </div>
                </Link>
              ))
            ) : (
              <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20">
                {t("snapshots.no_limit_up_data")}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Market News Flow */}
      <Card className="premium-glass-card bg-background/30 shadow-md">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 font-display text-lg font-bold">
            <Newspaper className="h-5 w-5 text-primary" />
            {t("news.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {latestNewsDate
              ? t("news.latest_batch", { date: latestNewsDate })
              : t("news.feed_inactive")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {isNewsLoading ? (
            Array.from({ length: 6 }).map((_, idx) => (
              <div key={idx} className="h-32 rounded-xl border shimmer-loading opacity-60" />
            ))
          ) : newsItems?.length ? (
            newsItems.map((item) => (
              <a
                key={item.id}
                href={item.url || "#"}
                target={item.url ? "_blank" : undefined}
                rel={item.url ? "noreferrer" : undefined}
                className="group flex flex-col justify-between rounded-xl border border-muted/50 p-4 transition-all duration-300 hover:border-primary/30 hover:bg-background/40 hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between gap-3 text-[10px] text-muted-foreground font-mono">
                    <span className="bg-primary/10 text-primary px-2 py-0.5 rounded font-semibold uppercase tracking-wider">
                      {item.source || t("news.default_source")}
                    </span>
                    <span>{item.published_at ? item.published_at.slice(11, 16) : item.trade_date}</span>
                  </div>
                  <div className="mt-3 line-clamp-3 text-xs font-semibold text-foreground/90 group-hover:text-primary transition-colors leading-5">
                    {item.title}
                  </div>
                </div>
                {item.code && (
                  <div className="mt-3 pt-2 border-t border-muted/30 text-[10px] font-mono text-muted-foreground">
                    {t("news.related_code")} <span className="font-semibold text-primary">{item.code}</span>
                  </div>
                )}
              </a>
            ))
          ) : (
            <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 md:col-span-2 xl:col-span-3">
              {t("news.no_news_data")}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
