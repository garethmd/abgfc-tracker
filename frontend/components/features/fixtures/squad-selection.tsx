"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Clock, MapPin, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { formatTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/stat-card";
import { GuestPicker } from "@/components/features/fixtures/guest-picker";
import { SectionTitle } from "@/components/page-header";
import { Field } from "@/components/features/fixtures/fixture-form";
import { cn } from "@/lib/utils";

type Fixture = Schema["FixtureDetail"];
type Member = Schema["SquadMemberRead"];
type Selection = Schema["SelectionRead"];
type Player = Schema["PlayerSummary"];

export function selectionKey(fixtureId: number) {
  return $api.queryOptions("get", "/api/v1/fixtures/{fixture_id}/selection", { params: { path: { fixture_id: fixtureId } } }).queryKey;
}

/** "Available 10 · Not available 2" */
export function selectionSummary(sel: Selection): string {
  return availabilitySummary({ available: sel.available.length, unavailable: sel.unavailable.length });
}

/** The same line from the headline the fixtures list carries (`FixtureRead.availability`). */
export function availabilitySummary(a: { available: number; unavailable: number }): string {
  return `Available ${a.available}${a.unavailable ? ` · Not available ${a.unavailable}` : ""}`;
}

/** Guests named on the selection - they aren't in the squad, so the result and live
 *  screens need them handed over or the coach would have to add them a second time. */
export function guestPlayers(sel: Selection | null | undefined): Player[] {
  return (sel?.available ?? []).filter((p) => p.is_guest).map((p) => p.player);
}

/** The available players, as a default for "who played" / the live line-up. undefined
 *  when there's no selection (or nobody marked yet), so callers keep their own default. */
export function pickedIds(sel: Selection | null | undefined): number[] | undefined {
  if (!sel) return undefined;
  const ids = sel.available.map((p) => p.player.id);
  return ids.length ? ids : undefined;
}

/** Kick-off minus the lead time, for display only - the message text comes from the server. */
export function arrivalTime(kickoffAt: string, leadMinutes: number): string {
  const d = new Date(kickoffAt); // naive wall-clock string → local time, like everywhere else
  d.setMinutes(d.getMinutes() - leadMinutes);
  return formatTime(d);
}

export function SquadSelection({
  fixture,
  squad,
  selection,
  leadMinutes,
  base,
}: {
  fixture: Fixture;
  squad: Member[];
  selection: Selection | null;
  leadMinutes: number;
  base: string;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  // Guests named on the selection, and any added in this session: children from other
  // teams in the age group playing for us this week. They aren't in the squad, so unlike
  // everyone else they have to be named before they can be marked available.
  const [guests, setGuests] = useState<Player[]>(
    () => [...(selection?.available ?? []), ...(selection?.unavailable ?? [])].filter((p) => p.is_guest).map((p) => p.player),
  );
  const squadIds = useMemo(() => new Set(squad.map((m) => m.player.id)), [squad]);
  const players = useMemo<Player[]>(() => {
    const fromSquad = squad.filter((m) => !m.left_at && !m.player.left_date).map((m) => m.player);
    // Anyone marked out but no longer in the squad still needs to be visible.
    const seen = new Set(fromSquad.map((p) => p.id));
    const extra = [...(selection?.unavailable ?? []).map((p) => p.player), ...guests].filter(
      (p) => !seen.has(p.id) && seen.add(p.id),
    );
    return [...fromSquad, ...extra];
  }, [squad, selection, guests]);

  // Everyone is available unless the coach taps them out.
  const [out, setOut] = useState<Set<number>>(() => new Set((selection?.unavailable ?? []).map((p) => p.player.id)));
  // The FA's imported times are placeholders; the real one is known a week or so before,
  // which is exactly when the coach is on this screen. Blank for an unset (00:00) kick-off.
  const [kickoff, setKickoff] = useState(() => (isUnset(fixture.kickoff_at) ? "" : timePart(fixture.kickoff_at)));
  // Where it's being played. Usually the default copied in when the fixture was created -
  // the exception is a late switch (a waterlogged pitch), which is also when the coach is
  // here telling the parents about it.
  const [ground, setGround] = useState(fixture.venue_notes ?? "");
  const [coaching, setCoaching] = useState(selection?.coaching ?? "");
  const [notes, setNotes] = useState(selection?.notes ?? "");
  const [confirmRemove, setConfirmRemove] = useState(false);

  const save = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/selection");
  const setTime = $api.useMutation("patch", "/api/v1/fixtures/{fixture_id}");
  const remove = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/selection");

  function toggle(id: number) {
    setOut((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function invalidate() {
    qc.invalidateQueries({ queryKey: selectionKey(fixture.id) });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures/{fixture_id}"] });
  }

  const kickoffAt = kickoff ? `${fixture.kickoff_at.slice(0, 10)}T${kickoff}:00` : fixture.kickoff_at;
  const kickoffChanged = kickoffAt !== fixture.kickoff_at;
  const groundChanged = (ground.trim() || null) !== (fixture.venue_notes ?? null);
  const fixtureChanged = kickoffChanged || groundChanged;

  async function onSave() {
    try {
      // The kick-off belongs to the fixture, availability to the selection - two writes,
      // the time first so a failure there doesn't leave the two disagreeing.
      if (fixtureChanged) {
        await setTime.mutateAsync({
          params: { path: { fixture_id: fixture.id } },
          body: {
            ...(kickoffChanged ? { kickoff_at: kickoffAt } : {}),
            ...(groundChanged ? { venue_notes: ground.trim() || null } : {}),
          },
        });
      }
      const d = await save.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: {
          unavailable_player_ids: [...out],
          guest_player_ids: guests.map((g) => g.id),
          coaching: coaching.trim() || null,
          notes: notes.trim() || null,
        },
      });
      qc.setQueryData(selectionKey(fixture.id), d);
      invalidate();
      toast.success(fixtureChanged ? "Match details and availability saved" : "Availability saved");
      router.replace(`${base}/fixtures/${fixture.id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onRemove() {
    try {
      await remove.mutateAsync({ params: { path: { fixture_id: fixture.id } } });
      qc.setQueryData(selectionKey(fixture.id), null);
      invalidate();
      toast.success("Availability cleared");
      router.replace(`${base}/fixtures/${fixture.id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const available = players.length - out.size;

  return (
    <div className="space-y-8 pb-24">
      <section>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <SectionTitle className="mb-0">Who can play</SectionTitle>
          <span className="tnum text-xs text-muted-foreground">
            Available {available}{out.size > 0 && <> · Not available {out.size}</>}
          </span>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">Everyone is in. Tap anyone who can&apos;t make it.</p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {players.map((p) => (
            <SelectionChip key={p.id} name={p.display_name} out={out.has(p.id)} guest={!squadIds.has(p.id)} onClick={() => toggle(p.id)} />
          ))}
        </div>
        {players.length === 0 && <p className="text-sm text-muted-foreground">No players in this season&apos;s squad.</p>}
        <GuestPicker
          exclude={players.map((p) => p.id)}
          onAdd={(p) => {
            setGuests((g) => [...g, p]);
            setOut((prev) => {
              const next = new Set(prev);
              next.delete(p.id);
              return next;
            });
          }}
        />
      </section>
      <section>
        <SectionTitle>Where and when</SectionTitle>
        <Card className="divide-y divide-border/40 text-sm">
          <label className="flex items-center gap-3 p-4">
            <Clock className="size-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 font-medium">Kick-off</span>
            <Input
              type="time"
              value={kickoff}
              onChange={(e) => setKickoff(e.target.value)}
              className="h-11 w-32 text-base"
              aria-label="Kick-off time"
            />
          </label>
          <label className="flex items-center gap-3 p-4">
            <MapPin className="size-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 font-medium">Ground</span>
            <Input
              value={ground}
              onChange={(e) => setGround(e.target.value)}
              placeholder="Not set"
              className="h-11 w-48 text-base"
              aria-label="Ground"
            />
          </label>
          <div className="flex items-center gap-3 p-4">
            <span className="size-4 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1">
              {kickoff ? (
                <>
                  <div className="font-medium">Arrive {arrivalTime(kickoffAt, leadMinutes)}</div>
                  <div className="text-xs text-muted-foreground">
                    {leadMinutes} min before the {formatTime(kickoffAt)} kick-off
                    {fixtureChanged && <span className="text-primary"> · saves with availability</span>}
                  </div>
                </>
              ) : (
                <>
                  <div className="font-medium">Kick-off time not set</div>
                  <div className="text-xs text-muted-foreground">
                    Fixtures imported from the FA list come with a placeholder time. Set the real one
                    here once the league confirms it.
                  </div>
                </>
              )}
            </div>
            <Link href={`${base}/settings`} className="shrink-0 text-xs font-medium text-primary hover:underline">
              Change {leadMinutes}m
            </Link>
          </div>
        </Card>
      </section>

      <section className="space-y-4">
        <Field label="Coaching on the day">
          <Input className="h-11" value={coaching} onChange={(e) => setCoaching(e.target.value)} placeholder="Adam & Dan" maxLength={200} />
        </Field>
        <Field label="Notes for parents">
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Bring both kits. Car park is the far one." className="text-base" />
        </Field>
      </section>

      {selection && (
        <div className="flex justify-center">
          <Button type="button" variant="ghost" className="h-11 text-destructive" onClick={() => setConfirmRemove(true)}>
            <Trash2 className="size-4" /> Clear availability
          </Button>
        </div>
      )}

      {/* Sticky save: thumb-reachable above the bottom nav */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto max-w-lg">
          <Button type="button" className="h-12 w-full text-base" onClick={onSave} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save availability"}
          </Button>
        </div>
      </div>

      <Dialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear availability?</DialogTitle>
            <DialogDescription>Who&apos;s available for this match is forgotten. Nothing recorded against the match is affected.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setConfirmRemove(false)}>Keep it</Button>
            <Button variant="destructive" className="h-11" onClick={onRemove} disabled={remove.isPending}>Clear</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Same footprint as the result-entry Chip: in (default) or out. */
function SelectionChip({ name, out, guest, onClick }: { name: string; out: boolean; guest?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={out}
      aria-label={`${name}${guest ? " (guest)" : ""}: ${out ? "not available" : "available"}`}
      className={cn(
        "flex h-12 flex-col items-center justify-center rounded-xl px-2 text-sm font-medium leading-tight ring-1 transition-all active:scale-[0.97]",
        out ? "bg-card text-muted-foreground/70 ring-border/40" : "bg-foreground text-background ring-foreground",
      )}
    >
      <span className={cn("max-w-full truncate", out && "line-through decoration-muted-foreground/60")}>{name}</span>
      {out ? (
        <span className="text-[10px] uppercase tracking-wider">Out</span>
      ) : guest ? (
        <span className="text-[10px] uppercase tracking-wider opacity-70">guest</span>
      ) : null}
    </button>
  );
}

/** "10:00" from a naive wall-clock kick-off, for <input type="time">. A slice, not a Date
 *  round-trip, which would shift it by the viewer's zone. */
function timePart(kickoffAt: string): string {
  return kickoffAt.slice(11, 16);
}

/** Midnight means the FA's placeholder, not a real midnight kick-off. */
function isUnset(kickoffAt: string): boolean {
  return kickoffAt.endsWith("T00:00:00");
}
