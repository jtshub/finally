"use client";

import { useEffect, useRef, useState } from "react";
import { price as fmt } from "@/lib/format";

/** How long the highlight is held before it fades out (fade itself is 500ms in CSS). */
export const FLASH_HOLD_MS = 120;

/** Price text that flashes green/red when the value ticks up/down. */
export function FlashPrice({ value, testId }: { value: number | null; testId?: string }) {
  const prev = useRef(value);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    const last = prev.current;
    prev.current = value;
    if (last == null || value == null || last === value) return;
    setFlash(value > last ? "up" : "down");
    const t = setTimeout(() => setFlash(null), FLASH_HOLD_MS);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <span
      data-testid={testId}
      data-flash={flash ?? undefined}
      className={`num rounded-sm px-1 ${flash ? `flash-${flash}` : "flash-fade"}`}
    >
      {fmt(value)}
    </span>
  );
}
