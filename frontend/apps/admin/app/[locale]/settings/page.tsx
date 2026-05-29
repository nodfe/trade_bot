import { setRequestLocale } from "next-intl/server"
import { SettingsClient } from "./settings-client"

type SettingsPageProps = {
  params: Promise<{ locale: string }>
}

export default async function SettingsPage({ params }: SettingsPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  return <SettingsClient />
}
