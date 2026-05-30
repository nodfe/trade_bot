"use client"

import Link from "next/link"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ArrowRight, FlaskConical, Sparkles, TrendingUp, Volume2 } from "lucide-react"

type StrategyKey = "strong_uptrend" | "volume_breakout" | "pullback_watch"

type StrategyMeta = {
  key: StrategyKey
  icon: typeof TrendingUp
  accent: string
  defaults: Record<string, string>
}

const STRATEGIES: StrategyMeta[] = [
  {
    key: "strong_uptrend",
    icon: TrendingUp,
    accent: "stock-up",
    defaults: {
      min_return_20d_pct: "5%",
      min_return_5d_pct: "0%",
      min_volume_ratio: "1.3x",
    },
  },
  {
    key: "volume_breakout",
    icon: Volume2,
    accent: "primary",
    defaults: {
      min_volume_ratio: "1.8x",
      min_return_5d_pct: "2%",
    },
  },
  {
    key: "pullback_watch",
    icon: Sparkles,
    accent: "stock-down",
    defaults: {
      min_return_20d_pct: "5%",
      max_return_5d_pct: "0%",
    },
  },
]

export function StrategiesClient() {
  const t = useTranslations("strategies")
  const tScreeners = useTranslations("screeners")

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Catalog Description */}
      <Card className="premium-glass-card border bg-background/30 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" />
            {t("catalog.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("catalog.description")}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Strategy Cards */}
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {STRATEGIES.map((strategy) => {
          const Icon = strategy.icon
          return (
            <Card
              key={strategy.key}
              className="premium-glass-card premium-glass-hover border bg-background/30 shadow-md flex flex-col"
            >
              <CardHeader className="pb-3 border-b border-muted/30">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex h-9 w-9 items-center justify-center rounded-xl bg-${strategy.accent}/10 text-${strategy.accent}`}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div>
                      <CardTitle className="text-base font-bold font-display">
                        {tScreeners(`options.${strategy.key}.label`)}
                      </CardTitle>
                      <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground mt-1">
                        {tScreeners(`options.${strategy.key}.badge`)}
                      </span>
                    </div>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="flex flex-col flex-1 gap-4 pt-4">
                <CardDescription className="text-xs leading-5">
                  {tScreeners(`options.${strategy.key}.description`)}
                </CardDescription>

                {/* Default parameters */}
                <div className="rounded-xl border bg-background/20 p-3 space-y-2">
                  <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                    {t("card.defaults_title")}
                  </div>
                  <div className="space-y-1.5 text-xs font-mono">
                    {Object.entries(strategy.defaults).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-3">
                        <span className="text-muted-foreground">{t(`params.${key}`)}</span>
                        <span className="font-semibold text-foreground">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Use cases */}
                <div className="space-y-1.5 text-xs">
                  <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                    {t("card.use_case_title")}
                  </div>
                  <p className="text-muted-foreground leading-5">
                    {t(`use_cases.${strategy.key}`)}
                  </p>
                </div>

                <div className="mt-auto pt-2">
                  <Link
                    href={`/screeners?screen=${strategy.key}`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/95 px-4 py-2 text-xs font-semibold transition-colors"
                  >
                    {t("card.run_in_screener")}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Custom strategies — coming soon */}
      <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground/70" />
            {t("custom.title")}
          </CardTitle>
          <CardDescription className="text-xs">{t("custom.description")}</CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
