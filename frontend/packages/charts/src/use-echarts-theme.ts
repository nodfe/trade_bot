import { useEffect, useMemo, useState } from "react";

/**
 * Reads a CSS custom property from :root or the <html> element,
 * returning the raw style string (e.g. "oklch(1 0 0)").
 */
function getCSSVar(name: string, element?: HTMLElement): string {
  const el = element ?? document.documentElement;
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/**
 * Resolves any CSS color string (including var(), oklch(), hsl(), names)
 * into a standard Hex color code using the browser's native layout engine.
 */
export function resolveColorToHex(cssColor: string): string {
  if (typeof document === "undefined" || !cssColor) return "#888888";
  
  // Resolve var() custom properties first
  if (cssColor.startsWith("var(")) {
    const varName = cssColor.slice(4, -1).trim();
    return resolveColorToHex(getCSSVar(varName));
  }

  const temp = document.createElement("div");
  temp.style.color = cssColor;
  temp.style.display = "none";
  document.body.appendChild(temp);
  const computed = getComputedStyle(temp).color; // returns "rgb(r, g, b)" or "rgba(r, g, b, a)"
  document.body.removeChild(temp);

  const match = computed.match(/\d+(\.\d+)?/g);
  if (match && match.length >= 3) {
    const r = Math.round(Number(match[0]));
    const g = Math.round(Number(match[1]));
    const b = Math.round(Number(match[2]));
    return "#" + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
  }
  return cssColor;
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
 * Hook that reads Shadcn Tailwind v4 CSS variables and returns an ECharts theme object.
 * Re-reads variables when dark mode toggles (observes <html> class changes).
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
      const raw = getCSSVar(`--color-chart-${i + 1}`, root);
      return resolveColorToHex(raw);
    });

    const stockUp = resolveColorToHex(getCSSVar("--color-stock-up", root));
    const stockDown = resolveColorToHex(getCSSVar("--color-stock-down", root));
    const foreground = resolveColorToHex(getCSSVar("--color-foreground", root));
    const background = resolveColorToHex(getCSSVar("--color-background", root));
    const mutedForeground = resolveColorToHex(getCSSVar("--color-muted-foreground", root));
    const border = resolveColorToHex(getCSSVar("--color-border", root));

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

export { getCSSVar };
