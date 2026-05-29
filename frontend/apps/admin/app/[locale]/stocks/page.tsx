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
import { useStockList } from "@quant/hooks"

export default function StocksPage() {
  const t = useTranslations("stocks")
  const tCommon = useTranslations("common")
  const { data: stocks, isLoading, isError } = useStockList()

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
                : t("list.count", { count: stocks?.length ?? 0 })}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {stocks?.slice(0, 60).map((stock) => (
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
          {!stocks?.length && !isLoading && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              {t("list.no_stocks")}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
