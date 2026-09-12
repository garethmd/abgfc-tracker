"use client";

import { PageHeader } from "@/components/page-header";
import { FixtureForm } from "@/components/features/fixtures/fixture-form";
import { useSeason } from "@/lib/season-context";

export default function NewFixturePage() {
  const { season } = useSeason();
  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Add fixture" description={season ? `${season.name} season` : undefined} />
      <FixtureForm />
    </div>
  );
}
