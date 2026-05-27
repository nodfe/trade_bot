"use client"

import Link from "next/link"
import { useState } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { createWatchlist, useStockScreen } from "@quant/hooks"

const screenOptions = [
  {
    value: "strong_uptrend",
    label: "Strong Uptrend",
    description: "多头趋势延续，适合追踪强势主线。",
  },
  {
    value: "volume_breakout",
    label: "Volume Breakout",
    description: "量能放大配合短线转强，适合观察突破。",
  },
  {
    value: "pullback_watch",
    label: "Pullback Watch",
    description: "中期趋势未坏，短线回撤后等待再启动。",
  },
]

function formatPercent(value: number | null | undefined) {
  if (value == null) {
    return "-"
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

export default function ScreenersPage() {
  const [screenType, setScreenType] = useState("strong_uptrend")
  const [saveStatus, setSaveStatus] = useState<string>("")
  const [params, setParams] = useState({
    limit: 12,
    min_return_20d_pct: 5,
    min_return_5d_pct: 0,
    min_volume_ratio: 1.3,
    max_return_5d_pct: 1,
  })
  const { data, isLoading, isError } = useStockScreen(screenType, params, {
    retry: false,
  })

  const updateParam = (key: keyof typeof params, value: string) => {
    setParams((current) => ({
      ...current,
      [key]: value === "" ? undefined : Number(value),
    }))
  }

  const handleSaveWatchlist = async () => {
    if (!data?.items?.length) {
      setSaveStatus("当前没有可保存的筛选结果")
      return
    }

    const payload = {
      name: `${screenType}-${new Date().toISOString().slice(0, 16)}`,
      source_screen_type: screenType,
      notes: "Saved from screener page",
      items: data.items.map((item) => ({
        stock_code: item.symbol,
        stock_name: item.name,
        match_reason: item.match_reason,
        hot_tags: item.hot_tags,
      })),
    }

    try {
      await createWatchlist(payload)
      setSaveStatus("已保存到 Watchlists")
    } catch {
      setSaveStatus("保存失败，请检查后端和数据库状态")
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Screeners</h1>
        <p className="text-muted-foreground">Find candidate names from shared quant rules.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {screenOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setScreenType(option.value)}
            className={`rounded-xl border p-4 text-left transition-colors ${screenType === option.value ? "border-primary bg-primary/5" : "hover:border-primary/40 hover:bg-muted/30"}`}
          >
            <div className="font-medium text-foreground">{option.label}</div>
            <div className="mt-2 text-sm text-muted-foreground">{option.description}</div>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Parameters</CardTitle>
          <CardDescription>Fine-tune the active screener without changing backend logic.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Limit</span>
            <input
              type="number"
              value={params.limit ?? ""}
              onChange={(event) => updateParam("limit", event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Min 20D %</span>
            <input
              type="number"
              value={params.min_return_20d_pct ?? ""}
              onChange={(event) => updateParam("min_return_20d_pct", event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Min 5D %</span>
            <input
              type="number"
              value={params.min_return_5d_pct ?? ""}
              onChange={(event) => updateParam("min_return_5d_pct", event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Min Volume Ratio</span>
            <input
              type="number"
              step="0.1"
              value={params.min_volume_ratio ?? ""}
              onChange={(event) => updateParam("min_volume_ratio", event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Max 5D %</span>
            <input
              type="number"
              value={params.max_return_5d_pct ?? ""}
              onChange={(event) => updateParam("max_return_5d_pct", event.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2"
            />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Matches</CardTitle>
          <CardDescription>
            {isLoading
              ? "Running screener"
              : isError
                ? "No screener results yet"
                : `${data?.total ?? 0} matches for ${screenType}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-0">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleSaveWatchlist}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Save To Watchlists
            </button>
            {saveStatus && <span className="text-sm text-muted-foreground">{saveStatus}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Candidate Cards</CardTitle>
          <CardDescription>Tap into a stock to continue with detail analysis.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data?.items.map((item) => (
            <Link
              key={`${screenType}-${item.symbol}`}
              href={`/stocks/${item.symbol}`}
              className="rounded-xl border p-4 transition-colors hover:border-primary/40 hover:bg-muted/30"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-foreground">{item.name}</div>
                  <div className="text-xs text-muted-foreground">{item.symbol}</div>
                </div>
                <div className="rounded-full border px-2 py-1 text-xs text-muted-foreground">{item.market}</div>
              </div>
              <div className="mt-3 text-sm text-muted-foreground line-clamp-2">{item.match_reason}</div>
              {!!item.hot_tags.length && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.hot_tags.map((tag) => (
                    <span key={tag} className="rounded-full border px-2 py-1 text-[11px] text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">5D</div>
                  <div className={(item.return_5d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}>
                    {formatPercent(item.return_5d_pct)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">20D</div>
                  <div className={(item.return_20d_pct ?? 0) >= 0 ? "text-stock-up" : "text-stock-down"}>
                    {formatPercent(item.return_20d_pct)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Vol</div>
                  <div className="text-foreground">{item.volume_ratio_5d?.toFixed(2) ?? "-"}x</div>
                </div>
              </div>
              {!!item.related_news_headlines.length && (
                <div className="mt-4 rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
                  <div className="mb-2 uppercase tracking-[0.16em]">Related News</div>
                  {item.related_news_headlines.map((headline) => (
                    <div key={headline} className="line-clamp-2">• {headline}</div>
                  ))}
                </div>
              )}
            </Link>
          ))}
          {!data?.items?.length && !isLoading && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              当前筛选器暂无结果，先确保股票池与日线数据已经同步。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
