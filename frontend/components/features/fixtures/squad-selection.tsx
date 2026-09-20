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
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/stat-card";
import { SectionTitle } from "@/components/page-header";
import { Field } from "@/components/features/fixtures/fixture-form";
import { cn } from "@/lib/utils";

type Fixture = Schema["FixtureDetail"];
type Member = Schema["SquadMemberRead"];
type Selection = Schema["SelectionRead"];
type Status = Schema["SelectionStatus"];
type Player = Schema["PlayerSummary"];

/** Tap order: not picked → starting → sub → out → not picked. */
const NEXT: Record<Status | "none", Status | "none"> = { none: "start", start: "sub", sub: "unavailable", unavailable: "none" };
const QUICK_REASONS = ["Injured", "Ill", "Away", "Holiday", "Unavailable"];

type Pick = { status: Status; reason: string | null };

export function selectionKey(fixtureId: number) {
  return $api.queryOptions("get", "/api/v1/fixtures/{fixture_id}/selection", { params: { path: { fixture_id: fixtureId } } }).queryKey;
}

/** "Selected 10 · Starting 7 · Subs 3" */
export function selectionSummary(sel: Selection): string {
  return `Selected ${sel.starters.length + sel.subs.length} · Starting ${sel.starters.length} · Subs ${sel.subs.length}`;
}

/** Starters + subs from a selection, as a default for "who played" / the live line-up.
 *  undefined when there's no selection (or nobody picked yet), so callers keep their default. */
export function pickedIds(sel: Selection | null | undefined): number[] | undefined {
  if (!sel) return undefined;
  const ids = [...sel.starters, ...sel.subs].map((p) => p.player.id);
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
    // Anyone already on the plan but no longer in the squad still needs to be visible.
    const onPlan = selection ? [...selection.starters, ...selection.subs, ...selection.unavailable].map((p) => p.player) : [];
    const extra = onPlan.filter((p) => !fromSquad.some((s) => s.id === p.id));
    return [...fromSquad, ...extra];
  }, [squad, selection]);

  const [picks, setPicks] = useState<Record<number, Pick>>(() => {
    const init: Record<number, Pick> = {};
    if (selection) {
      for (const p of [...selection.starters, ...selection.subs, ...selection.unavailable]) {
        init[p.player.id] = { status: p.status, reason: p.reason };
      }
    }
    return init;
  });
  const [coaching, setCoaching] = useState(selection?.coaching ?? "");
  const [notes, setNotes] = useState(selection?.notes ?? "");
  const [reasonFor, setReasonFor] = useState<Player | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const save = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/selection");
  const remove = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/selection");

  const counts = { start: 0, sub: 0, unavailable: 0 };
  for (const p of Object.values(picks)) counts[p.status] += 1;
  const unpicked = players.length - counts.start - counts.sub - counts.unavailable;

  function tap(p: Player) {
    const current = picks[p.id]?.status ?? "none";
    const next = NEXT[current];
    setPicks((prev) => {
      const copy = { ...prev };
      if (next === "none") delete copy[p.id];
      else copy[p.id] = { status: next, reason: next === "unavailable" ? (prev[p.id]?.reason ?? null) : null };
      return copy;
    });
    if (next === "unavailable") setReasonFor(p);
  }

  function setReason(playerId: number, reason: string | null) {
    setPicks((prev) => (prev[playerId] ? { ...prev, [playerId]: { ...prev[playerId], reason } } : prev));
    setReasonFor(null);
  }

  function invalidate() {
    qc.invalidateQueries({ queryKey: selectionKey(fixture.id) });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
  }

  async function onSave() {
    try {
      const d = await save.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: {
          players: Object.entries(picks).map(([id, p]) => ({ player_id: Number(id), status: p.status, reason: p.reason })),
          coaching: coaching.trim() || null,
          notes: notes.trim() || null,
        },
      });
      qc.setQueryData(selectionKey(fixture.id), d);
      invalidate();
      toast.success("Squad saved");
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
      toast.success("Selection removed");
      router.replace(`${base}/fixtures/${fixture.id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="space-y-8 pb-24">
      <section>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <SectionTitle className="mb-0">Squad</SectionTitle>
          <span className="tnum text-xs text-muted-foreground">
            Starting {counts.start} · Subs {counts.sub} · Out {counts.unavailable}
            {unpicked > 0 && <> · {unpicked} to pick</>}
          </span>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">Tap a player to cycle: starting → sub → out.</p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {players.map((p) => (
            <SelectionChip key={p.id} name={p.display_name} pick={picks[p.id]} onClick={() => tap(p)} />
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
            <Trash2 className="size-4" /> Remove selection
          </Button>
        </div>
      )}

      {/* Sticky save: thumb-reachable above the bottom nav */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto max-w-lg">
          <Button type="button" className="h-12 w-full text-base" onClick={onSave} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save selection"}
          </Button>
        </div>
      </div>

      <ReasonSheet
        player={reasonFor}
        initial={reasonFor ? (picks[reasonFor.id]?.reason ?? "") : ""}
        onDone={(reason) => reasonFor && setReason(reasonFor.id, reason)}
        onClose={() => setReasonFor(null)}
      />

      <Dialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove this selection?</DialogTitle>
            <DialogDescription>The plan for this match is cleared. Nothing recorded against the match is affected.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setConfirmRemove(false)}>Keep it</Button>
            <Button variant="destructive" className="h-11" onClick={onRemove} disabled={remove.isPending}>Remove</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Same footprint as the result-entry Chip, with three picked states. */
function SelectionChip({ name, pick, onClick }: { name: string; pick: Pick | undefined; onClick: () => void }) {
  const status = pick?.status ?? "none";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={status !== "none"}
      aria-label={`${name}: ${status === "none" ? "not picked" : status === "start" ? "starting" : status === "sub" ? "sub" : "out"}`}
      className={cn(
        "flex h-12 flex-col items-center justify-center rounded-xl px-2 text-sm font-medium leading-tight ring-1 transition-all active:scale-[0.97]",
        status === "none" && "bg-card text-muted-foreground ring-border/60 hover:text-foreground",
        status === "start" && "bg-foreground text-background ring-foreground",
        status === "sub" && "bg-primary/10 text-foreground ring-primary",
        status === "unavailable" && "bg-card text-muted-foreground/70 ring-border/40",
      )}
    >
      <span className={cn("max-w-full truncate", status === "unavailable" && "line-through decoration-muted-foreground/60")}>{name}</span>
      {status === "sub" && <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">Sub</span>}
      {status === "unavailable" && (
        <span className="max-w-full truncate text-[10px] uppercase tracking-wider">{pick?.reason ?? "Out"}</span>
      )}
    </button>
  );
}

function ReasonSheet({
  player,
  initial,
  onDone,
  onClose,
}: {
  player: Player | null;
  initial: string;
  onDone: (reason: string | null) => void;
  onClose: () => void;
}) {
  const [other, setOther] = useState("");
  const open = player !== null;
  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) { onClose(); setOther(""); } }}>
      <SheetContent side="bottom" className="rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
        <SheetHeader className="text-left">
          <SheetTitle>Why is {player?.display_name} out?</SheetTitle>
        </SheetHeader>
        <div className="mx-auto w-full max-w-lg space-y-4 px-4">
          <div className="grid grid-cols-3 gap-2">
            {QUICK_REASONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => { onDone(r); setOther(""); }}
                className={cn(
                  "h-12 rounded-xl px-2 text-sm font-medium ring-1 transition-all active:scale-[0.97]",
                  initial === r ? "bg-foreground text-background ring-foreground" : "bg-card text-muted-foreground ring-border/60 hover:text-foreground",
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => { e.preventDefault(); onDone(other.trim() || null); setOther(""); }}
          >
            <Input className="h-11 flex-1" value={other} onChange={(e) => setOther(e.target.value)} placeholder="Other reason (optional)" maxLength={100} />
            <Button type="submit" variant="outline" className="h-11">{other.trim() ? "Done" : "Skip"}</Button>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}
