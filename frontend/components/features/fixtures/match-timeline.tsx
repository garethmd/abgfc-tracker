"use client";

import Link from "next/link";
import { Flag, Volleyball, Whistle, X } from "lucide-react";
import type { Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { cn } from "@/lib/utils";

type Goal = Schema["GoalRead"];

const OURS = ["goal", "opp_own_goal"];

/** "1st half" / "Q3". */
export function periodLabel(period: number, periods: number): string {
  if (periods === 2) return ["1st half", "2nd half"][period - 1] ?? `Extra ${period - 2}`;
  if (periods === 4) return `Q${period}`;
  return `Period ${period}`;
}

/** What the break before a period is called. */
function breakLabel(period: number, periods: number): string {
  if (periods === 2 && period === 2) return "Half time";
  return periodLabel(period, periods);
}

type RowData = {
  goal: Goal;
  isOurs: boolean;
  ours: number;
  theirs: number;
  startsPeriod: boolean;
  period: number | null;
};

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

/**
 * The match as it happened, down a single rail: our goals on one side, theirs on the
 * other, the running score beside each one, and the rail breaking at each half or
 * quarter. Periods are the time axis - there is no clock - and a minute shows only when
 * one was recorded.
 */
export function MatchTimeline({
  goals,
  periods,
  teamName,
  oppositionName,
  ourScore,
  theirScore,
  status,
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
  status?: string;
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
  const first = rows[0];

  return (
    <Card className={cn("overflow-hidden px-3 py-4", className)}>
      <div className="grid grid-cols-[1fr_2.75rem_1fr] items-center pb-2">
        <span className="truncate pr-2 text-right text-xs font-medium">{teamName}</span>
        <span />
        <span className="truncate pl-2 text-left text-xs font-medium text-muted-foreground">
          {oppositionName}
        </span>
      </div>

      <Break
        label={first.period != null ? periodLabel(first.period, periods) : "Kick off"}
        icon={<Whistle className="size-3" />}
      />

      {rows.map((row) => (
        <div key={row.goal.id}>
          {row.startsPeriod && row.period != null && (
            <Break label={breakLabel(row.period, periods)} />
          )}
          <Row row={row} base={base} onRemove={onRemove} showScore={complete} oppositionName={oppositionName} />
        </div>
      ))}

      {status === "played" ? (
        <Break
          label={complete ? `Full time ${last.ours}–${last.theirs}` : "Full time"}
          icon={<Flag className="size-3" />}
        />
      ) : (
        // Still going: the rail runs on past the last goal.
        <div className="grid grid-cols-[1fr_2.75rem_1fr]">
          <span />
          <span className="mx-auto h-6 w-px bg-border" />
          <span />
        </div>
      )}
    </Card>
  );
}

function Row({
  row,
  base,
  onRemove,
  showScore,
  oppositionName,
}: {
  row: RowData;
  base?: string;
  onRemove?: (goal: Goal) => void;
  showScore: boolean;
  oppositionName: string;
}) {
  const g = row.goal;
  const own = g.event_type === "own_goal" || g.event_type === "opp_own_goal";
  // We never record the opposition's players, so their goals carry the team's name.
  const name = g.scorer?.display_name ?? (g.event_type === "opp_own_goal" ? "Own goal" : oppositionName);

  const score = showScore ? (
    <span className="tnum shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-xs font-semibold">
      {row.ours}
      <span className="mx-px text-muted-foreground">&ndash;</span>
      {row.theirs}
    </span>
  ) : null;

  const details = (
    <div className={cn("min-w-0 py-2.5", row.isOurs ? "pr-3 text-right" : "pl-3 text-left")}>
      <div className={cn("flex items-center gap-2", row.isOurs ? "justify-end" : "justify-start")}>
        {row.isOurs && score}
        <span className="min-w-0 truncate">
          {g.scorer && base ? (
            <Link
              href={`${base}/players/${g.scorer.id}`}
              className={cn("font-medium hover:underline", own && "text-rose-600 dark:text-rose-400")}
            >
              {name}
            </Link>
          ) : (
            <span className={cn("font-medium", own && "text-rose-600 dark:text-rose-400", !g.scorer && "text-muted-foreground")}>
              {name}
            </span>
          )}
          {own && <span className="ml-1 text-xs text-muted-foreground">(OG)</span>}
        </span>
        {!row.isOurs && score}
      </div>
      {g.assisted_by && (
        <p className="truncate text-xs text-muted-foreground">Assist: {g.assisted_by.display_name}</p>
      )}
      {g.minute != null && <p className="tnum text-xs text-muted-foreground">{g.minute}&apos;</p>}
      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(g)}
          aria-label={`Remove ${name}`}
          className="mt-1 inline-flex h-8 items-center gap-1 rounded-lg px-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <X className="size-3" /> Remove
        </button>
      )}
    </div>
  );

  return (
    <div className="grid grid-cols-[1fr_2.75rem_1fr] items-center">
      {row.isOurs ? details : <span />}
      {/* The rail: a continuous line with a node punched through it */}
      <div className="relative flex h-full min-h-14 items-center justify-center">
        <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border" aria-hidden />
        <span
          className={cn(
            "relative z-10 flex size-7 items-center justify-center rounded-full bg-card ring-1",
            own
              ? "text-rose-500 ring-rose-500/40"
              : row.isOurs
                ? "text-foreground ring-border"
                : "text-muted-foreground ring-border",
          )}
        >
          <Volleyball className="size-4" />
        </span>
      </div>
      {row.isOurs ? <span /> : details}
    </div>
  );
}

/** Kick off, half time, the start of a quarter, full time: the rail breaks for a label. */
function Break({ label, icon }: { label: string; icon?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 py-1.5">
      <span className="h-px flex-1 bg-border" />
      <span className="flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}
