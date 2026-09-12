"use client";

import { useState } from "react";
import type { Schema } from "@/lib/api/client";
import { Card, Stat } from "@/components/stat-card";
import { FormPips } from "./form-pips";
import { cn } from "@/lib/utils";

type Scope = "overall" | "league";

export function RecordCard({ summary }: { summary: Schema["SeasonSummary"] }) {
  const [scope, setScope] = useState<Scope>("overall");
  const rec = summary[scope];
  const gd = rec.goal_difference;

  return (
    <Card className="p-5 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Team record</h2>
        <div className="flex rounded-lg bg-muted p-0.5 text-xs font-medium">
          {(["overall", "league"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setScope(s)}
              className={cn(
                "h-8 rounded-md px-3 transition-colors",
                scope === s ? "bg-background shadow-sm" : "text-muted-foreground",
              )}
            >
              {s === "overall" ? "All" : "League"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 flex items-end gap-1 tnum">
        <span className="text-5xl font-semibold tracking-tighter">{rec.played}</span>
        <span className="mb-1.5 text-sm text-muted-foreground">played</span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-4 border-t border-border/60 pt-5">
        <Stat label="Won" value={rec.won} />
        <Stat label="Drawn" value={rec.drawn} />
        <Stat label="Lost" value={rec.lost} />
      </div>
      <div className="mt-4 grid grid-cols-3 gap-4">
        <Stat label="For" value={rec.goals_for} />
        <Stat label="Against" value={rec.goals_against} />
        <Stat
          label="Diff"
          value={
            <span className={cn(gd > 0 && "text-emerald-600 dark:text-emerald-400", gd < 0 && "text-rose-600 dark:text-rose-400")}>
              {gd > 0 ? `+${gd}` : gd}
            </span>
          }
        />
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-border/60 pt-5">
        <div>
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Last 5</span>
          <div className="mt-1.5">
            <FormPips form={summary.form} />
          </div>
        </div>
        <Stat label="Win rate" value={`${rec.win_pct}%`} className="items-end" />
      </div>
    </Card>
  );
}
