"use client";

import { useTeam } from "@/lib/team-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ThemeToggle } from "@/components/theme-toggle";
import { AccountCard } from "@/components/account-card";
import { SeasonsManager } from "@/components/features/settings/seasons-manager";
import { AwardTypesManager } from "@/components/features/settings/award-types-manager";
import { CompetitionsManager, TeamsManager } from "@/components/features/settings/lookup-managers";

export default function SettingsPage() {
  const { team } = useTeam();
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Settings" description={`ABGFC ${team.name}`} />

      <Tabs defaultValue="seasons">
        <TabsList className="mb-4 h-11 w-full">
          <TabsTrigger value="seasons" className="flex-1">Seasons</TabsTrigger>
          <TabsTrigger value="awards" className="flex-1">Awards</TabsTrigger>
          <TabsTrigger value="competitions" className="flex-1">Leagues</TabsTrigger>
          <TabsTrigger value="teams" className="flex-1">Opposition</TabsTrigger>
        </TabsList>
        <TabsContent value="seasons"><SeasonsManager /></TabsContent>
        <TabsContent value="awards"><AwardTypesManager /></TabsContent>
        <TabsContent value="competitions"><CompetitionsManager /></TabsContent>
        <TabsContent value="teams"><TeamsManager /></TabsContent>
      </Tabs>

      <section className="mt-10">
        <SectionTitle>Appearance</SectionTitle>
        <ThemeToggle />
      </section>

      <section className="mt-10">
        <SectionTitle>Account</SectionTitle>
        <AccountCard />
      </section>
    </div>
  );
}
