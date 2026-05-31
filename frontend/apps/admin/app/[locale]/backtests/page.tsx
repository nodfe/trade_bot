import { Suspense } from "react"
import { setRequestLocale } from "next-intl/server"
import { BacktestsClient } from "./backtests-client"

type BacktestsPageProps = {
  params: Promise<{ locale: string }>
}

export default async function BacktestsPage({ params }: BacktestsPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  return (
    <Suspense fallback={null}>
      <BacktestsClient />
    </Suspense>
  )
}
