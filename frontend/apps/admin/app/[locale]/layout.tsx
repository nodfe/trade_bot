import type { Metadata } from "next"
import { Inter, Outfit } from "next/font/google"
import { notFound } from "next/navigation"
import { NextIntlClientProvider } from "next-intl"
import { getMessages, setRequestLocale } from "next-intl/server"

import "./globals.css"
import { routing } from "@/i18n/routing"
import { QueryProvider } from "@/components/query-provider"
import { ThemeProvider } from "@/components/theme-provider"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
})

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
})

export const metadata: Metadata = {
  title: "Quant Admin - A-Share Analytics",
  description: "Chinese A-share quantitative analysis admin dashboard",
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode
  params: Promise<{ locale: string }>
}>) {
  const { locale } = await params

  if (!routing.locales.includes(locale as any)) {
    notFound()
  }

  // Set request locale for static rendering optimization
  setRequestLocale(locale)

  // Retrieve translation messages for Client context
  const messages = await getMessages()

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className={`${inter.variable} ${outfit.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <QueryProvider>
            <NextIntlClientProvider messages={messages}>
              <SidebarProvider>
                <AppSidebar />
                <SidebarInset>
                  <header className="flex h-14 items-center gap-2 border-b px-4">
                    <SidebarTrigger />
                    <div className="flex-1" />
                  </header>
                  <main className="flex-1 p-4">
                    {children}
                  </main>
                </SidebarInset>
              </SidebarProvider>
            </NextIntlClientProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
