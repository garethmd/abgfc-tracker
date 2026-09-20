"use client";

import Link from "next/link";
import { use } from "react";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { SquadSelection } from "@/components/features/fixtures/squad-selection";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function SquadSelectionPage({ params }: PageProps<"/[team]/fixtures/[id]/selection">) {
  const { id } = use(params);
  const fixtureId = Number(id);
  const { base, canEdit } = useTeam();
  const fixture = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}", { params: { path: { fixture_id: fixtureId } } });
  const selection = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}/selection", { params: { path: { fixture_id: fixtureId } } });
  const teamSeasonId = fixture.data?.team_season_id ?? 0;
  const squad = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/squad",
    { params: { path: { team_season_id: teamSeasonId } } },
    { enabled: !!fixture.data },
  );
  const teamSeason = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}",
    { params: { path: { team_season_id: teamSeasonId } } },
    { enabled: !!fixture.data },
  );

  const error = fixture.error ?? squad.error ?? selection.error ?? teamSeason.error;
  if (error) return <ErrorState error={error} onRetry={() => { fixture.refetch(); squad.refetch(); selection.refetch(); teamSeason.refetch(); }} />;
  if (!fixture.data || !squad.data || selection.data === undefined || !teamSeason.data) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    );
  }
  const f = fixture.data;
  const description = `v ${f.opposition.name} · ${formatDate(f.kickoff_at)}`;
  const editable = f.status === "scheduled" || f.status === "postponed";

  if (!canEdit || !editable) {
    return (
      <div className="mx-auto max-w-lg">
        <PageHeader title="Availability" description={description} />
        <EmptyState
          title={!canEdit ? "Coaches only" : "This match has been played"}
          description={!canEdit ? "Only coaches can record availability." : "Availability is only recorded before the match."}
          action={<Button asChild variant="outline"><Link href={`${base}/fixtures/${f.id}`}>Back to fixture</Link></Button>}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Availability" description={description} />
      <SquadSelection
        fixture={f}
        squad={squad.data}
        selection={selection.data}
        leadMinutes={teamSeason.data.arrival_lead_minutes}
        base={base}
      />
    </div>
  );
}
