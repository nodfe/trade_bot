"use client"

import Link from "next/link"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useStockAnalysis, useStockDetail, useStockKline, useStockQuote } from "@quant/hooks"

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

type StockDetailPageProps = {
  params: Promise<{ symbol: string }>
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { symbol } = await params

  return <StockDetailScreen symbol={symbol} />
}

function StockDetailScreen({ symbol }: { symbol: string }) {
  const { data: stock } = useStockDetail(symbol)
  const { data: quote } = useStockQuote(symbol, {
    retry: false,
  })
  const { data: analysis } = useStockAnalysis(symbol, {
    retry: false,
  })
  const { data: kline } = useStockKline({
    symbol,
    limit: 20,
  })

  const latestBar = kline?.[kline.length - 1]
  const previousBar = kline && kline.length > 1 ? kline[kline.length - 2] : null
  const barChange = latestBar && previousBar ? latestBar.close - previousBar.close : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-sm text-muted-foreground">
            <Link href="/stocks" className="hover:text-foreground">
              Stocks
            </Link>
            <span className="mx-2">/</span>
            <span>{symbol}</span>
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">{stock?.name ?? symbol}</h1>
          <p className="text-muted-foreground">
            {stock?.industry || "行业信息待补充"} · {stock?.market || "A-share"}
          </p>
        </div>
        <div className="rounded-2xl border px-4 py-3 text-right">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Quote</div>
          <div className="mt-2 text-2xl font-semibold">{formatNumber(quote?.price ?? latestBar?.close)}</div>
          <div className={`text-sm ${quote?.change != null && quote.change >= 0 ? "text-stock-up" : "text-stock-down"}`}>
            {quote?.change != null ? formatNumber(quote.change) : formatNumber(barChange)}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Latest Close</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{formatNumber(latestBar?.close ?? quote?.price)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Open</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{formatNumber(quote?.open ?? latestBar?.open)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">High / Low</CardTitle>
          </CardHeader>
          <CardContent className="text-lg font-semibold">
            {formatNumber(quote?.high ?? latestBar?.high)} / {formatNumber(quote?.low ?? latestBar?.low)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Volume</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{formatNumber(quote?.volume ?? latestBar?.volume)}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Technical Summary</CardTitle>
          <CardDescription>Shared analysis summary consumed by both admin and bot.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
          <div className="rounded-xl border bg-muted/30 p-4 text-sm leading-6 text-foreground">
            {analysis?.summary || "分析摘要暂不可用，请先确保该股票至少有 20 根日线数据。"}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">MA5</div>
              <div className="mt-2 text-xl font-semibold">{formatNumber(analysis?.ma5)}</div>
              <div className="text-sm text-muted-foreground">偏离 {formatPercent(analysis?.price_vs_ma5_pct)}</div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">MA20</div>
              <div className="mt-2 text-xl font-semibold">{formatNumber(analysis?.ma20)}</div>
              <div className="text-sm text-muted-foreground">偏离 {formatPercent(analysis?.price_vs_ma20_pct)}</div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">5D Return</div>
              <div className={`mt-2 text-xl font-semibold ${(analysis?.return_5d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                {formatPercent(analysis?.return_5d_pct)}
              </div>
              <div className="text-sm text-muted-foreground">短期强弱</div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">20D Return</div>
              <div className={`mt-2 text-xl font-semibold ${(analysis?.return_20d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                {formatPercent(analysis?.return_20d_pct)}
              </div>
              <div className="text-sm text-muted-foreground">中期表现</div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">RSI14</div>
              <div className="mt-2 text-xl font-semibold">{formatNumber(analysis?.rsi14)}</div>
              <div className="text-sm text-muted-foreground">动量温度</div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">MACD Histogram</div>
              <div className={`mt-2 text-xl font-semibold ${(analysis?.macd_histogram ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}`}>
                {formatNumber(analysis?.macd_histogram)}
              </div>
              <div className="text-sm text-muted-foreground">趋势动能</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Signal Explanations</CardTitle>
          <CardDescription>Why the current analysis is leaning strong, weak, or neutral.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {analysis?.signals.map((signal) => (
            <div key={signal.name} className="rounded-lg border p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{signal.name}</div>
              <div className="mt-2 text-sm font-medium leading-6 text-foreground">{signal.detail}</div>
            </div>
          ))}
          {!analysis?.signals?.length && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              暂无信号解释，先确保该股票已有足够的日线样本。
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent K-Line Snapshot</CardTitle>
            <CardDescription>Latest 20 stored daily bars for this stock</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {kline?.slice(-10).reverse().map((bar) => (
              <div key={bar.timestamp} className="grid grid-cols-[1fr_repeat(5,minmax(0,1fr))] gap-3 rounded-lg border p-3 text-sm">
                <div className="text-muted-foreground">{bar.timestamp.slice(0, 10)}</div>
                <div>{formatNumber(bar.open)}</div>
                <div>{formatNumber(bar.high)}</div>
                <div>{formatNumber(bar.low)}</div>
                <div>{formatNumber(bar.close)}</div>
                <div>{formatNumber(bar.volume)}</div>
              </div>
            ))}
            {!kline?.length && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                暂无 K 线数据，先同步日线后这里会展示最近行情切片。
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Static metadata from the local stock master</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Code</div>
              <div className="mt-1 font-medium text-foreground">{stock?.code ?? symbol}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Industry</div>
              <div className="mt-1 font-medium text-foreground">{stock?.industry || "待补充"}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Market</div>
              <div className="mt-1 font-medium text-foreground">{stock?.market || "-"}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">List Date</div>
              <div className="mt-1 font-medium text-foreground">{stock?.list_date || "-"}</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
