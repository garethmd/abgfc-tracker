"use client";

import { createContext, useContext, useMemo, useSyncExternalStore } from "react";
import { $api, type Schema } from "@/lib/api/client";
import { canEdit, type TeamAccess } from "@/lib/me-context";

type TeamSeason = Schema["TeamSeasonRead"];

interface TeamContextValue {
  access: TeamAccess;
  team: Schema["ClubTeamRead"];
  /** The team-season being viewed (defaults to the current one). */
  teamSeason: TeamSeason | null;
  teamSeasons: TeamSeason[];
  setTeamSeasonId: (id: number) => void;
  canEdit: boolean;
  isPending: boolean;
  /** Prefix for links: "/blues" */
  base: string;
}

const TeamContext = createContext<TeamContextValue | null>(null);

// Selected season per team, persisted; server snapshot is always null.
const listeners = new Set<() => void>();
const key = (teamId: number) => `abgfc.teamSeason.${teamId}`;
function readStored(teamId: number): number | null {
  try {
    const v = window.localStorage.getItem(key(teamId));
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}
function writeStored(teamId: number, id: number) {
  try {
    window.localStorage.setItem(key(teamId), String(id));
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function TeamProvider({ access, children }: { access: TeamAccess; children: React.ReactNode }) {
  const team = access.team;
  const { data: teamSeasons = [], isPending } = $api.useQuery(
    "get",
    "/api/v1/club-teams/{team_id}/seasons",
    { params: { path: { team_id: team.id } } },
  );
  const selectedId = useSyncExternalStore(subscribe, () => readStored(team.id), () => null);

  const teamSeason = useMemo(() => {
    if (!teamSeasons.length) return null;
    return (
      teamSeasons.find((s) => s.id === selectedId) ??
      teamSeasons.find((s) => s.is_current) ??
      teamSeasons[0]
    );
  }, [teamSeasons, selectedId]);

  const value: TeamContextValue = {
    access,
    team,
    teamSeason,
    teamSeasons,
    setTeamSeasonId: (id) => writeStored(team.id, id),
    canEdit: canEdit(access.role),
    isPending,
    base: `/${team.slug}`,
  };
  return (
    // The team's colour drives --primary for everything inside (see globals.css).
    <div className="team-accent contents" style={{ "--team-accent": team.colour ?? "oklch(0.5 0.2 258)" } as React.CSSProperties}>
      <TeamContext.Provider value={value}>{children}</TeamContext.Provider>
    </div>
  );
}

export function useTeam(): TeamContextValue {
  const ctx = useContext(TeamContext);
  if (!ctx) throw new Error("useTeam must be used inside TeamProvider");
  return ctx;
}
