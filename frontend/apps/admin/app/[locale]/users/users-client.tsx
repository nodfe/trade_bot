"use client"

import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Users, Clock } from "lucide-react"

export function UsersClient() {
  const t = useTranslations("users")

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Coming Soon Card */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="font-display text-lg font-bold flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" />
            {t("title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground bg-muted/20 flex flex-col items-center gap-3">
            <Clock className="h-8 w-8 text-muted-foreground/60" />
            <span>{t("coming_soon")}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
