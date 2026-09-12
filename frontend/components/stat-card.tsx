import { cn } from "@/lib/utils";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("rounded-xl bg-card shadow-sm ring-1 ring-border/60", className)}>{children}</div>
  );
}

export function Stat({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col", className)}>
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="tnum mt-1 text-2xl font-semibold tracking-tight">{value}</span>
      {hint && <span className="mt-0.5 text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}
