"use client";

import Link from "next/link";
import { X } from "lucide-react";
import type { Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { cn } from "@/lib/utils";

type Goal = Schema["GoalRead"];

const OURS = ["goal", "opp_own_goal"];

/** "1st half" / "Q3" - and what to call the break before a period starts. */
export function periodLabel(period: number, periods: number): string {
  if (periods === 2) return ["1st half", "2nd half"][period - 1] ?? `Extra ${period - 2}`;
  if (periods === 4) return `Q${period}`;
  return `Period ${period}`;
}

function breakLabel(period: number, periods: number): string {
  if (periods === 2 && period === 2) return "Half time";
  if (period > periods) return periodLabel(period, periods);
  return periodLabel(period, periods);
}

/**
 * The match as it happened: our goals on one side, theirs on the other, the score
 * climbing down the middle, a divider at each half or quarter. Periods are the time
 * axis - there is no clock, and a minute is shown only if one was recorded.
 */
export function MatchTimeline({
  goals,
  periods,
  teamName,
  oppositionName,
  ourScore,
  theirScore,
  base,
  onRemove,
  className,
}: {
  goals: Goal[];
  periods: number;
  teamName: string;
  oppositionName: string;
  /** The stored score. The running score is only shown when the events account for it -
   *  matches recorded before opposition goals existed would otherwise climb to a score
   *  that never happened. */
  ourScore?: number | null;
  theirScore?: number | null;
  base?: string;
  /** Live screen only: remove a goal that went in wrong. */
  onRemove?: (goal: Goal) => void;
  className?: string;
}) {
  const rows = buildRows(goals);
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const complete =
    ourScore == null || theirScore == null || (last.ours === ourScore && last.theirs === theirScore);

  return (
    <Card className={cn("px-3 py-5", className)}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-x-2 text-sm">
        <Side name={teamName} align="right" />
        <span className="px-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Goals
        </span>
        <Side name={oppositionName} align="left" />
      </div>

      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-x-2 gap-y-1">
        {rows.map((r, i) => (
          <Row key={r.goal.id} row={r} first={i === 0} periods={periods} base={base} onRemove={onRemove} showScore={complete} />
        ))}
      </div>
    </Card>
  );
}

/** Walk the events in order, carrying the running score and noticing period changes.
 *  Module scope, not the component body: the React Compiler forbids accumulating into
 *  render-scope variables. */
function buildRows(goals: Goal[]): RowData[] {
  const rows: RowData[] = [];
  let ours = 0;
  let theirs = 0;
  let lastPeriod: number | null = null;
  for (const goal of goals) {
    const isOurs = OURS.includes(goal.event_type);
    if (isOurs) ours += 1;
    else theirs += 1;
    // A divider whenever the period moves on; nothing for goals recorded before periods
    // existed (those all come through with period = null).
    const startsPeriod = goal.period != null && lastPeriod != null && goal.period !== lastPeriod;
    if (goal.period != null) lastPeriod = goal.period;
    rows.push({ goal, isOurs, ours, theirs, startsPeriod, period: goal.period });
  }
  return rows;
}

function Side({ name, align }: { name: string; align: "left" | "right" }) {
  return (
    <span className={cn("truncate text-xs font-medium text-muted-foreground", align === "right" ? "text-right" : "text-left")}>
      {name}
    </span>
  );
}

type RowData = {
  goal: Goal;
  isOurs: boolean;
  ours: number;
  theirs: number;
  startsPeriod: boolean;
  period: number | null;
};

function Row({
  row,
  first,
  periods,
  base,
  onRemove,
  showScore,
}: {
  row: RowData;
  first: boolean;
  periods: number;
  base?: string;
  onRemove?: (goal: Goal) => void;
  showScore: boolean;
}) {
  const g = row.goal;
  const own = g.event_type === "own_goal" || g.event_type === "opp_own_goal";
  const detail = (
    <div className={cn("min-w-0 py-1.5", row.isOurs ? "text-right" : "text-left")}>
      {g.scorer ? (
        <>
          {base ? (
            <Link href={`${base}/players/${g.scorer.id}`} className={cn("font-medium hover:underline", own && "text-rose-600 dark:text-rose-400")}>
              {g.scorer.display_name}
            </Link>
          ) : (
            <span className={cn("font-medium", own && "text-rose-600 dark:text-rose-400")}>{g.scorer.display_name}</span>
          )}
          {own && <span className="ml-1 text-xs text-muted-foreground">(OG)</span>}
          {g.assisted_by && (
            <p className="truncate text-xs text-muted-foreground">Assist: {g.assisted_by.display_name}</p>
          )}
        </>
      ) : (
        <span className="font-medium text-muted-foreground">
          {g.event_type === "opp_own_goal" ? "Own goal" : "Opposition goal"}
        </span>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(g)}
          aria-label="Remove goal"
          className="mt-0.5 inline-flex h-8 items-center gap-1 rounded-lg px-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <X className="size-3" /> Remove
        </button>
      )}
    </div>
  );

  return (
    <>
      {/* Kick-off, half time, or the start of a quarter */}
      {(first || row.startsPeriod) && row.period != null && (
        <Divider label={first ? periodLabel(row.period, periods) : breakLabel(row.period, periods)} />
      )}

      {row.isOurs ? detail : <span />}
      <div className="flex w-16 flex-col items-center gap-0.5 self-stretch justify-center">
        {showScore ? (
          <span className="tnum rounded-md bg-muted px-2 py-0.5 text-xs font-semibold">
            {row.ours}<span className="mx-0.5 text-muted-foreground">-</span>{row.theirs}
          </span>
        ) : (
          <span className="size-1.5 rounded-full bg-border" />
        )}
        {g.minute != null && <span className="tnum text-[10px] text-muted-foreground">{g.minute}&apos;</span>}
      </div>
      {row.isOurs ? <span /> : detail}
    </>
  );
}

function Divider({ label }: { label: string }) {
  return (
    <div className="col-span-3 flex items-center gap-3 py-2">
      <span className="h-px flex-1 bg-border" />
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}
