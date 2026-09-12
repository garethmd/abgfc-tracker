"use client";

import { ChevronDown } from "lucide-react";
import { useSeason } from "@/lib/season-context";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export function SeasonSwitcher({ compact = false }: { compact?: boolean }) {
  const { seasons, season, setSeasonId } = useSeason();
  if (!season) return null;

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
          <span className="tnum">{season.name}</span>
        </span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        {seasons.map((s) => (
          <DropdownMenuItem key={s.id} onSelect={() => setSeasonId(s.id)} className="tnum">
            {s.name}
            {s.is_current && <span className="ml-auto text-xs text-muted-foreground">current</span>}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
