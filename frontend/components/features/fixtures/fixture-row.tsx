import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Schema } from "@/lib/api/client";
import { formatDate, STATUS_LABEL } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const RESULT_STYLE = {
  W: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  D: "bg-muted text-muted-foreground",
  L: "bg-rose-500/15 text-rose-700 dark:text-rose-400",
};

export function resultOf(f: Schema["FixtureRead"]): "W" | "D" | "L" | null {
  if (f.status !== "played" || f.our_score == null || f.their_score == null) return null;
  return f.our_score > f.their_score ? "W" : f.our_score < f.their_score ? "L" : "D";
}

export function FixtureRow({ fixture: f, base = "" }: { fixture: Schema["FixtureRead"]; base?: string }) {
  const result = resultOf(f);
  return (
    <Link
      href={`${base}/fixtures/${f.id}`}
      className="flex min-h-16 items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/50 active:bg-accent"
    >
      <div className="flex w-12 shrink-0 flex-col items-center">
        {result ? (
          <span className={cn("flex size-9 items-center justify-center rounded-lg text-sm font-bold", RESULT_STYLE[result])}>
            {result}
          </span>
        ) : (
          <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-[11px] font-medium text-muted-foreground">
            {f.match_number ? `#${f.match_number}` : "–"}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">
          {f.opposition.short_name ?? f.opposition.name}
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">({f.venue === "home" ? "H" : f.venue === "away" ? "A" : "N"})</span>
        </p>
        <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>{formatDate(f.kickoff_at)}</span>
          <span aria-hidden>·</span>
          <span>{f.competition.name}</span>
          {f.status !== "played" && f.status !== "scheduled" && (
            <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px]">
              {STATUS_LABEL[f.status]}
            </Badge>
          )}
        </p>
      </div>
      {result ? (
        <span className="tnum text-lg font-semibold tracking-tight">
          {f.our_score}<span className="mx-0.5 text-muted-foreground">–</span>{f.their_score}
        </span>
      ) : (
        <ChevronRight className="size-4 text-muted-foreground" />
      )}
    </Link>
  );
}
