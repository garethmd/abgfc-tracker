"use client";

import { PageHeader } from "@/components/page-header";
import { FixtureForm } from "@/components/features/fixtures/fixture-form";
import { useTeam } from "@/lib/team-context";

export default function NewFixturePage() {
  const { teamSeason, team } = useTeam();
  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Add fixture" description={teamSeason ? `${team.name} · ${teamSeason.season.name}` : undefined} />
      <FixtureForm />
    </div>
  );
}
