"use client";

import Link from "next/link";
import { useState } from "react";
import { CalendarPlus, FileSpreadsheet } from "lucide-react";
import { seasonSpreadsheetUrl } from "@/lib/reports";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { RecordCard } from "@/components/features/dashboard/record-card";
import { HighlightTiles } from "@/components/features/dashboard/highlight-tiles";
import { Leaderboard } from "@/components/features/dashboard/leaderboard";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const { team, teamSeason, teamSeasons, isPending: seasonPending, canEdit, base } = useTeam();
  const [scope, setScope] = useState<"all" | "league">("all");
  const tsId = teamSeason?.id ?? 0;

  const summary = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/stats/summary",
    { params: { path: { team_season_id: tsId } } },
    { enabled: !!teamSeason },
  );
  const board = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/stats/leaderboard",
    { params: { path: { team_season_id: tsId }, query: scope === "league" ? { competition_type: "league" } : {} } },
    { enabled: !!teamSeason },
  );

  if (!seasonPending && !teamSeason) {
    return (
      <>
        <PageHeader title={team.name} />
        <EmptyState
          title="No season started"
          description={`${team.name} haven't started a season yet. Start one from Settings and the squad and fixtures follow.`}
          action={
            canEdit ? (
              <Button asChild>
                <Link href={`${base}/settings`}>Go to Settings</Link>
              </Button>
            ) : undefined
          }
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={teamSeason ? `${teamSeason.season.name} season` : <Skeleton className="h-8 w-40" />}
        description={`ABGFC ${team.name}${teamSeason?.age_group ? ` · ${teamSeason.age_group}` : ""}${teamSeasons.length > 1 && !teamSeason?.is_current ? " · past season" : ""}`}
        action={
          canEdit && teamSeason ? (
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm" title="Download the season as a spreadsheet">
                <a href={seasonSpreadsheetUrl(teamSeason.id)} download>
                  <FileSpreadsheet className="size-4" /> <span className="hidden sm:inline">Spreadsheet</span>
                </a>
              </Button>
              <Button asChild variant="outline" size="sm" className="hidden md:inline-flex">
                <Link href={`${base}/fixtures/new`}>
                  <CalendarPlus className="size-4" /> Add fixture
                </Link>
              </Button>
            </div>
          ) : undefined
        }
      />

      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section>
          {summary.isPending ? (
            <Skeleton className="h-80 rounded-xl" />
          ) : summary.error ? (
            <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
          ) : (
            <RecordCard summary={summary.data} base={base} />
          )}
        </section>

        <section>
          <SectionTitle>Highlights</SectionTitle>
          {summary.isPending ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-xl" />
              ))}
            </div>
          ) : summary.data ? (
            <HighlightTiles tiles={summary.data.highlights} base={base} />
          ) : null}
          {summary.data && summary.data.overall.played === 0 && (
            <p className="mt-3 text-sm text-muted-foreground">Highlights fill in after the first result is entered.</p>
          )}
        </section>
      </div>

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle className="mb-0">Squad</SectionTitle>
          <div className="flex rounded-lg bg-muted p-0.5 text-xs font-medium">
            {(["all", "league"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                className={cn("h-8 rounded-md px-3 transition-colors", scope === s ? "bg-background shadow-sm" : "text-muted-foreground")}
              >
                {s === "all" ? "All matches" : "League only"}
              </button>
            ))}
          </div>
        </div>
        {board.isPending ? (
          <Skeleton className="h-96 rounded-xl" />
        ) : board.error ? (
          <ErrorState error={board.error} onRetry={() => board.refetch()} />
        ) : (
          <Leaderboard board={board.data} base={base} />
        )}
      </section>
    </>
  );
}
