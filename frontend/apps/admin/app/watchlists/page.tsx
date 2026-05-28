"use client"

import Link from "next/link"
import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatWatchlistTimestamp, summarizeWatchlistParams } from "@/lib/watchlist-utils"
import { refreshAutoWatchlists, refreshWatchlist, stockKeys, useWatchlists } from "@quant/hooks"

export default function WatchlistsPage() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState("")
  const [expandedWatchlists, setExpandedWatchlists] = useState<Record<string, boolean>>({})
  const [refreshSummaries, setRefreshSummaries] = useState<Record<string, string>>({})
  const { data: watchlists, isLoading, isError } = useWatchlists({
    retry: false,
  })

  const summarizeRefreshChange = (
    previousItems: Array<{ stock_code: string; stock_name: string }>,
    nextItems: Array<{ stock_code: string; stock_name: string }>,
  ) => {
    const previousCodes = new Set(previousItems.map((item) => item.stock_code))
    const nextCodes = new Set(nextItems.map((item) => item.stock_code))
    const added = nextItems.filter((item) => !previousCodes.has(item.stock_code))
    const removed = previousItems.filter((item) => !nextCodes.has(item.stock_code))
    const keptCount = nextItems.length - added.length

    const changeParts = [
      `当前 ${nextItems.length} 只`,
      `新增 ${added.length} 只`,
      `移除 ${removed.length} 只`,
      `延续 ${keptCount} 只`,
    ]
    const highlights = added.slice(0, 2).map((item) => item.stock_name).join("、")

    return highlights ? `${changeParts.join(" · ")} · 新进 ${highlights}` : changeParts.join(" · ")
  }

  const toggleExpanded = (watchlistId: string) => {
    setExpandedWatchlists((current) => ({
      ...current,
      [watchlistId]: !current[watchlistId],
    }))
  }

  const handleRefreshOne = async (watchlistId: string) => {
    try {
      const currentWatchlist = watchlists?.find((watchlist) => watchlist.id === watchlistId)
      const refreshed = await refreshWatchlist(watchlistId)
      await queryClient.setQueryData(stockKeys.watchlists(), (current: typeof watchlists) => {
        if (!current) {
          return [refreshed]
        }

        return current.map((watchlist) =>
          watchlist.id === refreshed.id ? refreshed : watchlist,
        )
      })
      const refreshSummary = summarizeRefreshChange(
        currentWatchlist?.items ?? [],
        refreshed.items,
      )
      setRefreshSummaries((current) => ({
        ...current,
        [watchlistId]: refreshSummary,
      }))
      setStatus(`候选池已刷新，${refreshSummary}`)
    } catch {
      setStatus("刷新失败，请检查后端或数据库状态")
    }
  }

  const handleRefreshAuto = async () => {
    try {
      const refreshed = await refreshAutoWatchlists()
      const refreshSummaryMap = new Map(
        refreshed.map((watchlist) => {
          const previousItems = watchlists?.find((item) => item.id === watchlist.id)?.items ?? []
          return [watchlist.id, summarizeRefreshChange(previousItems, watchlist.items)]
        }),
      )
      await queryClient.setQueryData(stockKeys.watchlists(), (current: typeof watchlists) => {
        if (!current?.length) {
          return refreshed
        }

        const refreshedMap = new Map(refreshed.map((watchlist) => [watchlist.id, watchlist]))
        return current.map((watchlist) => refreshedMap.get(watchlist.id) ?? watchlist)
      })
      setRefreshSummaries((current) => ({
        ...current,
        ...Object.fromEntries(refreshSummaryMap),
      }))
      setStatus(`已触发 ${refreshed.length} 个自动候选池刷新，并更新了最新变化摘要`)
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
          {isError && (
            <div className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              候选池暂时无法加载。先确认后端服务、数据库迁移和已保存的筛选结果都可用；如果这是第一次使用，先去
              <Link href="/screeners" className="mx-1 text-primary hover:underline">
                Screeners
              </Link>
              保存一组候选池。
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Saved Pools</CardTitle>
          <CardDescription>Review, refresh, and drill into candidate names with context.</CardDescription>
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
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg bg-muted/40 p-3">
                    <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Items</div>
                    <div className="mt-2 font-medium text-foreground">{watchlist.items.length}</div>
                  </div>
                  <div className="rounded-lg bg-muted/40 p-3">
                    <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Mode</div>
                    <div className="mt-2 font-medium text-foreground">{watchlist.auto_refresh}</div>
                  </div>
                  <div className="rounded-lg bg-muted/40 p-3">
                    <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Source</div>
                    <div className="mt-2 font-medium text-foreground">
                      {watchlist.source_screen_type || "manual"}
                    </div>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border bg-background/80 p-3 text-xs text-muted-foreground">
                    <div className="uppercase tracking-[0.16em]">Created</div>
                    <div className="mt-2 font-medium text-foreground">
                      {formatWatchlistTimestamp(watchlist.created_at)}
                    </div>
                  </div>
                  <div className="rounded-lg border bg-background/80 p-3 text-xs text-muted-foreground">
                    <div className="uppercase tracking-[0.16em]">Last Refresh</div>
                    <div className="mt-2 font-medium text-foreground">
                      {formatWatchlistTimestamp(watchlist.last_refreshed_at)}
                    </div>
                  </div>
                </div>
                {!!summarizeWatchlistParams(watchlist.screen_params_json).length && (
                  <div className="rounded-lg border bg-background/80 p-3 text-xs text-muted-foreground">
                    <div className="mb-2 uppercase tracking-[0.16em]">Refresh Summary</div>
                    <div className="flex flex-wrap gap-2">
                      {summarizeWatchlistParams(watchlist.screen_params_json).map((item) => (
                        <span key={item} className="rounded-full border px-2 py-1">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => handleRefreshOne(watchlist.id)}
                  className="rounded-md border px-3 py-2 text-sm hover:border-primary/40"
                >
                  Refresh Now
                </button>
                {refreshSummaries[watchlist.id] && (
                  <div className="rounded-lg border bg-background/80 p-3 text-xs text-muted-foreground">
                    <div className="mb-2 uppercase tracking-[0.16em]">Latest Refresh</div>
                    <div>{refreshSummaries[watchlist.id]}</div>
                  </div>
                )}
                {(expandedWatchlists[watchlist.id] ? watchlist.items : watchlist.items.slice(0, 4)).map((item) => (
                  <Link
                    key={item.id}
                    href={`/stocks/${item.stock_code}?from=watchlist&watchlist=${watchlist.id}`}
                    className="block rounded-md border p-3 hover:border-primary/40 hover:bg-muted/30"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-foreground">{item.stock_name}</div>
                        <div className="text-xs text-muted-foreground">{item.stock_code}</div>
                      </div>
                      {!!item.hot_tags.length && (
                        <div className="flex flex-wrap justify-end gap-1">
                          {item.hot_tags.slice(0, 2).map((tag) => (
                            <span key={tag} className="rounded-full border px-2 py-1 text-[10px] text-muted-foreground">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {item.match_reason && (
                      <div className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                        {item.match_reason}
                      </div>
                    )}
                  </Link>
                ))}
                {watchlist.items.length > 4 && (
                  <button
                    type="button"
                    onClick={() => toggleExpanded(watchlist.id)}
                    className="text-left text-sm font-medium text-primary hover:underline"
                  >
                    {expandedWatchlists[watchlist.id]
                      ? "收起候选标的"
                      : `查看更多 (${watchlist.items.length - 4} 只)`}
                  </button>
                )}
              </CardContent>
            </Card>
          ))}
          {!watchlists?.length && !isLoading && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              还没有保存的候选池。先去 Screeners 页面运行一个筛选器，给它起个名字，再保存成可以持续刷新的候选池。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
