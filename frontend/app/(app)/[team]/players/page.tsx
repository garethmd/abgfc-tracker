"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight, Plus, Users } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { PlayerForm } from "@/components/features/players/player-form";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function PlayersPage() {
  const { team, teamSeason, canEdit, base } = useTeam();
  const [adding, setAdding] = useState(false);
  const tsId = teamSeason?.id ?? 0;
  const squad = $api.useQuery("get", "/api/v1/team-seasons/{team_season_id}/squad", { params: { path: { team_season_id: tsId } } }, { enabled: !!teamSeason });
  const board = $api.useQuery("get", "/api/v1/team-seasons/{team_season_id}/stats/leaderboard", { params: { path: { team_season_id: tsId } } }, { enabled: !!teamSeason });

  const statsFor = (id: number) => board.data?.rows.find((r) => r.player.id === id);
  const active = (squad.data ?? []).filter((m) => !m.left_at);
  const departed = (squad.data ?? []).filter((m) => m.left_at);

  return (
    <>
      <PageHeader
        title="Squad"
        description={teamSeason ? `${team.name} · ${teamSeason.season.name} · ${active.length} players` : undefined}
        action={
          canEdit ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus className="size-4" /> Add
            </Button>
          ) : undefined
        }
      />

      {squad.isPending ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : squad.error ? (
        <ErrorState error={squad.error} onRetry={() => squad.refetch()} />
      ) : !squad.data.length ? (
        <EmptyState
          icon={Users}
          title="No players in this season's squad"
          description="Add the squad and they'll show on the dashboard from day one."
          action={canEdit ? <Button onClick={() => setAdding(true)}>Add a player</Button> : undefined}
        />
      ) : (
        <Card className="divide-y divide-border/40 overflow-hidden">
          {active.map((m) => {
            const s = statsFor(m.player.id);
            return (
              <Link key={m.id} href={`${base}/players/${m.player.id}`} className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-accent/50 active:bg-accent">
                <span className="tnum flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-sm font-semibold text-muted-foreground">
                  {m.squad_number ?? "–"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{m.player.display_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {m.primary_position?.name ?? "No position"}
                    {m.player.left_date && " · Left"}
                  </p>
                </div>
                {s && (
                  <div className="tnum flex gap-4 text-right text-sm">
                    <MiniStat label="Apps" value={s.appearances} />
                    <MiniStat label="G" value={s.goals} />
                    <MiniStat label="A" value={s.assists} />
                  </div>
                )}
                <ChevronRight className="size-4 text-muted-foreground" />
              </Link>
            );
          })}
        </Card>
      )}

      {departed.length > 0 && (
        <section className="mt-8">
          <SectionTitle>Left during the season</SectionTitle>
          <Card className="divide-y divide-border/40 overflow-hidden">
            {departed.map((m) => (
              <Link key={m.id} href={`${base}/players/${m.player.id}`} className="flex min-h-14 items-center justify-between px-4 py-3 text-sm hover:bg-accent/50">
                <span className="font-medium text-muted-foreground">{m.player.display_name}</span>
                <span className="text-xs text-muted-foreground">Left {m.left_at}{statsFor(m.player.id) ? ` · ${statsFor(m.player.id)!.appearances} apps` : ""}</span>
              </Link>
            ))}
          </Card>
        </section>
      )}

      <Sheet open={adding} onOpenChange={setAdding}>
        <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
          <SheetHeader className="text-left"><SheetTitle>Add player</SheetTitle></SheetHeader>
          <div className="mx-auto w-full max-w-lg px-4">
            <PlayerForm onSaved={() => setAdding(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex w-8 flex-col items-end">
      <span className="font-semibold">{value}</span>
      <span className="text-[10px] uppercase text-muted-foreground">{label}</span>
    </span>
  );
}
