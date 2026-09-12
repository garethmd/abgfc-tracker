"use client";

import { use, useEffect } from "react";
import { CalendarDays, LayoutDashboard, Settings, Users } from "lucide-react";
import { rememberTeam, useMe } from "@/lib/me-context";
import { TeamProvider } from "@/lib/team-context";
import { AppShell } from "@/components/app-shell";
import { TeamSwitcher } from "@/components/team-switcher";
import { SeasonSwitcher } from "@/components/season-switcher";
import { PlainShell } from "@/components/plain-shell";
import { EmptyState } from "@/components/empty-state";

export default function TeamLayout({ children, params }: LayoutProps<"/[team]">) {
  const { team: slug } = use(params);
  const { teamBySlug } = useMe();
  const access = teamBySlug(slug);

  useEffect(() => {
    if (access) rememberTeam(slug);
  }, [access, slug]);

  if (!access) {
    return (
      <PlainShell>
        <EmptyState title="Team not found" description="Either it doesn't exist or you don't have access to it." />
      </PlainShell>
    );
  }

  const base = `/${slug}`;
  const nav = [
    { href: base, label: "Home", icon: LayoutDashboard, exact: true },
    { href: `${base}/fixtures`, label: "Fixtures", icon: CalendarDays },
    { href: `${base}/players`, label: "Squad", icon: Users },
    { href: `${base}/settings`, label: "Settings", icon: Settings },
  ];

  return (
    <TeamProvider access={access}>
      <AppShell
        nav={nav}
        brand={<TeamSwitcher current={{ name: access.team.name, slug, colour: access.team.colour }} />}
        aside={<SeasonSwitcher />}
        headerRight={<SeasonSwitcher compact />}
      >
        {children}
      </AppShell>
    </TeamProvider>
  );
}
