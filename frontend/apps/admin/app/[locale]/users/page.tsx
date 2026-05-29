import { setRequestLocale } from "next-intl/server"
import { UsersClient } from "./users-client"

type UsersPageProps = {
  params: Promise<{ locale: string }>
}

export default async function UsersPage({ params }: UsersPageProps) {
  const { locale } = await params
  setRequestLocale(locale)

  return <UsersClient />
}
