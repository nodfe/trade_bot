import { setRequestLocale } from "next-intl/server"
import { StockDetailClient } from "./stock-detail-client"

type StockDetailPageProps = {
  params: Promise<{ symbol: string; locale: string }>
  searchParams: Promise<{
    from?: string
    watchlist?: string
  }>
}

export default async function StockDetailPage({
  params,
  searchParams,
}: StockDetailPageProps) {
  const { symbol, locale } = await params
  setRequestLocale(locale)

  const query = await searchParams

  return (
    <StockDetailClient
      symbol={symbol}
      sourceContext={{
        from: query.from,
        watchlistId: query.watchlist,
      }}
    />
  )
}
