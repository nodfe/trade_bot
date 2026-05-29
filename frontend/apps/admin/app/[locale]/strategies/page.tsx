import { setRequestLocale } from "next-intl/server"
import { StrategiesClient } from "./strategies-client"

type StrategiesPageProps = {
  params: Promise<{ locale: string }>
}

export default async function StrategiesPage({ params }: StrategiesPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  return <StrategiesClient />
}
