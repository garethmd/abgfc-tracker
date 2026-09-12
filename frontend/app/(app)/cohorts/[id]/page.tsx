"use client";

import Link from "next/link";
import { use, useState } from "react";
import { ArrowRightLeft } from "lucide-react";
import { $api, type Schema } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { PlainShell } from "@/components/plain-shell";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Card, Stat } from "@/components/stat-card";
import { FormPips } from "@/components/features/dashboard/form-pips";
import { MovePlayerDialog } from "@/components/features/cohort/move-player-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export default function CohortOverviewPage({ params }: PageProps<"/cohorts/[id]">) {
  const { id } = use(params);
  const cohortId = Number(id);
  const { me } = useMe();
  const cohortAccess = me.cohorts.find((c) => c.cohort.id === cohortId);
  const canMove = cohortAccess ? (cohortAccess.role === "coach" || cohortAccess.role === "admin") &&
    (me.club_role !== null || me.roles.some((r) => r.scope_type === "cohort" && r.scope_id === cohortId)) : false;

  const seasons = $api.useQuery("get", "/api/v1/seasons");
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const effectiveSeason = seasonId ?? seasons.data?.[0]?.id ?? 0;
  const overview = $api.useQuery(
    "get",
    "/api/v1/cohorts/{cohort_id}/overview",
    { params: { path: { cohort_id: cohortId }, query: { season_id: effectiveSeason } } },
    { enabled: !!effectiveSeason },
  );
  const [moving, setMoving] = useState<{ player: Schema["PlayerSummary"]; from: number } | null>(null);
  const teamBySlug = (name: string) => me.teams.find((t) => t.team.name === name)?.team.slug;

  return (
    <PlainShell>
      <PageHeader
        title={cohortAccess?.cohort.name ?? "Age group"}
        description="Every team side by side, and how game time is shared across the group."
        action={
          seasons.data && seasons.data.length > 1 ? (
            <div className="flex rounded-lg bg-muted p-0.5 text-xs font-medium">
              {seasons.data.map((s) => (
                <button key={s.id} type="button" onClick={() => setSeasonId(s.id)} className={cn("h-8 rounded-md px-3 tnum", effectiveSeason === s.id ? "bg-background shadow-sm" : "text-muted-foreground")}>
                  {s.name}
                </button>
              ))}
            </div>
          ) : undefined
        }
      />

      {overview.isPending ? (
        <div className="space-y-4"><Skeleton className="h-40 rounded-xl" /><Skeleton className="h-96 rounded-xl" /></div>
      ) : overview.error ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : !overview.data.teams.length ? (
        <EmptyState title="No teams in this season" description="Teams appear here once they've started the season." />
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {overview.data.teams.map((t) => {
              const slug = teamBySlug(t.team_name);
              return (
                <Card key={t.team_season_id} className="p-4">
                  <div className="flex items-center justify-between">
                    {slug ? (
                      <Link href={`/${slug}`} className="font-semibold hover:underline">{t.team_name}</Link>
                    ) : (
                      <span className="font-semibold">{t.team_name}</span>
                    )}
                    <span className="tnum text-xs text-muted-foreground">{t.squad_size} in squad</span>
                  </div>
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    <Stat label="P" value={t.overall.played} />
                    <Stat label="W" value={t.overall.won} />
                    <Stat label="D" value={t.overall.drawn} />
                    <Stat label="L" value={t.overall.lost} />
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <FormPips form={t.form} size="sm" base={slug ? `/${slug}` : ""} />
                    <span className="tnum text-xs text-muted-foreground">{t.overall.goals_for}–{t.overall.goals_against}</span>
                  </div>
                </Card>
              );
            })}
          </section>

          <section className="mt-8">
            <SectionTitle>Players across the age group</SectionTitle>
            {!overview.data.players.length ? (
              <EmptyState title="No players yet" description="Squads appear here as teams add players." />
            ) : (
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/60 text-[11px] uppercase tracking-wider text-muted-foreground">
                        <th className="sticky left-0 z-10 bg-card py-3 pl-4 pr-2 text-left font-medium">Player</th>
                        <th className="px-3 py-3 text-left font-medium">Team</th>
                        <th className="px-3 py-3 text-right font-medium">Apps</th>
                        <th className="px-3 py-3 text-right font-medium">Goals</th>
                        <th className="px-3 py-3 text-right font-medium">Assists</th>
                        <th className="px-3 py-3 text-right font-medium" title="Once minutes are recorded">Mins</th>
                        {canMove && <th className="px-3 py-3" />}
                      </tr>
                    </thead>
                    <tbody className="tnum">
                      {overview.data.players.map((p) => {
                        const currentTeam = overview.data.teams.find((t) => t.team_name === p.teams[p.teams.length - 1]);
                        return (
                          <tr key={p.player.id} className="border-b border-border/40 last:border-0">
                            <td className="sticky left-0 z-10 bg-card py-2.5 pl-4 pr-2 font-medium">{p.player.display_name}</td>
                            <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">{p.teams.join(" → ")}</td>
                            <td className="px-3 py-2.5 text-right">{p.appearances}</td>
                            <td className="px-3 py-2.5 text-right">{p.goals}</td>
                            <td className="px-3 py-2.5 text-right">{p.assists}</td>
                            <td className="px-3 py-2.5 text-right text-muted-foreground">{p.minutes ?? "—"}</td>
                            {canMove && (
                              <td className="px-2 py-1 text-right">
                                <DropdownMenu>
                                  <DropdownMenuTrigger className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent" aria-label="Actions">
                                    <ArrowRightLeft className="size-4" />
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onSelect={() => currentTeam && setMoving({ player: p.player, from: currentTeam.team_season_id })} disabled={!currentTeam}>
                                      Move to another team…
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
            <p className="mt-2 text-xs text-muted-foreground">Minutes show once coaches record substitutions; appearances are the fairness measure until then.</p>
          </section>

          <MovePlayerDialog
            open={moving !== null}
            onOpenChange={(o) => !o && setMoving(null)}
            player={moving?.player ?? null}
            fromTeamSeasonId={moving?.from ?? null}
            teams={overview.data.teams}
          />
        </>
      )}
    </PlainShell>
  );
}
