import { setRequestLocale } from "next-intl/server"
import { SystemStatusClient } from "./system-status-client"

type SystemPageProps = {
  params: Promise<{ locale: string }>
}

export default async function SystemPage({ params }: SystemPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  return <SystemStatusClient />
}
