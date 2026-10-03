"use client";

import { use, useState } from "react";
import { Pencil } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { PlayerForm } from "@/components/features/players/player-form";
import { PhotoPicker } from "@/components/features/players/photo-picker";
import { PlayerAvatar } from "@/components/player-avatar";
import { Card, Stat } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";

export default function PlayerPage({ params }: PageProps<"/[team]/players/[id]">) {
  const { id } = use(params);
  const playerId = Number(id);
  const { teamSeason, canEdit } = useTeam();
  const [editing, setEditing] = useState(false);
  const tsId = teamSeason?.id ?? 0;

  const player = $api.useQuery("get", "/api/v1/players/{player_id}", { params: { path: { player_id: playerId } } });
  const squad = $api.useQuery("get", "/api/v1/team-seasons/{team_season_id}/squad", { params: { path: { team_season_id: tsId } } }, { enabled: !!teamSeason });
  const memberships = $api.useQuery("get", "/api/v1/players/{player_id}/memberships", { params: { path: { player_id: playerId } } });
  // The season across every team in the age group: one child, one set of totals, with the
  // split by team underneath. A guest spell for another team is part of their season.
  const season = $api.useQuery(
    "get",
    "/api/v1/players/{player_id}/season-stats",
    { params: { path: { player_id: playerId }, query: { season_id: teamSeason?.season.id ?? 0 } } },
    { enabled: !!teamSeason },
  );

  if (player.isPending) return <Skeleton className="h-64 rounded-xl" />;
  if (player.error) return <ErrorState error={player.error} onRetry={() => player.refetch()} />;
  const p = player.data;
  const member = squad.data?.find((m) => m.player.id === playerId) ?? null;
  const totals = season.data?.totals;
  const byTeam = season.data?.teams ?? [];
  // Numbers belong to the player across the age group, so any row has the right one.
  const number = member?.squad_number ?? byTeam.find((t) => t.squad_number != null)?.squad_number;
  // Spells in other seasons; this season's teams are in the breakdown below.
  const pastSeasons = (memberships.data ?? []).filter((m) => m.season_name !== teamSeason?.season.name);

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <PlayerAvatar playerId={p.id} name={p.display_name} photoKey={p.photo_key} size={48} />
            {/* Their own number, which they keep when guesting for another team. */}
            {number != null && (
              <span className="tnum flex size-9 items-center justify-center rounded-xl bg-primary/10 text-sm font-bold text-primary">{number}</span>
            )}
            {p.display_name}
          </span>
        }
        description={
          [p.first_name !== p.display_name || p.last_name ? `${p.first_name} ${p.last_name ?? ""}`.trim() : null,
           member?.primary_position?.name, p.left_date ? `Left ${p.left_date}` : null]
            .filter(Boolean).join(" · ") || undefined
        }
        action={
          canEdit ? (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="size-4" /> Edit
            </Button>
          ) : undefined
        }
      />

      {canEdit && (
        <div className="mb-8">
          <PhotoPicker player={p} onChanged={() => player.refetch()} />
        </div>
      )}

      <SectionTitle>{teamSeason ? `${teamSeason.season.name} season` : "Season"}</SectionTitle>
      {season.isPending && teamSeason ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : totals && byTeam.length > 0 ? (
        <>
          <Card className="grid grid-cols-3 gap-y-6 p-5 md:grid-cols-6">
            <Stat label="Apps" value={totals.appearances} />
            <Stat label="Goals" value={totals.goals} />
            <Stat label="Assists" value={totals.assists} />
            <Stat label="Per game" value={totals.goals_per_game.toFixed(2)} />
            {totals.awards.map((a) => (
              <Stat key={a.award_type_id} label={awardLabel(a.award_type_code)} value={a.count} />
            ))}
          </Card>
          {totals.own_goals > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">{totals.own_goals} own goal{totals.own_goals > 1 ? "s" : ""}</p>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            {byTeam.length > 1
              ? `Every appearance this season, across ${byTeam.length} teams in the age group.`
              : `Every appearance for ${byTeam[0].team_name} this season.`}
          </p>

          <SectionTitle className="mt-8">By team</SectionTitle>
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="py-3 pl-4 pr-2 text-left font-medium">Team</th>
                  <th className="px-3 py-3 text-right font-medium">Apps</th>
                  <th className="px-3 py-3 text-right font-medium">Goals</th>
                  <th className="px-3 py-3 pr-4 text-right font-medium">Assists</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {byTeam.map((t) => (
                  <tr key={t.team_season_id} className="border-b border-border/40 last:border-0">
                    <td className="py-3 pl-4 pr-2">
                      <span className="font-medium">{t.team_name}</span>
                      {t.is_guest && (
                        <span className="ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground ring-1 ring-border/60">
                          guest
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right">{t.appearances}</td>
                    <td className={cn("px-3 py-3 text-right", t.goals > 0 && "font-semibold")}>{t.goals}</td>
                    <td className={cn("px-3 py-3 pr-4 text-right", t.assists > 0 && "font-semibold")}>{t.assists}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">No appearances recorded this season.</p>
      )}

      {pastSeasons.length > 0 && (
        <>
          <SectionTitle className="mt-8">Earlier seasons</SectionTitle>
          <Card className="divide-y divide-border/40">
            {pastSeasons.map((m) => (
              <div key={m.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="font-medium">{m.team_name} <span className="tnum text-muted-foreground">{m.season_name}</span>{m.age_group ? <span className="ml-1 text-xs text-muted-foreground">{m.age_group}</span> : null}</span>
                <span className="text-xs text-muted-foreground">
                  {m.left_at ? `left ${m.left_at}` : "current"}{m.squad_number != null ? ` · #${m.squad_number}` : ""}
                </span>
              </div>
            ))}
          </Card>
        </>
      )}

      <p className="mt-8 text-xs text-muted-foreground">
        Positions per match and minutes played are coming; the data model already supports them.
      </p>

      <Sheet open={editing} onOpenChange={setEditing}>
        <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
          <SheetHeader className="text-left"><SheetTitle>Edit {p.display_name}</SheetTitle></SheetHeader>
          <div className="mx-auto w-full max-w-lg px-4">
            <PlayerForm player={p} member={member} onSaved={() => { setEditing(false); player.refetch(); season.refetch(); }} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function awardLabel(code: string) {
  return code === "coaches_potm" ? "Coaches' POTM" : code === "parents_potm" ? "Parents' POTM" : code;
}
