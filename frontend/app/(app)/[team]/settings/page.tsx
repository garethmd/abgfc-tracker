"use client";

import { useTeam } from "@/lib/team-context";
import { useMe } from "@/lib/me-context";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ThemeToggle } from "@/components/theme-toggle";
import { AccountCard } from "@/components/account-card";
import { PasskeysCard } from "@/components/passkeys-card";
import { SeasonsManager } from "@/components/features/settings/seasons-manager";
import { AwardTypesManager } from "@/components/features/settings/award-types-manager";
import { CompetitionsManager } from "@/components/features/settings/lookup-managers";
import { ParentsManager } from "@/components/features/settings/parents-manager";

export default function SettingsPage() {
  const { team, canEdit } = useTeam();
  const { me } = useMe();
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Settings" description={`ABGFC ${team.name}`} />

      <Tabs defaultValue="seasons">
        <TabsList className="mb-4 h-11 w-full">
          <TabsTrigger value="seasons" className="flex-1">Seasons</TabsTrigger>
          <TabsTrigger value="awards" className="flex-1">Awards</TabsTrigger>
          <TabsTrigger value="competitions" className="flex-1">Leagues</TabsTrigger>
          {canEdit && <TabsTrigger value="parents" className="flex-1">Parents</TabsTrigger>}
        </TabsList>
        <TabsContent value="seasons"><SeasonsManager /></TabsContent>
        <TabsContent value="awards"><AwardTypesManager /></TabsContent>
        <TabsContent value="competitions"><CompetitionsManager /></TabsContent>
        {canEdit && <TabsContent value="parents"><ParentsManager /></TabsContent>}
      </Tabs>

      <section className="mt-10">
        <SectionTitle>Appearance</SectionTitle>
        <ThemeToggle />
      </section>

      {!me.has_password && (
        <section className="mt-10">
          <SectionTitle>Signing in</SectionTitle>
          <PasskeysCard />
        </section>
      )}

      <section className="mt-10">
        <SectionTitle>Account</SectionTitle>
        <AccountCard />
      </section>
    </div>
  );
}
