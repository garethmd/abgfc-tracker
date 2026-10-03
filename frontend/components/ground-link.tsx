import { ExternalLink, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

/** A ground, linked to Google Maps for directions. The link is a plain search URL, so it
 *  needs no API key and opens the Maps app on a phone - which is what a parent driving
 *  there actually wants. */
export function GroundLink({ ground, className }: { ground: string; className?: string }) {
  return (
    <a
      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery(ground))}`}
      target="_blank"
      rel="noopener noreferrer"
      title={`Directions to ${ground}`}
      className={cn("inline-flex min-w-0 items-center gap-1 hover:text-foreground hover:underline", className)}
    >
      <MapPin className="size-3 shrink-0" />
      <span className="truncate">{ground}</span>
      <ExternalLink className="size-3 shrink-0 opacity-60" />
    </a>
  );
}

/** What to send to Maps. Grounds are recorded with the pitch on the end ("Hook Junior
 *  School 7v7", "Headley Playing Fields 4"), which is what the coach needs on the day but
 *  not something Maps can find, so the pitch is dropped from the search and kept on screen. */
export function mapQuery(ground: string): string {
  const trimmed = ground
    .replace(/\s*[-–]\s*\d+v\d+\s*$/i, "")
    .replace(/\s+(?:pitch\s*)?#?\d+\s*$/i, "")
    .replace(/\s+\d+v\d+\s*$/i, "")
    .trim();
  return trimmed || ground;
}
