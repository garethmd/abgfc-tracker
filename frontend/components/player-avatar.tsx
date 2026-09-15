"use client";

import { cn } from "@/lib/utils";

/** Same-origin, access-checked photo URL; `key` changes on every upload so caches refresh. */
export function playerPhotoUrl(playerId: number, key: string, size: "full" | "thumb" = "thumb") {
  return `/api/v1/players/${playerId}/photo?size=${size}&v=${key}`;
}

export function PlayerAvatar({
  playerId,
  name,
  photoKey,
  size = 36,
  className,
}: {
  playerId: number;
  name: string;
  photoKey?: string | null;
  size?: number;
  className?: string;
}) {
  const initials = name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-muted font-semibold text-muted-foreground", className)}
      style={{ width: size, height: size, fontSize: Math.max(11, size * 0.38) }}
    >
      {photoKey ? (
        // eslint-disable-next-line @next/next/no-img-element -- private, cookie-authenticated endpoint; next/image can't optimise it
        <img src={playerPhotoUrl(playerId, photoKey, size > 300 ? "full" : "thumb")} alt={name} className="size-full object-cover" />
      ) : (
        initials
      )}
    </span>
  );
}
