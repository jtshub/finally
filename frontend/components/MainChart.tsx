"use client";

import { useEffect, useRef } from "react";
import { AreaSeries, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import type { PricePoint } from "@/hooks/usePriceStream";
import { chartOptions, toSeconds } from "@/lib/chartTheme";
import { pct, price, tone } from "@/lib/format";
import type { PriceTick } from "@/lib/types";

/** Large live area chart of the selected ticker's streamed prices. */
export default function MainChart({ ticker, points, tick }: { ticker: string | null; points: PricePoint[]; tick?: PriceTick }) {
  const box = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Area"> | null>(null);
  const shownTicker = useRef<string | null>(null);

  useEffect(() => {
    const chart = createChart(box.current!, chartOptions);
    chartRef.current = chart;
    series.current = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32,157,215,0.28)",
      bottomColor: "rgba(32,157,215,0.02)",
      lineWidth: 2,
    });
    return () => {
      chart.remove();
      series.current = null;
      shownTicker.current = null;
    };
  }, []);

  useEffect(() => {
    const s = series.current;
    if (!s) return;
    const data = toSeconds(points).map((p) => ({ time: p.time as UTCTimestamp, value: p.value }));
    if (shownTicker.current !== ticker) {
      s.setData(data);
      chartRef.current?.timeScale().fitContent();
      shownTicker.current = ticker;
    } else if (data.length) {
      s.update(data[data.length - 1]);
    }
  }, [ticker, points]);

  return (
    <section data-testid="main-chart" className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-baseline gap-3 border-b border-line px-3 py-2">
        <h2 className="font-medium">{ticker ?? "Select a ticker"}</h2>
        {tick && (
          <>
            <span className="num text-base">{price(tick.price)}</span>
            <span className={`num text-xs ${tone(tick.day_change_percent)}`}>{pct(tick.day_change_percent)} today</span>
          </>
        )}
      </div>
      <div ref={box} className="min-h-0 flex-1" />
    </section>
  );
}
