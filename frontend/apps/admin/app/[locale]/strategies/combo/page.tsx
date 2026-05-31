import { setRequestLocale } from "next-intl/server"
import { ComboClient } from "./combo-client"

type ComboPageProps = {
  params: Promise<{ locale: string }>
}

export default async function ComboPage({ params }: ComboPageProps) {
  const { locale } = await params
  setRequestLocale(locale)
  return <ComboClient />
}
