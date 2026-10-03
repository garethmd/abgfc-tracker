"use client";

import { $api } from "@/lib/api/client";
import { GroundLink } from "@/components/ground-link";
import { Card } from "@/components/stat-card";

/** A small map of where a match is being played.
 *
 *  OpenStreetMap, not Google: the tiles need no API key and no billing account, and they
 *  don't load a third-party tracker into an app full of children's names. The server
 *  geocodes the ground once and caches it (`services/grounds.py`); when it can't be placed
 *  the map simply doesn't appear and the directions link carries on working. */
export function GroundMap({ ground, className }: { ground: string; className?: string }) {
  const q = $api.useQuery("get", "/api/v1/grounds/lookup", { params: { query: { q: ground } } }, { staleTime: Infinity });
  const d = q.data;
  if (!d?.found || d.lat == null || d.lon == null) return null;

  // A tight box around the point - about 700m across, enough to recognise the turning.
  const pad = 0.004;
  const bbox = [d.lon - pad, d.lat - pad / 2, d.lon + pad, d.lat + pad / 2].join("%2C");
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${d.lat}%2C${d.lon}`;

  return (
    <Card className={className}>
      <iframe
        src={src}
        title={`Map of ${ground}`}
        loading="lazy"
        className="h-44 w-full rounded-t-xl border-0 bg-muted"
        referrerPolicy="no-referrer"
      />
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-xs text-muted-foreground">
        <GroundLink ground={ground} className="min-w-0" />
        <span className="shrink-0 opacity-70">OpenStreetMap</span>
      </div>
    </Card>
  );
}
