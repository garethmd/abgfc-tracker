"use client";

import Link from "next/link";
import { CalendarDays, FileDown, Plus, Radio } from "lucide-react";
import { matchdaySheetUrl } from "@/lib/reports";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { FixtureRow } from "@/components/features/fixtures/fixture-row";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function FixturesPage() {
  const { teamSeason, canEdit, base } = useTeam();
  const fixtures = $api.useQuery(
    "get",
    "/api/v1/fixtures",
    { params: { query: { team_season_id: teamSeason?.id ?? 0 } } },
    { enabled: !!teamSeason },
  );

  const live = (fixtures.data ?? []).find((f) => f.status === "live");
  const upcoming = (fixtures.data ?? []).filter((f) => f.status === "scheduled");
  const others = (fixtures.data ?? []).filter((f) => f.status !== "scheduled" && f.status !== "live").slice().reverse();
  const nextUp = live ?? upcoming[0];

  return (
    <>
      <PageHeader
        title="Fixtures"
        description={teamSeason ? `${teamSeason.season.name} · ${fixtures.data?.length ?? 0} fixtures` : undefined}
        action={
          canEdit ? (
            <Button asChild size="sm">
              <Link href={`${base}/fixtures/new`}>
                <Plus className="size-4" /> Add
              </Link>
            </Button>
          ) : undefined
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
            canEdit ? (
              <Button asChild>
                <Link href={`${base}/fixtures/new`}>Add a fixture</Link>
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-8">
          {nextUp && (
            <section>
              <SectionTitle>{nextUp.status === "live" ? "Live now" : "Next up"}</SectionTitle>
              <Card className="overflow-hidden">
                <FixtureRow fixture={nextUp} base={base} />
                {canEdit && teamSeason && nextUp.status === "live" && (
                  <div className="border-t border-border/60 p-3">
                    <Button asChild className="h-11 w-full">
                      <Link href={`${base}/fixtures/${nextUp.id}/live`}><Radio className="size-4" /> Continue live match</Link>
                    </Button>
                  </div>
                )}
                {canEdit && teamSeason && nextUp.status === "scheduled" && (
                  <div className="grid grid-cols-[1fr_1fr_auto] gap-2 border-t border-border/60 p-3">
                    <Button asChild className="h-11 w-full">
                      <Link href={`${base}/fixtures/${nextUp.id}/live`}><Radio className="size-4" /> Start match</Link>
                    </Button>
                    <Button asChild variant="outline" className="h-11 w-full">
                      <Link href={`${base}/fixtures/${nextUp.id}/entry`}>Enter result</Link>
                    </Button>
                    <Button asChild variant="outline" className="h-11" title="Download the matchday sheet (PDF)">
                      <a href={matchdaySheetUrl(teamSeason.id, nextUp.id)} download>
                        <FileDown className="size-4" /> Sheet
                      </a>
                    </Button>
                  </div>
                )}
              </Card>
              {upcoming.filter((f) => f.id !== nextUp.id).length > 0 && (
                <Card className="mt-3 divide-y divide-border/40 overflow-hidden">
                  {upcoming.filter((f) => f.id !== nextUp.id).map((f) => (
                    <FixtureRow key={f.id} fixture={f} base={base} />
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
                  <FixtureRow key={f.id} fixture={f} base={base} />
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
