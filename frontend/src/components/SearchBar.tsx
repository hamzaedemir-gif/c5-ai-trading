import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

export function SearchBar({ onPick }: { onPick: (sym: string) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setItems([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .search(q.trim())
        .then((r) => {
          if (!cancelled) setItems(r.items);
        })
        .catch(() => undefined);
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (sym: string) => {
    setQ("");
    setItems([]);
    setOpen(false);
    onPick(sym);
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && items[0]) pick(items[0]);
          if (e.key === "Enter" && !items[0] && q.trim()) pick(q.trim().toUpperCase());
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Search ticker (AAPL, TSLA…)"
        className="w-full bg-panel2 border border-border rounded px-3 py-2 text-sm
          placeholder:text-mute focus:outline-none focus:border-accent
          focus:shadow-glow transition-all"
      />
      {open && items.length > 0 && (
        <ul className="absolute z-40 left-0 right-0 mt-1 bg-panel2 border border-border rounded
          max-h-72 overflow-auto shadow-xl">
          {items.map((s) => (
            <li
              key={s}
              onClick={() => pick(s)}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-accent/10 hover:text-accent ticker"
            >
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
