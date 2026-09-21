"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Clock, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { formatTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/stat-card";
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
  const players = useMemo<Player[]>(() => {
    const fromSquad = squad.filter((m) => !m.left_at && !m.player.left_date).map((m) => m.player);
    // Anyone marked out but no longer in the squad still needs to be visible.
    const extra = (selection?.unavailable ?? []).map((p) => p.player).filter((p) => !fromSquad.some((s) => s.id === p.id));
    return [...fromSquad, ...extra];
  }, [squad, selection]);

  // Everyone is available unless the coach taps them out.
  const [out, setOut] = useState<Set<number>>(() => new Set((selection?.unavailable ?? []).map((p) => p.player.id)));
  const [coaching, setCoaching] = useState(selection?.coaching ?? "");
  const [notes, setNotes] = useState(selection?.notes ?? "");
  const [confirmRemove, setConfirmRemove] = useState(false);

  const save = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/selection");
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
  }

  async function onSave() {
    try {
      const d = await save.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: { unavailable_player_ids: [...out], coaching: coaching.trim() || null, notes: notes.trim() || null },
      });
      qc.setQueryData(selectionKey(fixture.id), d);
      invalidate();
      toast.success("Availability saved");
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
            <SelectionChip key={p.id} name={p.display_name} out={out.has(p.id)} onClick={() => toggle(p.id)} />
          ))}
        </div>
        {players.length === 0 && <p className="text-sm text-muted-foreground">No players in this season&apos;s squad.</p>}
      </section>
      <section>
        <SectionTitle>Arrival</SectionTitle>
        <Card className="flex items-center gap-3 p-4 text-sm">
          <Clock className="size-4 shrink-0 text-muted-foreground" />
          {fixture.kickoff_at.endsWith("T00:00:00") ? (
            <>
              <div className="min-w-0 flex-1">
                <div className="font-medium">Kick-off time not set</div>
                <div className="text-xs text-muted-foreground">Parents will be asked to arrive {leadMinutes} min before kick-off.</div>
              </div>
              <Link href={`${base}/fixtures/${fixture.id}/edit`} className="text-xs font-medium text-primary hover:underline">Set it</Link>
            </>
          ) : (
            <>
              <div className="min-w-0 flex-1">
                <div className="font-medium">Arrive {arrivalTime(fixture.kickoff_at, leadMinutes)}</div>
                <div className="text-xs text-muted-foreground">{leadMinutes} min before the {formatTime(fixture.kickoff_at)} kick-off</div>
              </div>
              <Link href={`${base}/settings`} className="text-xs font-medium text-primary hover:underline">Change</Link>
            </>
          )}
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
function SelectionChip({ name, out, onClick }: { name: string; out: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={out}
      aria-label={`${name}: ${out ? "not available" : "available"}`}
      className={cn(
        "flex h-12 flex-col items-center justify-center rounded-xl px-2 text-sm font-medium leading-tight ring-1 transition-all active:scale-[0.97]",
        out ? "bg-card text-muted-foreground/70 ring-border/40" : "bg-foreground text-background ring-foreground",
      )}
    >
      <span className={cn("max-w-full truncate", out && "line-through decoration-muted-foreground/60")}>{name}</span>
      {out && <span className="text-[10px] uppercase tracking-wider">Out</span>}
    </button>
  );
}
