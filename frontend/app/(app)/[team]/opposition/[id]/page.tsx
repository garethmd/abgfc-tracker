"use client";

import Link from "next/link";
import { use, useState } from "react";
import { ChevronRight, MapPin } from "lucide-react";
import { $api, type Schema } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { useTeam } from "@/lib/team-context";
import { formatDate, STATUS_LABEL } from "@/lib/format";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Card, Stat } from "@/components/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";

const RESULT_STYLE: Record<string, string> = {
  W: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  D: "bg-muted text-muted-foreground",
  L: "bg-rose-500/15 text-rose-700 dark:text-rose-400",
};

export default function OppositionPage({ params }: PageProps<"/[team]/opposition/[id]">) {
  const { id } = use(params);
  const teamId = Number(id);
  const { team, base } = useTeam();
  const { me } = useMe();
  // Cohort/club users can widen to every ABGFC team they can see.
  const canWiden = me.teams.length > 1;
  const [scope, setScope] = useState<"team" | "all">("team");

  const h2h = $api.useQuery(
    "get",
    "/api/v1/teams/{team_id}/head-to-head",
    { params: { path: { team_id: teamId }, query: scope === "team" ? { club_team_id: team.id } : {} } },
  );

  if (h2h.isPending) return <div className="mx-auto max-w-2xl space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-40 rounded-xl" /><Skeleton className="h-64 rounded-xl" /></div>;
  if (h2h.error) return <ErrorState error={h2h.error} onRetry={() => h2h.refetch()} />;
  const d = h2h.data;
  const rec = d.record;
  const gd = rec.goal_difference;
  const showTeamColumn = scope === "all";

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={d.team.name}
        description={[d.team.short_name, d.team.colours, d.team.club_team_id ? "One of our own teams" : null].filter(Boolean).join(" · ") || undefined}
        action={
          canWiden ? (
            <div className="flex rounded-lg bg-muted p-0.5 text-xs font-medium">
              {(["team", "all"] as const).map((s) => (
                <button key={s} type="button" onClick={() => setScope(s)} className={cn("h-8 rounded-md px-3 transition-colors", scope === s ? "bg-background shadow-sm" : "text-muted-foreground")}>
                  {s === "team" ? team.name : "All ABGFC"}
                </button>
              ))}
            </div>
          ) : undefined
        }
      />

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">{scope === "team" ? `${team.name} v ${d.team.short_name ?? d.team.name}` : `ABGFC v ${d.team.short_name ?? d.team.name}`}</h2>
          <span className="tnum text-xs text-muted-foreground">{rec.played} played</span>
        </div>
        {rec.played === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Not played them yet.</p>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-3 gap-4">
              <Stat label="Won" value={rec.won} />
              <Stat label="Drawn" value={rec.drawn} />
              <Stat label="Lost" value={rec.lost} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4 border-t border-border/60 pt-4">
              <Stat label="For" value={rec.goals_for} />
              <Stat label="Against" value={rec.goals_against} />
              <Stat label="Diff" value={<span className={cn(gd > 0 && "text-emerald-600 dark:text-emerald-400", gd < 0 && "text-rose-600 dark:text-rose-400")}>{gd > 0 ? `+${gd}` : gd}</span>} />
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-border/60 pt-4">
              <div className="flex gap-1.5">
                {d.form.map((r, i) => (
                  <span key={i} className={cn("flex size-7 items-center justify-center rounded-full text-[11px] font-semibold", RESULT_STYLE[r])}>{r}</span>
                ))}
              </div>
              <Stat label="Win rate" value={`${rec.win_pct}%`} className="items-end" />
            </div>
          </>
        )}
      </Card>

      {d.team.notes && <p className="mt-3 text-sm text-muted-foreground">{d.team.notes}</p>}

      <Section title="Upcoming" items={d.upcoming} empty="No fixtures scheduled against them." base={base} showTeam={showTeamColumn} />
      <Section title="Results" items={d.played} empty="No results yet." base={base} showTeam={showTeamColumn} />
      {d.other.length > 0 && <Section title="Postponed / cancelled" items={d.other} empty="" base={base} showTeam={showTeamColumn} />}
    </div>
  );
}

function Section({ title, items, empty, base, showTeam }: { title: string; items: Schema["HeadToHeadFixture"][]; empty: string; base: string; showTeam: boolean }) {
  return (
    <section className="mt-8">
      <SectionTitle>{title}</SectionTitle>
      {!items.length ? (
        <EmptyState title={empty} className="py-8" />
      ) : (
        <Card className="divide-y divide-border/40 overflow-hidden">
          {items.map((f) => (
            <Link key={f.id} href={`${base}/fixtures/${f.id}`} className="flex min-h-14 items-center gap-3 px-4 py-3 hover:bg-accent/50 active:bg-accent">
              <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold", f.result ? RESULT_STYLE[f.result] : "bg-muted text-[11px] font-medium text-muted-foreground")}>
                {f.result ?? (f.match_number ? `#${f.match_number}` : "–")}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {formatDate(f.kickoff_at)}
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">({f.venue === "home" ? "H" : f.venue === "away" ? "A" : "N"})</span>
                </span>
                <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                  {showTeam && <span className="font-medium text-foreground">{f.club_team_name}</span>}
                  <span>{f.season_name}</span><span aria-hidden>·</span><span>{f.competition_name}</span>
                  {f.venue_notes && (<><span aria-hidden>·</span><MapPin className="size-3" /><span className="truncate">{f.venue_notes}</span></>)}
                  {f.status !== "played" && f.status !== "scheduled" && <span className="rounded bg-muted px-1 text-[10px]">{STATUS_LABEL[f.status]}</span>}
                </span>
              </span>
              {f.result ? (
                <span className="tnum text-lg font-semibold tracking-tight">{f.our_score}<span className="mx-0.5 text-muted-foreground">–</span>{f.their_score}</span>
              ) : (
                <ChevronRight className="size-4 text-muted-foreground" />
              )}
            </Link>
          ))}
        </Card>
      )}
    </section>
  );
}
