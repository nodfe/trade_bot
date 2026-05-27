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
import { refreshAutoWatchlists, refreshWatchlist, useWatchlists } from "@quant/hooks"

export default function WatchlistsPage() {
  const [status, setStatus] = useState("")
  const { data: watchlists, isLoading, isError } = useWatchlists({
    retry: false,
  })

  const handleRefreshOne = async (watchlistId: string) => {
    try {
      await refreshWatchlist(watchlistId)
      setStatus("候选池已刷新，重新进入页面可查看最新结果")
    } catch {
      setStatus("刷新失败，请检查后端或数据库状态")
    }
  }

  const handleRefreshAuto = async () => {
    try {
      const refreshed = await refreshAutoWatchlists()
      setStatus(`已触发 ${refreshed.length} 个自动候选池刷新`)
    } catch {
      setStatus("批量刷新失败，请检查后端或数据库状态")
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
        <p className="text-muted-foreground">Saved candidate pools from screeners and future workflows.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Saved Pools</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading watchlists"
              : isError
                ? "Unable to load watchlists"
                : `${watchlists?.length ?? 0} saved candidate pools`}
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-0">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleRefreshAuto}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Refresh Auto Watchlists
            </button>
            {status && <span className="text-sm text-muted-foreground">{status}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Saved Pools</CardTitle>
          <CardDescription>Review and refresh candidate pools.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {watchlists?.map((watchlist) => (
            <Card key={watchlist.id} className="border-dashed shadow-none">
              <CardHeader>
                <CardTitle className="text-base">{watchlist.name}</CardTitle>
                <CardDescription>
                  {(watchlist.source_screen_type || "manual") + " · " + watchlist.auto_refresh}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="text-muted-foreground">{watchlist.notes || "No notes"}</div>
                <div className="rounded-lg bg-muted/40 p-3">
                  <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Items</div>
                  <div className="mt-2 font-medium text-foreground">{watchlist.items.length}</div>
                </div>
                <button
                  type="button"
                  onClick={() => handleRefreshOne(watchlist.id)}
                  className="rounded-md border px-3 py-2 text-sm hover:border-primary/40"
                >
                  Refresh Now
                </button>
                {watchlist.items.slice(0, 3).map((item) => (
                  <Link key={item.id} href={`/stocks/${item.stock_code}`} className="block rounded-md border p-3 hover:border-primary/40">
                    <div className="font-medium text-foreground">{item.stock_name}</div>
                    <div className="text-xs text-muted-foreground">{item.stock_code}</div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          ))}
          {!watchlists?.length && !isLoading && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              还没有保存的候选池。先去 Screeners 页面保存一组筛选结果。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
