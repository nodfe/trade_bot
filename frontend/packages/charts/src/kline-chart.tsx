"use client";

import React, { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type HistogramData,
} from "lightweight-charts";
import { useLWCTheme } from "./use-lwc-theme";

export interface KLineBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KLineChartProps {
  data: KLineBar[];
  height?: number;
  className?: string;
  maPeriods?: number[];
}

export function KLineChart({
  data,
  height = 360,
  className = "",
  maPeriods = [5, 20],
}: KLineChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const themeColors = useLWCTheme();

  // Helper to calculate Simple Moving Averages
  const calculateSMA = (bars: KLineBar[], period: number): LineData[] => {
    const result: LineData[] = [];
    for (let i = 0; i < bars.length; i++) {
      if (i < period - 1) continue;
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += bars[i - j].close;
      }
      result.push({
        time: bars[i].timestamp.slice(0, 10),
        value: sum / period,
      });
    }
    return result;
  };

  useEffect(() => {
    if (!chartContainerRef.current || !data || data.length === 0) return;

    // 1. Initialize Chart API
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: themeColors.layout.background,
        textColor: themeColors.layout.textColor,
        fontSize: themeColors.layout.fontSize,
        fontFamily: "var(--font-sans), sans-serif",
      },
      grid: {
        vertLines: themeColors.grid.vertLines,
        horzLines: themeColors.grid.horzLines,
      },
      crosshair: {
        mode: themeColors.crosshair.mode,
        vertLine: themeColors.crosshair.vertLine,
        horzLine: themeColors.crosshair.horzLine,
      },
      rightPriceScale: {
        borderColor: themeColors.grid.vertLines.color,
        autoScale: true,
      },
      timeScale: {
        borderColor: themeColors.grid.vertLines.color,
        timeVisible: false,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 2. Add Candlestick Series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: themeColors.stockUp,
      downColor: themeColors.stockDown,
      borderUpColor: themeColors.stockUp,
      borderDownColor: themeColors.stockDown,
      wickUpColor: themeColors.stockUp,
      wickDownColor: themeColors.stockDown,
    });

    const candleData: CandlestickData[] = data.map((bar) => ({
      time: bar.timestamp.slice(0, 10),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    candlestickSeries.setData(candleData);

    // 3. Add MA Series dynamically
    const colors = ["#EAB308", "#3B82F6", "#A855F7"]; // Gold/Yellow, Blue, Purple
    const maSeriesList: ISeriesApi<"Line">[] = [];

    maPeriods.forEach((period, idx) => {
      const smaData = calculateSMA(data, period);
      if (smaData.length > 0) {
        const lineSeries = chart.addLineSeries({
          color: colors[idx % colors.length],
          lineWidth: 2,
          title: `MA${period}`,
          lastValueVisible: false,
          priceLineVisible: false,
        });
        lineSeries.setData(smaData);
        maSeriesList.push(lineSeries);
      }
    });

    // 4. Add Volume Series (overlaid at the bottom)
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "", // Overlay on the same pane
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8, // 80% from the top
        bottom: 0,
      },
    });

    const volumeData: HistogramData[] = data.map((bar) => {
      const isUp = bar.close >= bar.open;
      return {
        time: bar.timestamp.slice(0, 10),
        value: bar.volume,
        color: isUp ? `${themeColors.stockUp}50` : `${themeColors.stockDown}50`, // 50% opacity
      };
    });

    volumeSeries.setData(volumeData);

    // 5. Fit Content & Auto-Scale
    chart.timeScale().fitContent();

    // 6. Handle Container Resize Observer
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 0 || !entries[0].contentRect) return;
      const { width, height } = entries[0].contentRect;
      chart.resize(width, height);
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.removeSeries(candlestickSeries);
      maSeriesList.forEach((s) => chart.removeSeries(s));
      chart.removeSeries(volumeSeries);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height, themeColors]);

  return (
    <div className={`relative w-full rounded-xl p-2 ${className}`}>
      {/* Legend Float Overlay */}
      <div className="absolute top-4 left-4 z-10 flex gap-4 text-xs font-semibold">
        <span style={{ color: "#EAB308" }}>MA5</span>
        <span style={{ color: "#3B82F6" }}>MA20</span>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height }} />
    </div>
  );
}
