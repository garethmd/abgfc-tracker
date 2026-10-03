import Link from "next/link";
import { Award, Crosshair, Handshake, Star } from "lucide-react";
import type { Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { joinNames } from "@/lib/format";

const ICONS = [Crosshair, Handshake, Award, Star];

/** `guestIds` are players who turned out for us from another team in the age group - their
 *  goals count for us, so they can hold a tile, but the tile says whose player they are. */
export function HighlightTiles({ tiles, base = "", guestIds }: { tiles: Schema["HighlightTile"][]; base?: string; guestIds?: Set<number> }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((t, i) => {
        const Icon = ICONS[i % ICONS.length];
        const names = t.players.map((p) => (guestIds?.has(p.id) ? `${p.display_name} (guest)` : p.display_name));
        const empty = t.players.length === 0;
        return (
          <Card key={t.label} className="flex flex-col p-4">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Icon className="size-3.5" />
              <span className="truncate text-[11px] font-medium uppercase tracking-wider">{shortLabel(t.label)}</span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="tnum text-3xl font-semibold tracking-tight">{empty ? "—" : t.value}</span>
            </div>
            <div className="mt-1 min-h-10 text-sm leading-snug">
              {empty ? (
                <span className="text-muted-foreground">Nothing yet</span>
              ) : t.players.length === 1 ? (
                <Link href={`${base}/players/${t.players[0].id}`} className="font-medium hover:underline">
                  {names[0]}
                </Link>
              ) : (
                <span className="font-medium">{joinNames(names)}</span>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function shortLabel(label: string) {
  return label.replace("Player of the Match", "POTM");
}
