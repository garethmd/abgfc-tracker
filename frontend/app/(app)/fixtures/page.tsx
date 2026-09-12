"use client";

import Link from "next/link";
import { CalendarDays, Plus } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { FixtureRow } from "@/components/features/fixtures/fixture-row";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function FixturesPage() {
  const { season } = useSeason();
  const fixtures = $api.useQuery(
    "get",
    "/api/v1/fixtures",
    { params: { query: { season_id: season?.id ?? 0 } } },
    { enabled: !!season },
  );

  const upcoming = (fixtures.data ?? []).filter((f) => f.status === "scheduled");
  const others = (fixtures.data ?? []).filter((f) => f.status !== "scheduled").slice().reverse();
  const nextUp = upcoming[0];

  return (
    <>
      <PageHeader
        title="Fixtures"
        description={season ? `${season.name} · ${fixtures.data?.length ?? 0} fixtures` : undefined}
        action={
          <Button asChild size="sm">
            <Link href="/fixtures/new">
              <Plus className="size-4" /> Add
            </Link>
          </Button>
        }
      />

      {fixtures.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : fixtures.error ? (
        <ErrorState error={fixtures.error} onRetry={() => fixtures.refetch()} />
      ) : !fixtures.data.length ? (
        <EmptyState
          icon={CalendarDays}
          title="No fixtures yet"
          description="Add the first fixture and enter the result after the game."
          action={
            <Button asChild>
              <Link href="/fixtures/new">Add a fixture</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-8">
          {nextUp && (
            <section>
              <SectionTitle>Next up</SectionTitle>
              <Card className="overflow-hidden">
                <FixtureRow fixture={nextUp} />
                <div className="border-t border-border/60 p-3">
                  <Button asChild className="h-11 w-full">
                    <Link href={`/fixtures/${nextUp.id}/entry`}>Enter result</Link>
                  </Button>
                </div>
              </Card>
              {upcoming.length > 1 && (
                <Card className="mt-3 divide-y divide-border/40 overflow-hidden">
                  {upcoming.slice(1).map((f) => (
                    <FixtureRow key={f.id} fixture={f} />
                  ))}
                </Card>
              )}
            </section>
          )}

          <section>
            <SectionTitle>Results</SectionTitle>
            {others.length ? (
              <Card className="divide-y divide-border/40 overflow-hidden">
                {others.map((f) => (
                  <FixtureRow key={f.id} fixture={f} />
                ))}
              </Card>
            ) : (
              <EmptyState title="No results yet" description="Results appear here once a match has been entered." />
            )}
          </section>
        </div>
      )}
    </>
  );
}
