"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useMe } from "@/lib/me-context";
import { PlainShell } from "@/components/plain-shell";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/stat-card";

export default function TeamsPage() {
  const { me } = useMe();
  return (
    <PlainShell>
      <PageHeader title="Your teams" description="Pick a team to coach." />
      <Card className="divide-y divide-border/40 overflow-hidden">
        {me.teams.map((t) => (
          <Link key={t.team.id} href={`/${t.team.slug}`} className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-accent/50">
            <span className="size-3 rounded-full" style={{ background: t.team.colour ?? "currentColor" }} />
            <span className="flex-1 font-medium">{t.team.name}</span>
            <span className="text-xs capitalize text-muted-foreground">{t.role}</span>
            <ChevronRight className="size-4 text-muted-foreground" />
          </Link>
        ))}
      </Card>
    </PlainShell>
  );
}
