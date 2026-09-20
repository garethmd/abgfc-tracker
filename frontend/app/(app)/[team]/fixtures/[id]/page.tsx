"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Award, FileDown, MapPin, MoreHorizontal, Pencil, Radio, Trash2 } from "lucide-react";
import { matchdaySheetUrl } from "@/lib/reports";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { formatLongDate, formatTime, STATUS_LABEL, VENUE_LABEL } from "@/lib/format";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { MatchNotes } from "@/components/features/fixtures/match-notes";
import { SelectionCard } from "@/components/features/fixtures/selection-card";

export default function FixtureDetailPage({ params }: PageProps<"/[team]/fixtures/[id]">) {
  const { id } = use(params);
  const { team, base, canEdit } = useTeam();
  const fixtureId = Number(id);
  const router = useRouter();
  const qc = useQueryClient();
  const q = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}", { params: { path: { fixture_id: fixtureId } } });
  const del = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}");

  async function onDelete() {
    if (!confirm("Delete this fixture and everything recorded against it?")) return;
    try {
      await del.mutateAsync({ params: { path: { fixture_id: fixtureId } } });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
      toast.success("Fixture deleted");
      router.replace(`${base}/fixtures`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  if (q.isPending) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;

  const f = q.data;
  const played = f.status === "played";
  const result = played && f.our_score != null && f.their_score != null
    ? f.our_score > f.their_score ? "W" : f.our_score < f.their_score ? "L" : "D"
    : null;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={<span>{team.name} <span className="text-muted-foreground">v</span> <Link href={`${base}/opposition/${f.opposition.id}`} className="hover:underline">{f.opposition.name}</Link></span>}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{formatLongDate(f.kickoff_at)}, {formatTime(f.kickoff_at)}</span>
            <span aria-hidden>·</span>
            <span>{f.competition.name}</span>
            {f.match_number && (<><span aria-hidden>·</span><span>Match {f.match_number}</span></>)}
          </span>
        }
        action={
          canEdit && (
          <DropdownMenu>
            <DropdownMenuTrigger className="flex size-10 items-center justify-center rounded-lg ring-1 ring-border/60 hover:bg-accent">
              <MoreHorizontal className="size-4" />
              <span className="sr-only">More</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`${base}/fixtures/${f.id}/edit`}><Pencil className="size-4" /> Edit fixture</Link>
              </DropdownMenuItem>
              {played && (
                <DropdownMenuItem asChild>
                  <Link href={`${base}/fixtures/${f.id}/entry`}><Award className="size-4" /> Edit result</Link>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem asChild>
                <a href={matchdaySheetUrl(f.team_season_id, f.id)} download><FileDown className="size-4" /> Matchday sheet (PDF)</a>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={onDelete}>
                <Trash2 className="size-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          )
        }
      />

      <Card className="p-6">
        <div className="flex items-center justify-between gap-4">
          <TeamName name="Blues" align="left" />
          {played || f.status === "live" ? (
            <div className="flex items-center gap-3 tnum">
              <span className="text-5xl font-semibold tracking-tighter">{f.our_score}</span>
              <span className="text-2xl text-muted-foreground">–</span>
              <span className="text-5xl font-semibold tracking-tighter">{f.their_score}</span>
            </div>
          ) : (
            <Badge variant="secondary" className="h-7 px-3 text-xs">{STATUS_LABEL[f.status]}</Badge>
          )}
          <TeamName name={f.opposition.short_name ?? f.opposition.name} align="right" />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {f.status === "live" && <span className="font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400">Live</span>}
          {result && (
            <span className={cn("font-semibold", result === "W" && "text-emerald-600 dark:text-emerald-400", result === "L" && "text-rose-600 dark:text-rose-400")}>
              {result === "W" ? "Win" : result === "L" ? "Loss" : "Draw"}
            </span>
          )}
          <span className="flex items-center gap-1"><MapPin className="size-3" />{VENUE_LABEL[f.venue]}{f.venue_notes ? ` · ${f.venue_notes}` : ""}</span>
        </div>
        {!played && f.status === "scheduled" && canEdit && (
          <div className="mt-6 grid grid-cols-[1fr_1fr_auto] gap-2">
            <Button asChild className="h-12 w-full">
              <Link href={`${base}/fixtures/${f.id}/live`}><Radio className="size-4" /> Start match</Link>
            </Button>
            <Button asChild variant="outline" className="h-12 w-full">
              <Link href={`${base}/fixtures/${f.id}/entry`}>Enter result</Link>
            </Button>
            <Button asChild variant="outline" className="h-12" title="Download the matchday sheet (PDF)">
              <a href={matchdaySheetUrl(f.team_season_id, f.id)} download>
                <FileDown className="size-4" /> Sheet
              </a>
            </Button>
          </div>
        )}
        {f.status === "live" && canEdit && (
          <div className="mt-6">
            <Button asChild className="h-12 w-full">
              <Link href={`${base}/fixtures/${f.id}/live`}><Radio className="size-4" /> Continue live match</Link>
            </Button>
          </div>
        )}
      </Card>

      {(f.status === "scheduled" || f.status === "postponed") && (
        <SelectionCard fixture={f} base={base} canEdit={canEdit} />
      )}

      {f.warnings.length > 0 && (
        <div className="mt-4 flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
          <ul className="space-y-0.5">
            {f.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </div>
      )}

      {played && (
        <div className="mt-8 grid gap-8 md:grid-cols-2">
          <section>
            <SectionTitle>Goals</SectionTitle>
            {f.goals.length ? (
              <Card className="divide-y divide-border/40">
                {f.goals.map((g) => <GoalLine key={g.id} goal={g} base={base} />)}
              </Card>
            ) : (
              <p className="text-sm text-muted-foreground">No goals recorded.</p>
            )}

            <SectionTitle className="mt-8">Awards</SectionTitle>
            {f.awards.length ? (
              <Card className="divide-y divide-border/40">
                {f.awards.map((a) => (
                  <div key={a.id} className="flex items-center justify-between px-4 py-3 text-sm">
                    <span className="text-muted-foreground">{a.award_type.name.replace("Player of the Match", "POTM")}</span>
                    <Link href={`${base}/players/${a.player.id}`} className="font-medium hover:underline">{a.player.display_name}</Link>
                  </div>
                ))}
              </Card>
            ) : (
              <p className="text-sm text-muted-foreground">No awards recorded.</p>
            )}
          </section>

          <section>
            <SectionTitle>Played ({f.appearances.length})</SectionTitle>
            {f.appearances.length ? (
              <Card className="divide-y divide-border/40">
                {f.appearances.map((a) => (
                  <Link key={a.id} href={`${base}/players/${a.player.id}`} className="flex items-center justify-between px-4 py-3 text-sm hover:bg-accent/50">
                    <span className="font-medium">{a.player.display_name}</span>
                    <span className="text-xs text-muted-foreground">{a.position?.code ?? ""}{a.captain ? " · C" : ""}</span>
                  </Link>
                ))}
              </Card>
            ) : (
              <p className="text-sm text-muted-foreground">No appearances recorded.</p>
            )}
          </section>
        </div>
      )}

      {played && <MatchNotes fixtureId={f.id} canEdit={canEdit} />}

      {f.notes && (
        <section className="mt-8">
          <SectionTitle>Notes</SectionTitle>
          <p className="whitespace-pre-wrap text-sm text-muted-foreground">{f.notes}</p>
        </section>
      )}
    </div>
  );
}

function TeamName({ name, align }: { name: string; align: "left" | "right" }) {
  return (
    <span className={cn("min-w-0 flex-1 text-sm font-medium leading-tight", align === "right" ? "text-right" : "text-left")}>{name}</span>
  );
}

function GoalLine({ goal: g, base }: { goal: Schema["GoalRead"]; base: string }) {
  const label =
    g.event_type === "opp_own_goal" ? "Own goal (opposition)" : g.event_type === "own_goal" ? "Own goal" : null;
  return (
    <div className="flex items-center gap-3 px-4 py-3 text-sm">
      <span className="tnum w-8 shrink-0 text-xs text-muted-foreground">{g.minute != null ? `${g.minute}'` : ""}</span>
      <div className="min-w-0 flex-1">
        {g.scorer ? (
          <Link href={`${base}/players/${g.scorer.id}`} className={cn("font-medium hover:underline", g.event_type === "own_goal" && "text-rose-600 dark:text-rose-400")}>
            {g.scorer.display_name}
          </Link>
        ) : (
          <span className="font-medium">{label}</span>
        )}
        {label && g.scorer && <span className="ml-1.5 text-xs text-muted-foreground">({label})</span>}
        {g.assisted_by && <span className="ml-1.5 text-xs text-muted-foreground">assist {g.assisted_by.display_name}</span>}
      </div>
    </div>
  );
}
