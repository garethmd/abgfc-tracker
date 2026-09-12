"use client";

import { use } from "react";
import { $api } from "@/lib/api/client";
import { PageHeader } from "@/components/page-header";
import { FixtureForm } from "@/components/features/fixtures/fixture-form";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";

export default function EditFixturePage({ params }: PageProps<"/fixtures/[id]/edit">) {
  const { id } = use(params);
  const fixture = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}", { params: { path: { fixture_id: Number(id) } } });

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Edit fixture" />
      {fixture.isPending ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : fixture.error ? (
        <ErrorState error={fixture.error} onRetry={() => fixture.refetch()} />
      ) : (
        <FixtureForm fixture={fixture.data} />
      )}
    </div>
  );
}
