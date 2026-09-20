const dateFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });
const longDateFmt = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

export function formatLongDate(iso: string): string {
  return longDateFmt.format(new Date(iso));
}

export function formatTime(when: string | Date): string {
  return timeFmt.format(typeof when === "string" ? new Date(when) : when);
}

/** "2026-10-17T10:00" for <input type="datetime-local">. Kick-off is a naive wall-clock
 *  time, so this is a slice, not a Date round-trip (which would shift it by the zone). */
export function toLocalInput(iso: string): string {
  return iso.slice(0, 16);
}

export function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} & ${names[names.length - 1]}`;
}

export const STATUS_LABEL: Record<string, string> = {
  scheduled: "Scheduled",
  live: "Live",
  played: "Played",
  postponed: "Postponed",
  cancelled: "Cancelled",
  abandoned: "Abandoned",
};

export const VENUE_LABEL: Record<string, string> = { home: "Home", away: "Away", neutral: "Neutral" };
