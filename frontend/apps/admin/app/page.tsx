"use client"

import Link from "next/link"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Activity, BarChart3, Newspaper, TrendingDown, TrendingUp } from "lucide-react"

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
  const { data, isLoading, isError } = useMarketOverview()
  const latestDragonTigerDate = data?.latest_dragon_tiger_date ?? ""
  const latestLimitUpDate = data?.latest_limit_up_date ?? ""
  const latestNewsDate = data?.latest_news_date ?? ""

  const { data: dragonTigerItems } = useDragonTigerList(latestDragonTigerDate, {
    enabled: !!latestDragonTigerDate,
  })
  const { data: limitUpItems } = useLimitUpBoard(latestLimitUpDate, {
    enabled: !!latestLimitUpDate,
  })
  const { data: newsItems } = useMarketNews(latestNewsDate, 6, {
    enabled: !!latestNewsDate,
  })

  const kpiCards = [
    {
      title: "Tracked Stocks",
      value: data?.stock_count?.toLocaleString() ?? "-",
      description: "A-share securities in local store",
      icon: BarChart3,
    },
    {
      title: "龙虎榜 Records",
      value: data?.latest_dragon_tiger_count?.toLocaleString() ?? "-",
      description: "Latest available dragon tiger dataset",
      icon: TrendingUp,
      className: "text-stock-up",
    },
    {
      title: "涨停板 Records",
      value: data?.latest_limit_up_count?.toLocaleString() ?? "-",
      description: "Latest available limit-up dataset",
      icon: TrendingDown,
      className: "text-stock-down",
    },
    {
      title: "News Items",
      value: data?.latest_news_count?.toLocaleString() ?? "-",
      description: "Latest ingested market news batch",
      icon: Activity,
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Chinese A-share quantitative analysis overview
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading market overview from backend"
              : isError
                ? "Unable to load backend overview"
                : `Latest trade date: ${data?.latest_trade_date ?? "N/A"}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground/80">Data Spine</div>
            <div className="mt-2 font-medium text-foreground">Backend and admin now share one market contract.</div>
          </div>
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground/80">Latest Batch</div>
            <div className="mt-2 font-medium text-foreground">{data?.latest_trade_date ?? "N/A"}</div>
          </div>
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground/80">Delivery Phase</div>
            <div className="mt-2 font-medium text-foreground">Market Data MVP in progress</div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {kpiCards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {card.title}
              </CardTitle>
              <card.icon className={`h-4 w-4 ${card.className ?? "text-muted-foreground"}`} />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${card.className ?? ""}`}>
                {card.value}
              </div>
              <CardDescription>{card.description}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-stock-up" />
              龙虎榜 Snapshot
            </CardTitle>
            <CardDescription>
              {latestDragonTigerDate ? `Latest trade date: ${latestDragonTigerDate}` : "No dragon tiger data yet"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {dragonTigerItems?.slice(0, 5).map((item, index) => (
              <Link
                key={item.id}
                href={`/stocks/${item.code}`}
                className="flex items-start justify-between gap-4 rounded-lg border p-3 transition-colors hover:border-primary/40 hover:bg-muted/30"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">#{index + 1}</span>
                    <span className="font-medium text-foreground">{item.name}</span>
                    <span className="text-xs text-muted-foreground">{item.code}</span>
                  </div>
                  <div className="text-sm text-muted-foreground line-clamp-2">{item.reason || "暂无上榜原因"}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-stock-up">{formatCompactNumber(item.net_buy)}</div>
                  <div className="text-xs text-muted-foreground">净买入</div>
                </div>
              </Link>
            ))}
            {!dragonTigerItems?.length && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                暂无龙虎榜数据，先执行一次同步后这里会展示最新热点席位。
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-stock-down" />
              涨停板 Pulse
            </CardTitle>
            <CardDescription>
              {latestLimitUpDate ? `Latest trade date: ${latestLimitUpDate}` : "No limit-up data yet"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {limitUpItems?.slice(0, 6).map((item) => (
              <Link
                key={item.id}
                href={`/stocks/${item.code}`}
                className="block rounded-lg border p-3 transition-colors hover:border-primary/40 hover:bg-muted/30"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-foreground">{item.name}</div>
                    <div className="text-xs text-muted-foreground">{item.code}</div>
                  </div>
                  <div className="text-right text-stock-up font-semibold">{formatPercent(item.change_pct)}</div>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{item.reason || "暂无涨停原因"}</span>
                  <span>开板 {item.open_times ?? 0} 次</span>
                </div>
              </Link>
            ))}
            {!limitUpItems?.length && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                暂无涨停板数据，完成同步后这里会显示当天强势题材与封板情况。
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Newspaper className="h-4 w-4" />
            财经新闻 Flow
          </CardTitle>
          <CardDescription>
            {latestNewsDate ? `Latest trade date: ${latestNewsDate}` : "No news data yet"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {newsItems?.map((item) => (
            <a
              key={item.id}
              href={item.url || "#"}
              target={item.url ? "_blank" : undefined}
              rel={item.url ? "noreferrer" : undefined}
              className="group rounded-xl border p-4 transition-colors hover:border-primary/40 hover:bg-muted/40"
            >
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>{item.source || "财经"}</span>
                <span>{item.published_at ? item.published_at.slice(11, 16) : item.trade_date}</span>
              </div>
              <div className="mt-3 line-clamp-3 font-medium text-foreground group-hover:text-primary">
                {item.title}
              </div>
            </a>
          ))}
          {!newsItems?.length && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              暂无财经新闻数据，完成同步后这里会显示最新的市场资讯流。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
