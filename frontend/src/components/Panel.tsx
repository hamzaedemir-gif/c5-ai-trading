import React from "react";

export function Panel({
  title,
  children,
  right,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`bg-panel border border-border rounded-lg overflow-hidden glow-border ${className}`}
    >
      <header className="px-4 py-2 border-b border-border flex items-center justify-between bg-panel2">
        <h2 className="text-accent text-xs font-bold tracking-widest uppercase">{title}</h2>
        {right}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
