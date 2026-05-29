"use client"

import Link from "next/link"
import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatWatchlistTimestamp, summarizeWatchlistParams } from "@/lib/watchlist-utils"
import { refreshAutoWatchlists, refreshWatchlist, stockKeys, useWatchlists } from "@quant/hooks"
import { Play, RotateCw, Activity, Calendar, Award, Database, Flame } from "lucide-react"

export default function WatchlistsPage() {
  const t = useTranslations("watchlists")
  const queryClient = useQueryClient()
  const [status, setStatus] = useState("")
  const [isRefreshing, setIsRefreshing] = useState<Record<string, boolean>>({})
  const [isRefreshingAll, setIsRefreshingAll] = useState(false)
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
      t("summary.total_stocks", { count: nextItems.length }),
      t("summary.new_in", { count: added.length }),
      t("summary.removed", { count: removed.length }),
      t("summary.kept", { count: keptCount }),
    ]
    const joiner = t("summary.new_in_highlight").includes("【") ? "、" : ", "
    const highlights = added.slice(0, 2).map((item) => item.stock_name).join(joiner)

    return highlights ? `${changeParts.join(" · ")}${t("summary.new_in_highlight", { names: highlights })}` : changeParts.join(" · ")
  }

  const toggleExpanded = (watchlistId: string) => {
    setExpandedWatchlists((current) => ({
      ...current,
      [watchlistId]: !current[watchlistId],
    }))
  }

  const handleRefreshOne = async (watchlistId: string) => {
    try {
      setIsRefreshing(prev => ({ ...prev, [watchlistId]: true }))
      const currentWatchlist = watchlists?.find((watchlist) => watchlist.id === watchlistId)
      const refreshed = await refreshWatchlist(watchlistId)
      
      await queryClient.setQueryData(stockKeys.watchlists(), (current: typeof watchlists) => {
        if (!current) return [refreshed]
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
      setStatus(t("summary.refresh_success", { name: refreshed.name, summary: refreshSummary }))
      setTimeout(() => setStatus(""), 5000)
    } catch {
      setStatus(t("summary.refresh_failed"))
    } finally {
      setIsRefreshing(prev => ({ ...prev, [watchlistId]: false }))
    }
  }

  const handleRefreshAuto = async () => {
    try {
      setIsRefreshingAll(true)
      setStatus(t("summary.refreshing_batch"))
      const refreshed = await refreshAutoWatchlists()
      
      const refreshSummaryMap = new Map(
        refreshed.map((watchlist) => {
          const previousItems = watchlists?.find((item) => item.id === watchlist.id)?.items ?? []
          return [watchlist.id, summarizeRefreshChange(previousItems, watchlist.items)]
        }),
      )
      
      await queryClient.setQueryData(stockKeys.watchlists(), (current: typeof watchlists) => {
        if (!current?.length) return refreshed
        const refreshedMap = new Map(refreshed.map((watchlist) => [watchlist.id, watchlist]))
        return current.map((watchlist) => refreshedMap.get(watchlist.id) ?? watchlist)
      })
      
      setRefreshSummaries((current) => ({
        ...current,
        ...Object.fromEntries(refreshSummaryMap),
      }))
      setStatus(t("summary.batch_success", { count: refreshed.length }))
      setTimeout(() => setStatus(""), 6000)
    } catch {
      setStatus(t("summary.batch_failed"))
    } finally {
      setIsRefreshingAll(false)
    }
  }

  const totalWatchlists = watchlists?.length ?? 0
  const dailyCronCount = watchlists?.filter(w => w.auto_refresh === "daily").length ?? 0

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("subtitle")}
        </p>
      </div>

      {/* Analytics Strip & Batch Actions */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center justify-between">
            <span>{t("orchestrator.title")}</span>
            {!isLoading && (
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded uppercase tracking-wider">
                {t("orchestrator.cron_active")}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Stats Bar */}
          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            <div className="rounded-xl border bg-background/10 p-3.5 flex items-center gap-3">
              <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center text-primary shrink-0">
                <Database className="h-4 w-4" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{t("orchestrator.total_pools")}</div>
                <div className="mt-1 text-base font-bold font-display">{totalWatchlists}</div>
              </div>
            </div>
            <div className="rounded-xl border bg-background/10 p-3.5 flex items-center gap-3">
              <div className="h-8 w-8 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0">
                <Calendar className="h-4 w-4" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{t("orchestrator.daily_cron_sync")}</div>
                <div className="mt-1 text-base font-bold font-display">{dailyCronCount}</div>
              </div>
            </div>
            <div className="rounded-xl border bg-background/10 p-3.5 flex items-center gap-3">
              <div className="h-8 w-8 rounded bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
                <Award className="h-4 w-4" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{t("orchestrator.overall_stocks")}</div>
                <div className="mt-1 text-base font-bold font-display">
                  {watchlists?.reduce((sum, w) => sum + w.items.length, 0) ?? 0}
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              type="button"
              onClick={handleRefreshAuto}
              disabled={isRefreshingAll || isLoading || totalWatchlists === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 py-2 text-xs transition-colors h-[34px] disabled:opacity-50 disabled:pointer-events-none"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshingAll ? "animate-spin" : ""}`} />
              {t("orchestrator.sync_button")}
            </button>
            {status && (
              <span className="text-xs font-semibold text-primary flex items-center gap-1.5 bg-primary/10 border border-primary/20 px-3 py-1.5 rounded-lg">
                <Activity className="h-3 w-3 animate-pulse" /> {status}
              </span>
            )}
          </div>

          {isError && (
            <div className="rounded-xl border border-dashed border-destructive/30 p-4 text-xs text-muted-foreground bg-destructive/5">
              {t("summary.load_failed")}
              <Link href="/screeners" className="mx-1 text-primary font-semibold hover:underline">
                {t("summary.screeners_link")}
              </Link>
              {t("summary.first_watchlist_guide")}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Watchlist Cards Grid */}
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, idx) => (
            <div key={idx} className="h-[380px] rounded-2xl border shimmer-loading opacity-60" />
          ))
        ) : watchlists?.length ? (
          watchlists.map((watchlist) => (
            <Card key={watchlist.id} className="premium-glass-card border bg-background/30 shadow-md relative overflow-hidden flex flex-col justify-between">
              <div>
                <CardHeader className="pb-4 border-b border-muted/20">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <CardTitle className="text-base font-bold font-display">{watchlist.name}</CardTitle>
                      <CardDescription className="text-[10px] uppercase tracking-wider font-semibold font-mono mt-1 text-muted-foreground/80 flex items-center gap-1.5">
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
                        {watchlist.source_screen_type || "manual"} · {watchlist.auto_refresh}
                      </CardDescription>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRefreshOne(watchlist.id)}
                      disabled={isRefreshing[watchlist.id]}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border bg-background/50 hover:bg-background transition-colors"
                      title={t("card.sync_tooltip")}
                    >
                      <RotateCw className={`h-3.5 w-3.5 text-muted-foreground hover:text-primary ${isRefreshing[watchlist.id] ? "animate-spin text-primary" : ""}`} />
                    </button>
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-4 text-xs pt-4">
                  <div className="text-muted-foreground leading-5 min-h-[35px] italic">
                    {watchlist.notes || t("card.no_description")}
                  </div>

                  {/* Sync Timestamps Grid */}
                  <div className="grid gap-2 grid-cols-2 border-y border-muted/20 py-3 text-[10px] text-muted-foreground font-mono">
                    <div>
                      <div className="font-semibold uppercase tracking-wider">{t("card.created")}</div>
                      <div className="mt-1 text-foreground font-medium">
                        {formatWatchlistTimestamp(watchlist.created_at)}
                      </div>
                    </div>
                    <div>
                      <div className="font-semibold uppercase tracking-wider">{t("card.last_refreshed")}</div>
                      <div className="mt-1 text-foreground font-medium">
                        {formatWatchlistTimestamp(watchlist.last_refreshed_at)}
                      </div>
                    </div>
                  </div>

                  {/* Parameter Badges */}
                  {!!summarizeWatchlistParams(watchlist.screen_params_json, t).length && (
                    <div className="space-y-2">
                      <div className="uppercase tracking-[0.16em] text-[9px] font-bold text-muted-foreground/80">{t("card.thresholds")}</div>
                      <div className="flex flex-wrap gap-1.5">
                        {summarizeWatchlistParams(watchlist.screen_params_json, t).map((item) => (
                          <span key={item} className="rounded bg-muted/60 px-2 py-0.5 text-[9px] font-medium text-muted-foreground/90 border border-muted/30">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Refresh changes highlights */}
                  {refreshSummaries[watchlist.id] && (
                    <div className="rounded-xl bg-primary/5 p-3 text-[10px] text-primary border border-primary/10 leading-relaxed font-semibold">
                      <div className="uppercase tracking-wider text-[9px] mb-1 font-bold">{t("card.latest_changes")}</div>
                      <div>{refreshSummaries[watchlist.id]}</div>
                    </div>
                  )}

                  {/* Expandable Candidates list */}
                  <div className="space-y-2 pt-2">
                    <div className="uppercase tracking-[0.16em] text-[9px] font-bold text-muted-foreground/80 flex items-center gap-1">
                      {t("card.candidates_count", { count: watchlist.items.length })}
                    </div>
                    <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                      {(expandedWatchlists[watchlist.id] ? watchlist.items : watchlist.items.slice(0, 3)).map((item) => (
                        <Link
                          key={item.id}
                          href={`/stocks/${item.stock_code}?from=watchlist&watchlist=${watchlist.id}`}
                          className="flex items-start justify-between gap-3 rounded-lg border border-muted/40 p-3 bg-background/20 transition-all hover:scale-[1.01] hover:border-primary/30 hover:bg-background/40"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-foreground text-sm leading-none">{item.stock_name}</span>
                              <span className="text-[10px] text-muted-foreground font-mono">{item.stock_code}</span>
                            </div>
                            {item.match_reason && (
                              <div className="text-[10px] text-muted-foreground line-clamp-1 leading-normal mt-1">{item.match_reason}</div>
                            )}
                          </div>
                          
                          {!!item.hot_tags.length && (
                            <div className="flex flex-wrap gap-1 justify-end shrink-0">
                              {item.hot_tags.slice(0, 1).map((tag) => (
                                <span key={tag} className="inline-flex items-center gap-0.5 rounded-full bg-primary/5 border border-primary/10 px-2.5 py-0.5 text-[8px] font-semibold text-primary">
                                  <Flame className="h-2 w-2 text-primary" /> {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </Link>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </div>

              <CardContent className="pt-0 pb-4">
                {watchlist.items.length > 3 && (
                  <button
                    type="button"
                    onClick={() => toggleExpanded(watchlist.id)}
                    className="w-full text-center text-xs font-semibold text-primary hover:text-primary/95 transition-colors pt-2 border-t border-muted/20"
                  >
                    {expandedWatchlists[watchlist.id]
                      ? t("card.collapse")
                      : t("card.view_more", { count: watchlist.items.length - 3 })}
                  </button>
                )}
              </CardContent>
            </Card>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 md:col-span-2 xl:col-span-3">
            {t("summary.no_watchlists")}
          </div>
        )}
      </div>
    </div>
  )
}
