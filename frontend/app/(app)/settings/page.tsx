"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { $api, fetchClient } from "@/lib/api/client";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/stat-card";
import { ThemeToggle } from "@/components/theme-toggle";
import { SeasonsManager } from "@/components/features/settings/seasons-manager";
import { CompetitionsManager, TeamsManager } from "@/components/features/settings/lookup-managers";

export default function SettingsPage() {
  const router = useRouter();
  const me = $api.useQuery("get", "/api/v1/auth/me");

  async function logout() {
    await fetchClient.POST("/api/v1/auth/logout");
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Settings" />

      <Tabs defaultValue="seasons">
        <TabsList className="mb-4 h-11 w-full">
          <TabsTrigger value="seasons" className="flex-1">Seasons</TabsTrigger>
          <TabsTrigger value="competitions" className="flex-1">Competitions</TabsTrigger>
          <TabsTrigger value="teams" className="flex-1">Teams</TabsTrigger>
        </TabsList>
        <TabsContent value="seasons"><SeasonsManager /></TabsContent>
        <TabsContent value="competitions"><CompetitionsManager /></TabsContent>
        <TabsContent value="teams"><TeamsManager /></TabsContent>
      </Tabs>

      <section className="mt-10">
        <SectionTitle>Appearance</SectionTitle>
        <ThemeToggle />
      </section>

      <section className="mt-10">
        <SectionTitle>Account</SectionTitle>
        <Card className="flex items-center justify-between p-4">
          <div className="text-sm">
            <p className="font-medium">{me.data?.username ?? "…"}</p>
            <p className="text-xs capitalize text-muted-foreground">{me.data?.role}</p>
          </div>
          <Button variant="outline" size="sm" onClick={logout}><LogOut className="size-4" /> Sign out</Button>
        </Card>
      </section>
    </div>
  );
}
