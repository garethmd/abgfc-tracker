"use client";

import { ChevronDown } from "lucide-react";
import { useTeam } from "@/lib/team-context";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export function SeasonSwitcher({ compact = false }: { compact?: boolean }) {
  const { teamSeasons, teamSeason, setTeamSeasonId } = useTeam();
  if (!teamSeason) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex items-center gap-1.5 rounded-lg text-sm font-medium transition-colors hover:bg-accent",
          compact ? "h-9 px-2.5" : "h-10 w-full justify-between px-3 ring-1 ring-border/60",
        )}
      >
        <span className="flex items-center gap-2">
          {!compact && <span className="text-xs text-muted-foreground">Season</span>}
          <span className="tnum">{teamSeason.season.name}</span>
          {teamSeason.age_group && <span className="text-xs text-muted-foreground">{teamSeason.age_group}</span>}
        </span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-44">
        {teamSeasons.map((s) => (
          <DropdownMenuItem key={s.id} onSelect={() => setTeamSeasonId(s.id)} className="tnum">
            {s.season.name}
            <span className="text-xs text-muted-foreground">{s.age_group}</span>
            {s.is_current && <span className="ml-auto text-xs text-muted-foreground">current</span>}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
