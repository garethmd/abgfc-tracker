"use client";

import { use } from "react";
import { $api } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { ResultEntry } from "@/components/features/fixtures/result-entry";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";

export default function ResultEntryPage({ params }: PageProps<"/fixtures/[id]/entry">) {
  const { id } = use(params);
  const fixtureId = Number(id);
  const fixture = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}", { params: { path: { fixture_id: fixtureId } } });
  const seasonId = fixture.data?.season_id ?? 0;
  const squad = $api.useQuery(
    "get",
    "/api/v1/seasons/{season_id}/squad",
    { params: { path: { season_id: seasonId } } },
    { enabled: !!fixture.data },
  );
  const awardTypes = $api.useQuery("get", "/api/v1/award-types");

  const error = fixture.error ?? squad.error ?? awardTypes.error;
  if (error) return <ErrorState error={error} onRetry={() => { fixture.refetch(); squad.refetch(); awardTypes.refetch(); }} />;
  if (!fixture.data || !squad.data || !awardTypes.data) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  const f = fixture.data;

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader
        title={f.status === "played" ? "Edit result" : "Enter result"}
        description={`v ${f.opposition.name} · ${formatDate(f.kickoff_at)}`}
      />
      <ResultEntry fixture={f} squad={squad.data} awardTypes={awardTypes.data} />
    </div>
  );
}
