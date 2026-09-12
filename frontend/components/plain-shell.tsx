"use client";

import { AppShell } from "@/components/app-shell";
import { TeamSwitcher } from "@/components/team-switcher";

/** Shell for pages outside a team (admin, cohort overview, team picker). */
export function PlainShell({ children }: { children: React.ReactNode }) {
  return (
    <AppShell nav={[]} brand={<TeamSwitcher />}>
      {children}
    </AppShell>
  );
}
