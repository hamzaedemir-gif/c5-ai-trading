import { useEffect, useRef, useState } from "react";

/** Flashes green / red briefly when the value changes. */
export function PriceCell({
  value,
  fmt = (v) => v.toFixed(2),
  className = "",
}: {
  value: number | null | undefined;
  fmt?: (v: number) => string;
  className?: string;
}) {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (value == null) return;
    if (prev.current != null && prev.current !== value) {
      setFlash(value > prev.current ? "up" : "down");
      const t = setTimeout(() => setFlash(null), 700);
      return () => clearTimeout(t);
    }
    prev.current = value;
  }, [value]);

  useEffect(() => {
    if (value != null) prev.current = value;
  }, [value]);

  const anim = flash === "up" ? "animate-flashUp" : flash === "down" ? "animate-flashDown" : "";
  return (
    <span className={`inline-block px-1 rounded ${anim} ${className}`}>
      {value == null ? "—" : fmt(value)}
    </span>
  );
}
