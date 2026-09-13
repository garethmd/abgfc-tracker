"use client";

import Link from "next/link";
import type { Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { EmptyState } from "@/components/empty-state";
import { Users } from "lucide-react";
import { cn } from "@/lib/utils";

const AWARD_SHORT: Record<string, string> = { coaches_potm: "Coaches' POTM", parents_potm: "Parents' POTM" };

function awardLabel(code: string) {
  return AWARD_SHORT[code] ?? code.replace(/^[a-z0-9-]+_/, "").replace(/_/g, " ");
}

export function Leaderboard({ board, base = "" }: { board: Schema["Leaderboard"]; base?: string }) {
  if (!board.rows.length) {
    return (
      <EmptyState
        icon={Users}
        title="No squad yet"
        description="Add players to this season's squad and they'll appear here with zeros until the first match."
      />
    );
  }
  const noGames = board.rows.every((r) => r.appearances === 0);

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="sticky left-0 z-10 bg-card py-3 pl-4 pr-2 text-left font-medium">Player</th>
              <Th>Apps</Th>
              <Th>Goals</Th>
              <Th>Assists</Th>
              <Th title="Goals per game">GPG</Th>
              {board.award_types.map((a) => (
                <Th key={a.award_type_id} title={a.award_type_code}>
                  {awardLabel(a.award_type_code)}
                </Th>
              ))}
            </tr>
          </thead>
          <tbody className="tnum">
            {board.rows.map((r, i) => (
              <tr key={r.player.id} className={cn("border-b border-border/40 last:border-0", noGames && "text-muted-foreground")}>
                <td className="sticky left-0 z-10 bg-card py-3 pl-4 pr-2">
                  <Link href={`${base}/players/${r.player.id}`} className="flex items-center gap-2.5 font-medium hover:underline">
                    <span
                      className={cn(
                        "flex size-6 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold",
                        i === 0 && r.goals > 0 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
                      )}
                    >
                      {r.squad_number ?? "–"}
                    </span>
                    <span className="whitespace-nowrap">{r.player.display_name}</span>
                  </Link>
                </td>
                <Td>{r.appearances}</Td>
                <Td strong={r.goals > 0}>{r.goals}</Td>
                <Td strong={r.assists > 0}>{r.assists}</Td>
                <Td muted>{r.goals_per_game.toFixed(2)}</Td>
                {r.awards.map((a) => (
                  <Td key={a.award_type_id} strong={a.count > 0}>
                    {a.count}
                  </Td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Th({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <th title={title} className="whitespace-nowrap px-3 py-3 text-right font-medium last:pr-4">
      {children}
    </th>
  );
}

function Td({ children, strong, muted }: { children: React.ReactNode; strong?: boolean; muted?: boolean }) {
  return (
    <td className={cn("px-3 py-3 text-right last:pr-4", strong && "font-semibold", muted && "text-muted-foreground")}>
      {children}
    </td>
  );
}
