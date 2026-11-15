"use client";

import { useEffect, useRef } from "react";
import { BaselineSeries, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { chartOptions, toSeconds } from "@/lib/chartTheme";
import type { Snapshot } from "@/lib/types";

/** Total portfolio value over time, green above the starting value and red below. */
export default function PnlChart({ snapshots }: { snapshots: Snapshot[] }) {
  const box = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Baseline"> | null>(null);

  useEffect(() => {
    const chart = createChart(box.current!, chartOptions);
    chartRef.current = chart;
    series.current = chart.addSeries(BaselineSeries, {
      topLineColor: "#26c281",
      topFillColor1: "rgba(38,194,129,0.25)",
      topFillColor2: "rgba(38,194,129,0.02)",
      bottomLineColor: "#ef5350",
      bottomFillColor1: "rgba(239,83,80,0.02)",
      bottomFillColor2: "rgba(239,83,80,0.25)",
      lineWidth: 2,
    });
    return () => chart.remove();
  }, []);

  useEffect(() => {
    const s = series.current;
    if (!s || !snapshots.length) return;
    const points = toSeconds(snapshots.map((x) => ({ time: Date.parse(x.recorded_at) / 1000, value: x.total_value })));
    s.applyOptions({ baseValue: { type: "price", price: snapshots[0].total_value } });
    s.setData(points.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    chartRef.current?.timeScale().fitContent();
  }, [snapshots]);

  return (
    <section data-testid="pnl-chart" data-points={snapshots.length} className="flex min-h-0 flex-1 flex-col">
      <h2 className="border-b border-line px-3 py-2 font-medium">Portfolio value</h2>
      <div ref={box} className="min-h-0 flex-1" />
    </section>
  );
}
