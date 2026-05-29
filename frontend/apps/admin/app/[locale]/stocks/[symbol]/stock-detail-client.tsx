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
import { summarizeWatchlistParams } from "@/lib/watchlist-utils"
import { useStockAnalysis, useStockDetail, useStockKline, useStockQuote, useWatchlists } from "@quant/hooks"
import { KLineChart } from "@quant/charts"
import { ArrowLeft, Sparkles, TrendingUp, TrendingDown, Activity, Info, BarChart3 } from "lucide-react"

function formatNumber(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }

  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value)
}

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }

  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

type StockDetailClientProps = {
  symbol: string
  sourceContext?: {
    from?: string
    watchlistId?: string
  }
}

export function StockDetailClient({ symbol, sourceContext }: StockDetailClientProps) {
  const t = useTranslations("stocks")
  const tCommon = useTranslations("common")
  const tWatchlists = useTranslations("watchlists")
  
  const { data: stock } = useStockDetail(symbol)
  const { data: quote } = useStockQuote(symbol, {
    retry: false,
  })
  const { data: analysis } = useStockAnalysis(symbol, {
    retry: false,
  })
  const { data: kline, isLoading: isKlineLoading } = useStockKline({
    symbol,
    limit: 60,
  })
  
  const watchlistId = sourceContext?.watchlistId
  const fromWatchlist = sourceContext?.from === "watchlist"
  const { data: watchlists } = useWatchlists({
    enabled: fromWatchlist,
  })
  const sourceWatchlist = watchlists?.find((watchlist) => watchlist.id === watchlistId)
  const sourceSummary = summarizeWatchlistParams(sourceWatchlist?.screen_params_json, tWatchlists)

  const latestBar = kline?.[kline.length - 1]
  const previousBar = kline && kline.length > 1 ? kline[kline.length - 2] : null
  const barChange = latestBar && previousBar ? latestBar.close - previousBar.close : null

  // Determine sentiment state for glows
  const priceChange = quote?.change ?? barChange ?? 0
  const isPriceUp = priceChange >= 0
  const glowBorderClass = isPriceUp ? "stock-up-glow" : "stock-down-glow"

  return (
    <div className="space-y-6">
      {/* Return Back Link & Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1.5">
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <Link href="/" className="hover:text-foreground transition-colors flex items-center gap-1">
              <ArrowLeft className="h-3.5 w-3.5" /> {t("detail.dashboard_breadcrumb")}
            </Link>
            <span className="mx-1 text-muted-foreground/55">/</span>
            <span>{symbol}</span>
          </div>
          
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
              {stock?.name ?? symbol}
            </h1>
            <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded text-muted-foreground mt-1">
              {symbol}
            </span>
          </div>
          
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            {stock?.industry || tCommon("industry_placeholder")} · {stock?.market || tCommon("market_fallback")}
          </p>
        </div>

        {/* Floating Fin-Card Quote Header */}
        <div className={`premium-glass-card rounded-2xl border px-6 py-4 text-right shadow-md max-w-[200px] transition-all duration-300 ${glowBorderClass}`}>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            {quote?.is_delayed ? t("detail.latest_close") : t("detail.live_price")}
          </div>
          <div className="mt-1.5 text-3xl font-extrabold font-display tracking-tight text-foreground">
            {formatNumber(quote?.price ?? latestBar?.close)}
          </div>
          <div className={`text-xs font-bold font-mono mt-1.5 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 ${
            isPriceUp ? "bg-stock-up/10 text-stock-up" : "bg-stock-down/10 text-stock-down"
          }`}>
            {isPriceUp ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {quote?.change_percent != null 
              ? formatPercent(quote.change_percent) 
              : formatPercent(((barChange ?? 0) / (previousBar?.close ?? 1)) * 100)}
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        <Card className="premium-glass-card bg-background/30 shadow-sm">
          <CardHeader className="pb-1.5 pt-4 px-4 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">{t("detail.session_open")}</CardTitle>
            <Activity className="h-3.5 w-3.5 text-muted-foreground/60" />
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-xl font-bold font-display">{formatNumber(quote?.open ?? latestBar?.open)}</div>
          </CardContent>
        </Card>
        <Card className="premium-glass-card bg-background/30 shadow-sm">
          <CardHeader className="pb-1.5 pt-4 px-4 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">{t("detail.high_price")}</CardTitle>
            <TrendingUp className="h-3.5 w-3.5 text-stock-up/60" />
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-xl font-bold font-display text-stock-up">{formatNumber(quote?.high ?? latestBar?.high)}</div>
          </CardContent>
        </Card>
        <Card className="premium-glass-card bg-background/30 shadow-sm">
          <CardHeader className="pb-1.5 pt-4 px-4 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">{t("detail.low_price")}</CardTitle>
            <TrendingDown className="h-3.5 w-3.5 text-stock-down/60" />
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-xl font-bold font-display text-stock-down">{formatNumber(quote?.low ?? latestBar?.low)}</div>
          </CardContent>
        </Card>
        <Card className="premium-glass-card bg-background/30 shadow-sm">
          <CardHeader className="pb-1.5 pt-4 px-4 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">{t("detail.volume")}</CardTitle>
            <BarChart3 className="h-3.5 w-3.5 text-muted-foreground/60" />
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-xl font-bold font-display">{formatNumber(quote?.volume ?? latestBar?.volume)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Source Watchlist Context */}
      {fromWatchlist && (
        <Card className="premium-glass-card border bg-background/30 shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" /> {t("detail.active_context")}
            </CardTitle>
            <CardDescription className="text-xs">
              {t("detail.context_desc")}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3 text-xs">
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.active_pool")}</span>
              <span className="mt-2 text-sm font-bold text-foreground">{sourceWatchlist?.name || "Drilldown Pool"}</span>
            </div>
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.return_path")}</span>
              <Link href="/watchlists" className="mt-2 text-sm font-bold text-primary hover:underline">
                {t("detail.back_to_watchlists")}
              </Link>
            </div>
            {sourceWatchlist?.source_screen_type && (
              <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.source_screener")}</span>
                <Link href={`/screeners?screen=${sourceWatchlist.source_screen_type}`} className="mt-2 text-sm font-bold text-primary hover:underline">
                  {t("detail.inspect_screener")}
                </Link>
              </div>
            )}
            {!!sourceSummary.length && (
              <div className="rounded-xl border bg-background/25 p-4 md:col-span-3">
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.saved_criteria")}</span>
                <div className="mt-3 flex flex-wrap gap-2">
                  {sourceSummary.map((item) => (
                    <span key={item} className="rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-semibold text-muted-foreground border border-muted/50">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Technical Summary with Visual Gauges */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-4">
          <CardTitle className="font-display text-lg font-bold">
            {t("detail.technical_summary")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("detail.technical_desc")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
          <div className="rounded-xl border border-muted/40 bg-background/20 p-5 text-sm leading-7 text-foreground/90 backdrop-blur-md">
            <div className="font-semibold uppercase tracking-wider text-[10px] text-muted-foreground/80 mb-2 flex items-center gap-1">
              <Info className="h-3.5 w-3.5 text-primary" /> {t("detail.analyst_verdict")}
            </div>
            {analysis?.summary || t("detail.no_analysis")}
          </div>
          
          {/* Visual Technical Dials */}
          <div className="grid gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between transition-all hover:bg-background/40">
              <div>
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.ma5")}</span>
                <div className="mt-1 text-base font-bold font-display">{formatNumber(analysis?.ma5)}</div>
              </div>
              <div className="mt-2 text-[10px] font-semibold text-muted-foreground">
                {tCommon("deviation")}: <span className={(analysis?.price_vs_ma5_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}>
                  {formatPercent(analysis?.price_vs_ma5_pct)}
                </span>
              </div>
            </div>

            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between transition-all hover:bg-background/40">
              <div>
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.ma20")}</span>
                <div className="mt-1 text-base font-bold font-display">{formatNumber(analysis?.ma20)}</div>
              </div>
              <div className="mt-2 text-[10px] font-semibold text-muted-foreground">
                {tCommon("deviation")}: <span className={(analysis?.price_vs_ma20_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}>
                  {formatPercent(analysis?.price_vs_ma20_pct)}
                </span>
              </div>
            </div>

            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between transition-all hover:bg-background/40">
              <div>
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.return_5d")}</span>
                <div className={`mt-1 text-base font-bold font-display ${(analysis?.return_5d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                  {formatPercent(analysis?.return_5d_pct)}
                </div>
              </div>
              <div className="mt-2 text-[10px] font-semibold text-muted-foreground">{t("detail.short_term_strength")}</div>
            </div>

            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between transition-all hover:bg-background/40">
              <div>
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.return_20d")}</span>
                <div className={`mt-1 text-base font-bold font-display ${(analysis?.return_20d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                  {formatPercent(analysis?.return_20d_pct)}
                </div>
              </div>
              <div className="mt-2 text-[10px] font-semibold text-muted-foreground">{t("detail.mid_term_strength")}</div>
            </div>

            {/* RSI14 visual range track */}
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between sm:col-span-2">
              <div className="flex justify-between items-center">
                <span className="uppercase tracking-wider text-[10px] text-muted-foreground font-semibold">{t("detail.rsi14")}</span>
                <span className="font-bold text-sm text-primary font-mono">{formatNumber(analysis?.rsi14)}</span>
              </div>
              <div className="relative h-1.5 w-full bg-muted rounded-full overflow-hidden mt-3">
                {/* Visual marker of RSI position */}
                <div 
                  className="absolute h-full bg-primary rounded-full transition-all duration-500" 
                  style={{ width: `${Math.min(Math.max(analysis?.rsi14 ?? 50, 0), 100)}%` }} 
                />
              </div>
              <div className="flex justify-between text-[9px] text-muted-foreground mt-1.5 uppercase font-mono">
                <span>{t("detail.oversold")}</span>
                <span>{t("detail.neutral")}</span>
                <span>{t("detail.overbought")}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Signal Explanations */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-4 border-b border-muted/30">
          <CardTitle className="font-display text-base font-bold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" /> {t("detail.signals_title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("detail.signals_desc")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 pt-6 text-xs">
          {analysis?.signals?.length ? (
            analysis.signals.map((signal) => (
              <div key={signal.name} className="rounded-xl border border-muted/40 bg-background/20 p-4 transition-all hover:bg-background/40">
                <div className="uppercase tracking-[0.16em] text-[10px] font-bold text-muted-foreground/80">{signal.name}</div>
                <div className="mt-2 text-foreground font-medium leading-relaxed">{signal.detail}</div>
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 md:col-span-2 xl:col-span-3">
              {t("detail.no_signals")}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dynamic Candlestick Chart & Profile Row */}
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        {/* Interactive TradingView Candlestick Chart */}
        <Card className="premium-glass-card bg-background/30 shadow-md">
          <CardHeader className="pb-4">
            <CardTitle className="font-display text-lg font-bold">
              {t("detail.kline_title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {t("detail.kline_desc")}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {isKlineLoading ? (
              <div className="h-[360px] rounded-xl border shimmer-loading opacity-60" />
            ) : kline?.length ? (
              <KLineChart data={kline} height={360} />
            ) : (
              <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20">
                {t("detail.no_kline_data")}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Static Profile Metadata */}
        <Card className="premium-glass-card bg-background/30 shadow-md">
          <CardHeader className="pb-4">
            <CardTitle className="font-display text-lg font-bold">
              {t("detail.profile_title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {t("detail.profile_desc")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-[0.16em] text-[10px] text-muted-foreground font-semibold">{t("detail.symbol_code")}</span>
              <span className="mt-2 text-base font-bold font-mono text-foreground">{stock?.code ?? symbol}</span>
            </div>
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-[0.16em] text-[10px] text-muted-foreground font-semibold">{t("detail.assigned_industry")}</span>
              <span className="mt-2 text-base font-bold text-foreground">{stock?.industry || tCommon("industry_fallback")}</span>
            </div>
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-[0.16em] text-[10px] text-muted-foreground font-semibold">{t("detail.domestic_market")}</span>
              <span className="mt-2 text-base font-bold text-foreground">{stock?.market || tCommon("market_fallback")}</span>
            </div>
            <div className="rounded-xl border bg-background/25 p-4 flex flex-col justify-between">
              <span className="uppercase tracking-[0.16em] text-[10px] text-muted-foreground font-semibold">{t("detail.ipo_date")}</span>
              <span className="mt-2 text-base font-bold font-mono text-foreground">{stock?.list_date || "N/A"}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
