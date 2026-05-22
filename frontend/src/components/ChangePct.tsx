export function ChangePct({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-mute">—</span>;
  const cls = value > 0 ? "text-green" : value < 0 ? "text-red" : "text-mute";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "•";
  return (
    <span className={`${cls} font-bold`}>
      {arrow} {value > 0 ? "+" : ""}{value.toFixed(2)}%
    </span>
  );
}

export function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.75 ? "bg-accent" : value >= 0.5 ? "bg-warn" : "bg-mute";
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 bg-panel2 rounded overflow-hidden border border-border">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-bold w-9 text-right">{pct}%</span>
    </div>
  );
}
