import type { PricePoint } from "@/hooks/usePriceStream";

/** Tiny SVG line of recent prices, colored by net move since the first point. */
export function Sparkline({ points, width = 72, height = 22 }: { points: PricePoint[]; width?: number; height?: number }) {
  if (points.length < 2) return <svg width={width} height={height} aria-hidden />;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const step = width / (points.length - 1);
  const d = values
    .map((v, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)},${(height - 1 - ((v - min) / span) * (height - 2)).toFixed(1)}`)
    .join("");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" strokeWidth={1.25} className={up ? "stroke-up" : "stroke-down"} />
    </svg>
  );
}
