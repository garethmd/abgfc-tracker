"use client";

import { useMe } from "@/lib/me-context";
import { PlainShell } from "@/components/plain-shell";
import { PageHeader, SectionTitle } from "@/components/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UsersManager } from "@/components/features/admin/users-manager";
import { StructureManager } from "@/components/features/admin/structure-manager";
import { AccountCard } from "@/components/account-card";
import { EmptyState } from "@/components/empty-state";

export default function AdminPage() {
  const { isAdminSomewhere } = useMe();
  return (
    <PlainShell>
      <div className="mx-auto max-w-2xl">
        <PageHeader title="Club admin" description="Coaches, age groups and teams." />
        {!isAdminSomewhere ? (
          <EmptyState title="Admins only" description="Ask your club admin if you need to manage coaches." />
        ) : (
          <Tabs defaultValue="coaches">
            <TabsList className="mb-4 h-11 w-full">
              <TabsTrigger value="coaches" className="flex-1">Coaches</TabsTrigger>
              <TabsTrigger value="structure" className="flex-1">Age groups & teams</TabsTrigger>
            </TabsList>
            <TabsContent value="coaches"><UsersManager /></TabsContent>
            <TabsContent value="structure"><StructureManager /></TabsContent>
          </Tabs>
        )}
        <section className="mt-10">
          <SectionTitle>Account</SectionTitle>
          <AccountCard />
        </section>
      </div>
    </PlainShell>
  );
}
