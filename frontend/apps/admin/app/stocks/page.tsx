"use client"

import Link from "next/link"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useStockList } from "@quant/hooks"

export default function StocksPage() {
  const { data: stocks, isLoading, isError } = useStockList()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stocks</h1>
        <p className="text-muted-foreground">Browse the locally tracked A-share universe.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stock Universe</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading tracked stocks"
              : isError
                ? "Unable to load stocks"
                : `${stocks?.length ?? 0} stocks available`}
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
                {stock.industry || "行业待补充"}
              </div>
            </Link>
          ))}
          {!stocks?.length && !isLoading && (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
              暂无股票数据，先执行股票列表同步后这里会展示可钻取的标的池。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
