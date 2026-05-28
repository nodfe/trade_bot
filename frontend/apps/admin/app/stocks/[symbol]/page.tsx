import { StockDetailClient } from "./stock-detail-client"

type StockDetailPageProps = {
  params: Promise<{ symbol: string }>
  searchParams: Promise<{
    from?: string
    watchlist?: string
  }>
}

export default async function StockDetailPage({
  params,
  searchParams,
}: StockDetailPageProps) {
  const { symbol } = await params
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
