import { useEffect, useMemo, useState } from "react";
import type {
  ColorType,
  CrosshairMode,
  LineStyle,
} from "lightweight-charts";

/**
 * Reads a CSS custom property from the <html> element,
 * returning the raw HSL value string (e.g. "0 80% 58%").
 */
function getCSSVar(name: string, element?: HTMLElement): string {
  const el = element ?? document.documentElement;
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/**
 * Converts an HSL string to a hex color for Lightweight Charts,
 * which requires hex or rgba format.
 */
function hslToHex(raw: string): string {
  if (!raw) return "#888888";
  if (raw.startsWith("#")) return raw;
  const parts = raw.replace(/%/g, "").split(/\s+/).map(Number);
  if (parts.length < 3) return "#888888";
  const [h, s, l] = parts;
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l / 100 - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

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
    vertLine: { color: string; style: LineStyle; width: number; labelBackgroundColor: string };
    horzLine: { color: string; style: LineStyle; width: number; labelBackgroundColor: string };
  };
  /** A-share convention: red = up, green = down */
  stockUp: string;
  stockDown: string;
}

/**
 * Hook that reads Shadcn CSS variables and returns a theme config
 * for TradingView Lightweight Charts.
 *
 * A-share convention: red = up (--stock-up), green = down (--stock-down).
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

    const background = hslToHex(getCSSVar("--background", root));
    const foreground = hslToHex(getCSSVar("--foreground", root));
    const border = hslToHex(getCSSVar("--border", root));
    const mutedForeground = hslToHex(getCSSVar("--muted-foreground", root));
    const stockUp = hslToHex(getCSSVar("--stock-up", root));
    const stockDown = hslToHex(getCSSVar("--stock-down", root));

    return {
      layout: {
        background: { type: ColorType.Solid, color: background },
        textColor: mutedForeground,
        fontSize: 12,
      },
      grid: {
        vertLines: { color: border, style: 2 }, // LineStyle.Dashed
        horzLines: { color: border, style: 2 },
      },
      crosshair: {
        mode: 0 as CrosshairMode, // CrosshairMode.Normal
        vertLine: {
          color: foreground,
          style: 2,
          width: 1,
          labelBackgroundColor: stockUp,
        },
        horzLine: {
          color: foreground,
          style: 2,
          width: 1,
          labelBackgroundColor: stockUp,
        },
      },
      stockUp,
      stockDown,
    };
  }, [isDark]);
}

export { hslToHex, getCSSVar };
