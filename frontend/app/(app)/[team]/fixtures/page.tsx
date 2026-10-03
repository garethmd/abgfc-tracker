"use client";

import Link from "next/link";
import { useState } from "react";
import { CalendarDays, ClipboardList, MessageCircle, Plus, Radio, Upload } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { FixtureRow } from "@/components/features/fixtures/fixture-row";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MessageSheet } from "@/components/features/fixtures/message-sheet";

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
  // A called-off match is not a result: it keeps the date it was due, so it gets its own
  // section rather than sitting under Results looking like a game with no score.
  const postponed = (fixtures.data ?? []).filter((f) => f.status === "postponed");
  const others = (fixtures.data ?? [])
    .filter((f) => !["scheduled", "live", "postponed"].includes(f.status))
    .slice()
    .reverse();
  const nextUp = live ?? upcoming[0];
  const later = upcoming.filter((f) => f.id !== nextUp?.id);
  // Which fixture's parents' message is open, if any.
  const [message, setMessage] = useState<number | null>(null);

  return (
    <>
      <PageHeader
        title="Fixtures"
        description={teamSeason ? `${teamSeason.season.name} · ${fixtures.data?.length ?? 0} fixtures` : undefined}
        action={
          canEdit ? (
            <div className="flex gap-2">
              <Button asChild size="sm" variant="outline" title="Import fixtures from FA Full-Time">
                <Link href={`${base}/fixtures/import`}>
                  <Upload className="size-4" /> Import
                </Link>
              </Button>
              <Button asChild size="sm">
                <Link href={`${base}/fixtures/new`}>
                  <Plus className="size-4" /> Add
                </Link>
              </Button>
            </div>
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
                  <div className="space-y-2 border-t border-border/60 p-3">
                    <div className="grid grid-cols-2 gap-2">
                      <Button asChild className="h-11 w-full">
                        <Link href={`${base}/fixtures/${nextUp.id}/live`}><Radio className="size-4" /> Start match</Link>
                      </Button>
                      <Button asChild variant="outline" className="h-11 w-full">
                        <Link href={`${base}/fixtures/${nextUp.id}/entry`}>Enter result</Link>
                      </Button>
                    </div>
                    <div className={nextUp.availability ? "grid grid-cols-2 gap-2" : ""}>
                      <Button asChild variant="outline" className="h-11 w-full">
                        <Link href={`${base}/fixtures/${nextUp.id}/selection`}>
                          <ClipboardList className="size-4" /> {nextUp.availability ? "Edit availability" : "Availability"}
                        </Link>
                      </Button>
                      {nextUp.availability && (
                        <Button type="button" variant="outline" className="h-11 w-full" onClick={() => setMessage(nextUp.id)}>
                          <MessageCircle className="size-4" /> Message parents
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </Card>
              {later.length > 0 && (
                <Card className="mt-3 divide-y divide-border/40 overflow-hidden">
                  {later.map((f) => (
                    <FixtureRow key={f.id} fixture={f} base={base} />
                  ))}
                </Card>
              )}
              {canEdit && message !== null && (
                <MessageSheet fixtureId={message} open onOpenChange={(o) => { if (!o) setMessage(null); }} />
              )}
            </section>
          )}

          {postponed.length > 0 && (
            <section>
              <SectionTitle>Postponed</SectionTitle>
              <Card className="divide-y divide-border/40 overflow-hidden">
                {postponed.map((f) => (
                  <FixtureRow key={f.id} fixture={f} base={base} />
                ))}
              </Card>
              <p className="mt-2 text-xs text-muted-foreground">
                Still on record for the day they were due, counting towards nothing.
              </p>
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
