"use client"

import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FlaskConical } from "lucide-react"

export function BacktestsClient() {
  const t = useTranslations("backtests")

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Coming Soon Placeholder */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3 border-b border-muted/30">
          <CardTitle className="font-display text-lg font-bold flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {t("title")}
          </CardTitle>
          <CardDescription className="text-xs mt-1">
            {t("subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground bg-muted/20 flex flex-col items-center gap-2">
            <FlaskConical className="h-5 w-5 text-muted-foreground/60" />
            <span>{t("coming_soon")}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
