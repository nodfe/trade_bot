import { ScreenersClient } from "./screeners-client"

type ScreenersPageProps = {
  searchParams: Promise<{
    screen?: string
  }>
}

export default async function ScreenersPage({ searchParams }: ScreenersPageProps) {
  const query = await searchParams

  return <ScreenersClient initialScreenType={query.screen} />
}
