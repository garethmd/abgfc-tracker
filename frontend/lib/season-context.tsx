"use client";

import { createContext, useContext, useMemo, useSyncExternalStore } from "react";
import { $api, type Schema } from "@/lib/api/client";

type Season = Schema["SeasonRead"];

interface SeasonContextValue {
  seasons: Season[];
  season: Season | null;
  setSeasonId: (id: number) => void;
  isPending: boolean;
}

const SeasonContext = createContext<SeasonContextValue | null>(null);
const STORAGE_KEY = "abgfc.seasonId";

// Tiny external store over localStorage so the selection survives reloads without
// a hydration mismatch (server snapshot is always null).
const listeners = new Set<() => void>();
function readStored(): number | null {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}
function writeStored(id: number) {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(id));
  } catch {
    /* private mode etc. */
  }
  listeners.forEach((l) => l());
}
function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function SeasonProvider({ children }: { children: React.ReactNode }) {
  const { data: seasons = [], isPending } = $api.useQuery("get", "/api/v1/seasons");
  const selectedId = useSyncExternalStore(subscribe, readStored, () => null);

  const season = useMemo(() => {
    if (!seasons.length) return null;
    return seasons.find((s) => s.id === selectedId) ?? seasons.find((s) => s.is_current) ?? seasons[0];
  }, [seasons, selectedId]);

  const setSeasonId = (id: number) => writeStored(id);

  return (
    <SeasonContext.Provider value={{ seasons, season, setSeasonId, isPending }}>
      {children}
    </SeasonContext.Provider>
  );
}

export function useSeason(): SeasonContextValue {
  const ctx = useContext(SeasonContext);
  if (!ctx) throw new Error("useSeason must be used inside SeasonProvider");
  return ctx;
}
