"use client";

import Link from "next/link";
import { use } from "react";
import { $api } from "@/lib/api/client";
import { pickedIds } from "@/components/features/fixtures/squad-selection";
import { useTeam } from "@/lib/team-context";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { LineUp, LiveMatch } from "@/components/features/fixtures/live-match";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function LiveMatchPage({ params }: PageProps<"/[team]/fixtures/[id]/live">) {
  const { id } = use(params);
  const fixtureId = Number(id);
  const { team, base, canEdit } = useTeam();
  const fixture = $api.useQuery(
    "get",
    "/api/v1/fixtures/{fixture_id}",
    { params: { path: { fixture_id: fixtureId } } },
    // Someone else may be tapping goals in on another phone: keep the score fresh.
    { refetchInterval: (q) => (q.state.data?.status === "live" ? 15_000 : false) },
  );
  const teamSeasonId = fixture.data?.team_season_id ?? 0;
  const squad = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/squad",
    { params: { path: { team_season_id: teamSeasonId } } },
    { enabled: !!fixture.data },
  );

  // The players marked available beforehand, if any, are the default line-up.
  const selection = $api.useQuery(
    "get",
    "/api/v1/fixtures/{fixture_id}/selection",
    { params: { path: { fixture_id: fixtureId } } },
    { enabled: fixture.data?.status === "scheduled" },
  );

  const error = fixture.error ?? squad.error;
  if (error) return <ErrorState error={error} onRetry={() => { fixture.refetch(); squad.refetch(); }} />;
  const needSelection = fixture.data?.status === "scheduled" && selection.data === undefined && !selection.error;
  if (!fixture.data || !squad.data || needSelection) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  const f = fixture.data;
  const description = `v ${f.opposition.name} · ${formatDate(f.kickoff_at)}`;

  if (!canEdit || (f.status !== "scheduled" && f.status !== "live")) {
    return (
      <div className="mx-auto max-w-lg">
        <PageHeader title="Live match" description={description} />
        <EmptyState
          title={f.status === "played" ? "This match has been played" : "Nothing to record"}
          description={!canEdit ? "Only coaches can record a match live." : "Only a scheduled fixture can be started."}
          action={<Button asChild variant="outline"><Link href={`${base}/fixtures/${f.id}`}>Back to fixture</Link></Button>}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      {f.status === "scheduled" ? (
        <>
          <PageHeader title="Start match" description={description} />
          <LineUp
            fixture={f}
            squad={squad.data}
            preselect={pickedIds(selection.data)}
          />
        </>
      ) : (
        <>
          <PageHeader title="Live match" description={description} className="mb-4" />
          <LiveMatch fixture={f} squad={squad.data} teamName={team.name} base={base} />
        </>
      )}
    </div>
  );
}
