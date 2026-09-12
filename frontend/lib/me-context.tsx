"use client";

import { createContext, useContext } from "react";
import { $api, type Schema } from "@/lib/api/client";

export type Me = Schema["MeRead"];
export type TeamAccess = Schema["TeamAccess"];

interface MeContextValue {
  me: Me;
  isClubAdmin: boolean;
  /** Admin at any scope - unlocks the Coaches page. */
  isAdminSomewhere: boolean;
  /** Cohorts where the user has a cohort-level role (age-group coach). */
  cohortRoles: Schema["CohortAccess"][];
  teamBySlug: (slug: string) => TeamAccess | undefined;
  refetch: () => void;
}

const MeContext = createContext<MeContextValue | null>(null);

export function MeProvider({ me, refetch, children }: { me: Me; refetch: () => void; children: React.ReactNode }) {
  const value: MeContextValue = {
    me,
    isClubAdmin: me.club_role === "admin",
    isAdminSomewhere:
      me.club_role === "admin" || me.roles.some((r) => r.role === "admin"),
    cohortRoles: me.cohorts.filter((c) =>
      me.roles.some((r) => r.scope_type === "cohort" && r.scope_id === c.cohort.id) || me.club_role,
    ),
    teamBySlug: (slug) => me.teams.find((t) => t.team.slug === slug),
    refetch,
  };
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>;
}

export function useMe(): MeContextValue {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe must be used inside MeProvider");
  return ctx;
}

export const LAST_TEAM_KEY = "abgfc.lastTeam";

export function rememberTeam(slug: string) {
  try {
    window.localStorage.setItem(LAST_TEAM_KEY, slug);
  } catch {
    /* ignore */
  }
}

export function lastTeam(): string | null {
  try {
    return window.localStorage.getItem(LAST_TEAM_KEY);
  } catch {
    return null;
  }
}

/** Where a user should land: their only team, their last team, else the picker. */
export function homeFor(me: Me): string {
  if (me.teams.length === 1) return `/${me.teams[0].team.slug}`;
  const last = typeof window !== "undefined" ? lastTeam() : null;
  if (last && me.teams.some((t) => t.team.slug === last)) return `/${last}`;
  if (me.teams.length === 0) return me.club_role === "admin" ? "/admin" : "/no-access";
  return "/teams";
}

/** Convenience: can the user hit the write endpoints for this team? */
export function canEdit(role: Schema["UserRole"]): boolean {
  return role === "coach" || role === "admin";
}

/** Keeps the $api import used for type inference in one place. */
export const useMeQuery = () => $api.useQuery("get", "/api/v1/auth/me", undefined, { retry: false, staleTime: 60_000 });
