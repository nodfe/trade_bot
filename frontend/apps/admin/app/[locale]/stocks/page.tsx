"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useTranslations } from "next-intl"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useStockList } from "@quant/hooks"

const PAGE_SIZE = 60

export default function StocksPage() {
  const t = useTranslations("stocks")
  const tCommon = useTranslations("common")
  const { data: stocks, isLoading, isError } = useStockList()
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => {
    if (!stocks) return []
    const q = search.trim().toLowerCase()
    if (!q) return stocks
    return stocks.filter(
      (s) => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
    )
  }, [stocks, search])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageStart = (safePage - 1) * PAGE_SIZE
  const pageItems = filtered.slice(pageStart, pageStart + PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("list.title")}</h1>
        <p className="text-muted-foreground">{t("list.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("list.universe")}</CardTitle>
          <CardDescription>
            {isLoading
              ? t("list.loading")
              : isError
                ? t("list.error")
                : search.trim()
                  ? t("list.search_count", { count: filtered.length, total: stocks?.length ?? 0 })
                  : t("list.count", { count: stocks?.length ?? 0 })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            placeholder={t("list.search_placeholder")}
            className="w-full rounded-lg border bg-background/50 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary md:max-w-md"
          />

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {pageItems.map((stock) => (
              <Link
                key={stock.code}
                href={`/stocks/${stock.code}`}
                className="rounded-xl border p-4 transition-colors hover:border-primary/40 hover:bg-muted/40"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-foreground">{stock.name}</div>
                    <div className="text-xs text-muted-foreground">{stock.code}</div>
                  </div>
                  <div className="rounded-full border px-2 py-1 text-xs text-muted-foreground">
                    {stock.market}
                  </div>
                </div>
                <div className="mt-3 text-sm text-muted-foreground">
                  {stock.industry || tCommon("industry_placeholder")}
                </div>
              </Link>
            ))}
            {!filtered.length && !isLoading && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
                {search.trim() ? t("list.no_search_results") : t("list.no_stocks")}
              </div>
            )}
          </div>

          {filtered.length > PAGE_SIZE && (
            <div className="flex items-center justify-between gap-3 pt-2 text-sm">
              <div className="text-xs text-muted-foreground">
                {t("list.page_indicator", { page: safePage, totalPages })}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-muted/50 disabled:opacity-50 disabled:pointer-events-none"
                >
                  {t("list.prev_page")}
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-muted/50 disabled:opacity-50 disabled:pointer-events-none"
                >
                  {t("list.next_page")}
                </button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
