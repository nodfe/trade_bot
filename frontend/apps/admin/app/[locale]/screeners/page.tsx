import { setRequestLocale } from "next-intl/server"
import { ScreenersClient } from "./screeners-client"

type ScreenersPageProps = {
  params: Promise<{ locale: string }>
  searchParams: Promise<{
    screen?: string
  }>
}

export default async function ScreenersPage({ params, searchParams }: ScreenersPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  const query = await searchParams

  return <ScreenersClient initialScreenType={query.screen} />
}
