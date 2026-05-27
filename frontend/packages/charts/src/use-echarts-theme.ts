import { useEffect, useMemo, useState } from "react";

/**
 * Reads a CSS custom property from :root or the <html> element,
 * returning the raw HSL value string (e.g. "12 76% 61%").
 */
function getCSSVar(name: string, element?: HTMLElement): string {
  const el = element ?? document.documentElement;
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/**
 * Converts an HSL string like "12 76% 61%" to a CSS color string "hsl(12 76% 61%)".
 */
function hslToCSS(raw: string): string {
  if (!raw) return "";
  // Already has hsl() wrapper
  if (raw.startsWith("hsl")) return raw;
  return `hsl(${raw})`;
}

/**
 * Converts an HSL string to a hex color for libraries that don't support hsl().
 */
function hslToHex(raw: string): string {
  if (!raw) return "#888888";
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

export interface EChartsTheme {
  color: string[];
  backgroundColor: string;
  textStyle: { color: string };
  title: { textStyle: { color: string }; subtextStyle: { color: string } };
  legend: { textStyle: { color: string } };
  categoryAxis: {
    axisLine: { lineStyle: { color: string } };
    axisTick: { lineStyle: { color: string } };
    axisLabel: { color: string };
    splitLine: { lineStyle: { color: string } };
  };
  valueAxis: {
    axisLine: { lineStyle: { color: string } };
    axisTick: { lineStyle: { color: string } };
    axisLabel: { color: string };
    splitLine: { lineStyle: { color: string } };
  };
  tooltip: {
    backgroundColor: string;
    borderColor: string;
    textStyle: { color: string };
  };
}

/**
 * Hook that reads Shadcn CSS variables and returns an ECharts theme object.
 *
 * A-share convention: red = up (--stock-up), green = down (--stock-down).
 * The hook re-reads variables when dark mode toggles (observes <html> class changes).
 */
export function useEChartsTheme(): EChartsTheme {
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

    const chartColors = Array.from({ length: 5 }, (_, i) => {
      const raw = getCSSVar(`--chart-${i + 1}`, root);
      return hslToCSS(raw);
    });

    const stockUp = hslToCSS(getCSSVar("--stock-up", root));
    const stockDown = hslToCSS(getCSSVar("--stock-down", root));
    const foreground = hslToCSS(getCSSVar("--foreground", root));
    const background = hslToCSS(getCSSVar("--background", root));
    const mutedForeground = hslToCSS(getCSSVar("--muted-foreground", root));
    const border = hslToCSS(getCSSVar("--border", root));

    // Prepend financial colors so chart series can use them easily
    const color = [stockUp, stockDown, ...chartColors];

    return {
      color,
      backgroundColor: background,
      textStyle: { color: foreground },
      title: {
        textStyle: { color: foreground },
        subtextStyle: { color: mutedForeground },
      },
      legend: { textStyle: { color: foreground } },
      categoryAxis: {
        axisLine: { lineStyle: { color: border } },
        axisTick: { lineStyle: { color: border } },
        axisLabel: { color: mutedForeground },
        splitLine: { lineStyle: { color: border } },
      },
      valueAxis: {
        axisLine: { lineStyle: { color: border } },
        axisTick: { lineStyle: { color: border } },
        axisLabel: { color: mutedForeground },
        splitLine: { lineStyle: { color: border } },
      },
      tooltip: {
        backgroundColor: background,
        borderColor: border,
        textStyle: { color: foreground },
      },
    };
  }, [isDark]);
}

export { hslToCSS, hslToHex, getCSSVar };
