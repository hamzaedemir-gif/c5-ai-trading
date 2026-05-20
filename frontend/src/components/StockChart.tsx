import { useEffect, useRef } from "react";
import { CandlestickData, ColorType, HistogramData, createChart, IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";

interface Bar {
  ts?: string;
  date?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function tsToUnix(s: string): UTCTimestamp {
  const d = new Date(s);
  return Math.floor(d.getTime() / 1000) as UTCTimestamp;
}

export function StockChart({ bars, mode }: { bars: Bar[]; mode: "intraday" | "daily" }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#e6edf7",
        fontFamily: "JetBrains Mono, monospace",
      },
      grid: {
        vertLines: { color: "#1f2a44" },
        horzLines: { color: "#1f2a44" },
      },
      rightPriceScale: { borderColor: "#1f2a44" },
      timeScale: { borderColor: "#1f2a44", timeVisible: mode === "intraday" },
      crosshair: { mode: 1 },
    });
    const candles = chart.addCandlestickSeries({
      upColor: "#00ff88",
      downColor: "#ff4d6d",
      borderUpColor: "#00ff88",
      borderDownColor: "#ff4d6d",
      wickUpColor: "#00ff88",
      wickDownColor: "#ff4d6d",
    });
    const volSeries = chart.addHistogramSeries({
      color: "rgba(0, 255, 136, 0.35)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = candles;
    volRef.current = volSeries;

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
    };
  }, [mode]);

  useEffect(() => {
    if (!candleRef.current || !volRef.current) return;
    const cdata: CandlestickData<UTCTimestamp>[] = [];
    const vdata: HistogramData<UTCTimestamp>[] = [];
    // De-dup by timestamp, lightweight-charts requires strictly ascending unique times.
    const seen = new Set<number>();
    for (const b of bars) {
      const tsStr = b.ts ?? (b.date ? `${b.date}T00:00:00Z` : "");
      if (!tsStr) continue;
      const t = tsToUnix(tsStr);
      if (seen.has(t)) continue;
      seen.add(t);
      cdata.push({ time: t, open: b.open, high: b.high, low: b.low, close: b.close });
      vdata.push({
        time: t,
        value: b.volume,
        color: b.close >= b.open ? "rgba(0,255,136,0.45)" : "rgba(255,77,109,0.45)",
      });
    }
    candleRef.current.setData(cdata);
    volRef.current.setData(vdata);
    chartRef.current?.timeScale().fitContent();
  }, [bars]);

  return <div ref={ref} className="h-[420px] w-full" />;
}
