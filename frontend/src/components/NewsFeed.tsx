import { useEffect, useState } from "react";
import { api, NewsItem } from "../api/client";
import { Panel } from "./Panel";

export function NewsFeed({ symbol }: { symbol?: string }) {
  const [items, setItems] = useState<NewsItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    const refresh = () =>
      api
        .news(symbol)
        .then((r) => {
          if (!cancelled) setItems(r.items);
        })
        .catch(() => undefined);
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [symbol]);

  return (
    <Panel title="Live News Feed" right={<span className="text-mute text-xs">{items.length}</span>}>
      {items.length === 0 ? (
        <div className="text-mute text-sm py-6 text-center">
          No news yet. Set <span className="text-accent">FINNHUB_API_KEY</span> and run{" "}
          <span className="text-accent">python run_paper.py ingest …</span>
        </div>
      ) : (
        <ul className="space-y-2 max-h-[640px] overflow-auto pr-2">
          {items.map((n) => (
            <li
              key={n.id}
              className="border-l-2 border-accent/40 pl-3 py-1 hover:border-accent transition-colors"
            >
              <div className="flex items-baseline justify-between gap-3">
                <div className="text-sm text-text leading-snug">
                  {n.url ? (
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-accent"
                    >
                      {n.headline}
                    </a>
                  ) : (
                    n.headline
                  )}
                </div>
                {n.symbol && (
                  <span className="text-[10px] ticker text-accent shrink-0 px-1.5 py-0.5 rounded border border-accent/40">
                    {n.symbol}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-mute mt-0.5">
                {fmtTs(n.published_at)} · {n.source}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function fmtTs(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
