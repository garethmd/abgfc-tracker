"use client";

import Link from "next/link";
import { ChevronRight, Shield } from "lucide-react";
import { $api } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export default function OppositionListPage() {
  const { base } = useTeam();
  const teams = $api.useQuery("get", "/api/v1/teams");

  return (
    <>
      <PageHeader title="Opposition" description="Every team we've played or are due to play." />
      {teams.isPending ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : teams.error ? (
        <ErrorState error={teams.error} onRetry={() => teams.refetch()} />
      ) : !teams.data.length ? (
        <EmptyState icon={Shield} title="No opposition yet" description="Teams appear here as fixtures are added." />
      ) : (
        <Card className="divide-y divide-border/40 overflow-hidden">
          {teams.data.map((t) => (
            <Link key={t.id} href={`${base}/opposition/${t.id}`} className="flex min-h-14 items-center gap-3 px-4 py-3 hover:bg-accent/50 active:bg-accent">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{t.name}</span>
                {(t.short_name || t.colours) && (
                  <span className="block truncate text-xs text-muted-foreground">{[t.short_name, t.colours].filter(Boolean).join(" · ")}</span>
                )}
              </span>
              {t.club_team_id && <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">ABGFC</span>}
              <ChevronRight className="size-4 text-muted-foreground" />
            </Link>
          ))}
        </Card>
      )}
    </>
  );
}
