"use client"

import { useLocale, useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useSystemInfo, type ServiceHealth, type SystemInfo } from "@quant/hooks"
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  Info,
  KeyRound,
  Loader2,
  MessageCircle,
  Network,
  Server,
  Settings as SettingsIcon,
  XCircle,
} from "lucide-react"

type ServiceKey = "database" | "redis" | "tushare" | "feishu_bot"

const SERVICE_ORDER: ServiceKey[] = ["database", "redis", "tushare", "feishu_bot"]

const SERVICE_ICONS: Record<ServiceKey, typeof Database> = {
  database: Database,
  redis: Server,
  tushare: Network,
  feishu_bot: MessageCircle,
}

function statusPillClass(health: ServiceHealth): string {
  if (!health.configured) {
    return "bg-muted/40 text-muted-foreground border-muted-foreground/30"
  }
  if (health.connected) {
    return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
  }
  return "bg-destructive/10 text-destructive border-destructive/30"
}

function StatusIcon({ health }: { health: ServiceHealth }) {
  if (!health.configured) return <AlertTriangle className="h-3.5 w-3.5" />
  if (health.connected) return <CheckCircle2 className="h-3.5 w-3.5" />
  return <XCircle className="h-3.5 w-3.5" />
}

function formatServerTime(iso: string, locale: string): string {
  try {
    const dt = new Date(iso)
    return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
      dateStyle: "medium",
      timeStyle: "medium",
      timeZone: "Asia/Shanghai",
    }).format(dt)
  } catch {
    return iso
  }
}

export function SettingsClient() {
  const t = useTranslations("settings")
  const locale = useLocale()
  const { data, isLoading, isError } = useSystemInfo()

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-display bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {isLoading ? (
        <Card className="premium-glass-card border bg-background/30 shadow-md">
          <CardContent className="pt-6 pb-6">
            <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{t("loading")}</span>
            </div>
          </CardContent>
        </Card>
      ) : isError || !data ? (
        <Card className="premium-glass-card border border-destructive/40 bg-destructive/5 shadow-md">
          <CardContent className="pt-6 pb-6">
            <div className="flex items-center justify-center gap-2 text-xs text-destructive">
              <XCircle className="h-4 w-4" />
              <span>{t("error")}</span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <RuntimeCard info={data} locale={locale} />
          <DependenciesCard info={data} />
          <EditHintCard />
        </>
      )}
    </div>
  )
}

function RuntimeCard({ info, locale }: { info: SystemInfo; locale: string }) {
  const t = useTranslations("settings")

  const items: { label: string; value: string }[] = [
    { label: t("runtime.app_env"), value: info.app_env },
    { label: t("runtime.app_version"), value: info.app_version },
    { label: t("runtime.python_version"), value: info.python_version },
    { label: t("runtime.server_time"), value: formatServerTime(info.server_time, locale) },
  ]

  return (
    <Card className="premium-glass-card border bg-background/30 shadow-md">
      <CardHeader className="pb-3 border-b border-muted/30">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" />
          {t("runtime.title")}
        </CardTitle>
        <CardDescription className="text-xs">
          {t("runtime.description")}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((item) => (
            <div
              key={item.label}
              className="rounded-xl border bg-background/20 p-3 space-y-1"
            >
              <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/80">
                {item.label}
              </div>
              <div className="text-sm font-mono font-semibold text-foreground break-all">
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function DependenciesCard({ info }: { info: SystemInfo }) {
  const t = useTranslations("settings")

  return (
    <Card className="premium-glass-card border bg-background/30 shadow-md">
      <CardHeader className="pb-3 border-b border-muted/30">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <SettingsIcon className="h-4 w-4 text-primary" />
          {t("dependencies.title")}
        </CardTitle>
        <CardDescription className="text-xs">
          {t("dependencies.description")}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="grid gap-3 md:grid-cols-2">
          {SERVICE_ORDER.map((key) => (
            <ServiceRow key={key} svcKey={key} health={info[key]} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function ServiceRow({
  svcKey,
  health,
}: {
  svcKey: ServiceKey
  health: ServiceHealth
}) {
  const t = useTranslations("settings")
  const Icon = SERVICE_ICONS[svcKey]

  const statusLabel = !health.configured
    ? t("service.not_configured")
    : health.connected
      ? t("service.connected")
      : t("service.disconnected")

  return (
    <div className="rounded-xl border bg-background/20 p-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <div className="text-sm font-semibold text-foreground">
              {t(`service.${svcKey}`)}
            </div>
            <div className="text-[10px] uppercase tracking-[0.16em] font-bold text-muted-foreground/70 font-mono">
              {health.name}
            </div>
          </div>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusPillClass(health)}`}
        >
          <StatusIcon health={health} />
          {statusLabel}
        </span>
      </div>

      {health.version ? (
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="text-muted-foreground">{t("service.version")}</span>
          <span className="font-mono font-semibold text-foreground/90 truncate max-w-[60%] text-right">
            {health.version}
          </span>
        </div>
      ) : null}

      {health.error ? (
        <div className="text-[11px] text-destructive/90 leading-4 font-mono break-all bg-destructive/5 border border-destructive/20 rounded-md px-2 py-1.5">
          <span className="font-semibold mr-1">{t("service.error")}:</span>
          {health.error}
        </div>
      ) : null}
    </div>
  )
}

function EditHintCard() {
  const t = useTranslations("settings")
  return (
    <Card className="premium-glass-card border border-dashed bg-background/20 shadow-none">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-muted-foreground/70" />
          {t("edit_hint.title")}
        </CardTitle>
        <CardDescription className="text-xs flex gap-1.5">
          <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-muted-foreground/60" />
          <span>{t("edit_hint.description")}</span>
        </CardDescription>
      </CardHeader>
    </Card>
  )
}
