"use client";

import { use, useState } from "react";
import { Pencil } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { PlayerForm } from "@/components/features/players/player-form";
import { Card, Stat } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ErrorState } from "@/components/error-state";

export default function PlayerPage({ params }: PageProps<"/players/[id]">) {
  const { id } = use(params);
  const playerId = Number(id);
  const { season } = useSeason();
  const [editing, setEditing] = useState(false);
  const seasonId = season?.id ?? 0;

  const player = $api.useQuery("get", "/api/v1/players/{player_id}", { params: { path: { player_id: playerId } } });
  const squad = $api.useQuery("get", "/api/v1/seasons/{season_id}/squad", { params: { path: { season_id: seasonId } } }, { enabled: !!season });
  const stats = $api.useQuery(
    "get",
    "/api/v1/players/{player_id}/stats",
    { params: { path: { player_id: playerId }, query: { season_id: seasonId } } },
    { enabled: !!season, retry: false },
  );

  if (player.isPending) return <Skeleton className="h-64 rounded-xl" />;
  if (player.error) return <ErrorState error={player.error} onRetry={() => player.refetch()} />;
  const p = player.data;
  const member = squad.data?.find((m) => m.player.id === playerId) ?? null;
  const s = stats.data;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {member?.squad_number != null && (
              <span className="tnum flex size-10 items-center justify-center rounded-xl bg-primary/10 text-base font-bold text-primary">{member.squad_number}</span>
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
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="size-4" /> Edit
          </Button>
        }
      />

      <SectionTitle>{season?.name ?? "Season"}</SectionTitle>
      {stats.isPending && season ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : s ? (
        <Card className="grid grid-cols-3 gap-y-6 p-5 md:grid-cols-6">
          <Stat label="Apps" value={s.appearances} />
          <Stat label="Goals" value={s.goals} />
          <Stat label="Assists" value={s.assists} />
          <Stat label="Per game" value={s.goals_per_game.toFixed(2)} />
          {s.awards.map((a) => (
            <Stat key={a.award_type_id} label={a.award_type_code === "coaches_potm" ? "Coaches' POTM" : a.award_type_code === "parents_potm" ? "Parents' POTM" : a.award_type_code} value={a.count} />
          ))}
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">Not in this season&apos;s squad and no appearances recorded.</p>
      )}
      {s?.own_goals ? <p className="mt-2 text-xs text-muted-foreground">{s.own_goals} own goal{s.own_goals > 1 ? "s" : ""}</p> : null}

      <p className="mt-8 text-xs text-muted-foreground">
        Player cards — photo, positions per match, minutes played and season-by-season history — are coming; the data model already supports them.
      </p>

      <Sheet open={editing} onOpenChange={setEditing}>
        <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
          <SheetHeader className="text-left"><SheetTitle>Edit {p.display_name}</SheetTitle></SheetHeader>
          <div className="mx-auto w-full max-w-lg px-4">
            <PlayerForm player={p} member={member} onSaved={() => { setEditing(false); player.refetch(); stats.refetch(); }} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
