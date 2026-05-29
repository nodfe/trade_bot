import { useEffect, useMemo, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  LineWidth,
} from "lightweight-charts";
import { getCSSVar, resolveColorToHex } from "./use-echarts-theme";

export interface LWCThemeColors {
  layout: {
    background: { type: ColorType; color: string };
    textColor: string;
    fontSize: number;
  };
  grid: {
    vertLines: { color: string; style: LineStyle };
    horzLines: { color: string; style: LineStyle };
  };
  crosshair: {
    mode: CrosshairMode;
    vertLine: { color: string; style: LineStyle; width: LineWidth; labelBackgroundColor: string };
    horzLine: { color: string; style: LineStyle; width: LineWidth; labelBackgroundColor: string };
  };
  /** A-share convention: red = up, green = down */
  stockUp: string;
  stockDown: string;
}

/**
 * Hook that reads Shadcn Tailwind v4 CSS variables and returns a theme config
 * for TradingView Lightweight Charts.
 *
 * A-share convention: red = up (--color-stock-up), green = down (--color-stock-down).
 * Re-reads variables when dark mode toggles (observes <html> class changes).
 */
export function useLWCTheme(): LWCThemeColors {
  const [isDark, setIsDark] = useState(() =>
    typeof document !== "undefined"
      ? document.documentElement.classList.contains("dark")
      : false
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  return useMemo(() => {
    const root = document.documentElement;

    const background = resolveColorToHex(getCSSVar("--color-background", root));
    const foreground = resolveColorToHex(getCSSVar("--color-foreground", root));
    const border = resolveColorToHex(getCSSVar("--color-border", root));
    const mutedForeground = resolveColorToHex(getCSSVar("--color-muted-foreground", root));
    const stockUp = resolveColorToHex(getCSSVar("--color-stock-up", root));
    const stockDown = resolveColorToHex(getCSSVar("--color-stock-down", root));

    return {
      layout: {
        background: { type: ColorType.Solid, color: background },
        textColor: mutedForeground,
        fontSize: 12,
      },
      grid: {
        vertLines: { color: border, style: LineStyle.Dashed },
        horzLines: { color: border, style: LineStyle.Dashed },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: foreground,
          style: LineStyle.Dashed,
          width: 1 as LineWidth,
          labelBackgroundColor: stockUp,
        },
        horzLine: {
          color: foreground,
          style: LineStyle.Dashed,
          width: 1 as LineWidth,
          labelBackgroundColor: stockUp,
        },
      },
      stockUp,
      stockDown,
    };
  }, [isDark]);
}
