"use client"

import {
  LayoutDashboard,
  BarChart3,
  Bookmark,
  ScanSearch,
  FlaskConical,
  TestTube2,
  Users,
  Settings,
  Activity,
} from "lucide-react"
import { useLocale, useTranslations } from "next-intl"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { ThemeToggle } from "@/components/theme-toggle"
import { Link, usePathname, useRouter } from "@/i18n/routing"

const navItems = [
  {
    href: "/",
    icon: LayoutDashboard,
  },
  {
    href: "/stocks",
    icon: BarChart3,
  },
  {
    href: "/strategies",
    icon: FlaskConical,
  },
  {
    href: "/screeners",
    icon: ScanSearch,
  },
  {
    href: "/watchlists",
    icon: Bookmark,
  },
  {
    href: "/backtests",
    icon: TestTube2,
  },
  {
    href: "/users",
    icon: Users,
  },
  {
    href: "/system",
    icon: Activity,
  },
  {
    href: "/settings",
    icon: Settings,
  },
]

const navKeys: Record<string, string> = {
  "/": "dashboard",
  "/stocks": "stocks",
  "/strategies": "strategies",
  "/screeners": "screeners",
  "/watchlists": "watchlists",
  "/backtests": "backtests",
  "/users": "users",
  "/system": "system",
  "/settings": "settings",
}

export function AppSidebar() {
  const t = useTranslations()
  const locale = useLocale()
  const pathname = usePathname()
  const router = useRouter()

  const handleLanguageChange = (nextLocale: "zh" | "en") => {
    router.replace(pathname, { locale: nextLocale })
  }

  const toggleLanguage = () => {
    const nextLocale = locale === "zh" ? "en" : "zh"
    router.replace(pathname, { locale: nextLocale })
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <BarChart3 className="h-4 w-4" />
          </div>
          <div className="flex flex-col group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold">Quant Admin</span>
            <span className="text-xs text-muted-foreground">A-Share Analytics</span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("navigation.group_title")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const key = navKeys[item.href]
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild>
                      <Link href={item.href}>
                        <item.icon />
                        <span>{t(`navigation.${key}` as any)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3 border-t">
        <div className="flex items-center justify-between gap-2 px-1">
          {/* Language Switcher Expanded Mode */}
          <div className="flex items-center gap-1.5 group-data-[collapsible=icon]:hidden">
            <button
              onClick={() => handleLanguageChange("zh")}
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded transition-all ${
                locale === "zh" 
                  ? "bg-primary text-primary-foreground shadow-sm" 
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              中
            </button>
            <button
              onClick={() => handleLanguageChange("en")}
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded transition-all ${
                locale === "en" 
                  ? "bg-primary text-primary-foreground shadow-sm" 
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              EN
            </button>
          </div>
          
          {/* Collapsed Mode Toggle */}
          <div className="hidden group-data-[collapsible=icon]:block">
            <button
              onClick={toggleLanguage}
              className="flex h-7 w-7 items-center justify-center rounded-lg border bg-background/50 text-[10px] font-bold text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Toggle Language"
            >
              {locale === "zh" ? "EN" : "中"}
            </button>
          </div>

          <ThemeToggle />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
