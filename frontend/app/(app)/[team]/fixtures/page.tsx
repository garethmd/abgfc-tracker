"use client";

import Link from "next/link";
import { useState } from "react";
import { CalendarDays, ClipboardList, FileDown, MessageCircle, Plus, Radio, Upload } from "lucide-react";
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
import { MessageSheet } from "@/components/features/fixtures/message-sheet";
import { availabilitySummary } from "@/components/features/fixtures/squad-selection";

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
                {nextUp.status === "scheduled" && (nextUp.availability || canEdit) && (
                  <div className="flex items-center gap-2 border-t border-border/60 px-4 py-2.5 text-xs text-muted-foreground">
                    <ClipboardList className="size-3.5 shrink-0" />
                    <span className="tnum">{nextUp.availability ? availabilitySummary(nextUp.availability) : "Availability not recorded yet"}</span>
                  </div>
                )}
                {canEdit && teamSeason && nextUp.status === "scheduled" && (
                  <div className="space-y-2 border-t border-border/60 p-3">
                    <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
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
                    <div key={f.id}>
                      <FixtureRow fixture={f} base={base} />
                      {(f.availability || canEdit) && (
                        <div className="flex min-h-10 items-center gap-2 border-t border-border/40 bg-muted/30 px-4 py-1.5 text-xs text-muted-foreground">
                          <ClipboardList className="size-3.5 shrink-0" />
                          <span className="tnum min-w-0 flex-1 truncate">
                            {f.availability ? availabilitySummary(f.availability) : "Availability not recorded"}
                          </span>
                          {canEdit && f.availability && (
                            <button type="button" className="flex h-8 items-center gap-1 rounded-md px-2 font-medium text-primary hover:bg-accent" onClick={() => setMessage(f.id)}>
                              <MessageCircle className="size-3.5" /> Message
                            </button>
                          )}
                          {canEdit && (
                            <Link href={`${base}/fixtures/${f.id}/selection`} className="flex h-8 items-center rounded-md px-2 font-medium text-primary hover:bg-accent">
                              {f.availability ? "Edit" : "Availability"}
                            </Link>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </Card>
              )}
              {canEdit && message !== null && (
                <MessageSheet fixtureId={message} open onOpenChange={(o) => { if (!o) setMessage(null); }} />
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
