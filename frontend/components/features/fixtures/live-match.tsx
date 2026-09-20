"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Flag, MoreHorizontal, Trash2, Undo2, Users, X } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Card } from "@/components/stat-card";
import { SectionTitle } from "@/components/page-header";
import { Chip, GoalSheet, type Goal } from "@/components/features/fixtures/result-entry";
import { cn } from "@/lib/utils";

type Fixture = Schema["FixtureDetail"];
type Member = Schema["SquadMemberRead"];
type Player = Schema["PlayerSummary"];

/** The query key the fixture page and this screen share; every live write returns the
 *  whole FixtureDetail, so we drop it straight into the cache instead of refetching. */
function fixtureKey(fixtureId: number) {
  return $api.queryOptions("get", "/api/v1/fixtures/{fixture_id}", { params: { path: { fixture_id: fixtureId } } }).queryKey;
}

function availablePlayers(squad: Member[], fixture: Fixture): Player[] {
  const fromSquad = squad.filter((m) => !m.left_at && !m.player.left_date).map((m) => m.player);
  const extra = fixture.appearances.map((a) => a.player).filter((p) => !fromSquad.some((s) => s.id === p.id));
  return [...fromSquad, ...extra];
}

// --- Before kick-off: who's playing ---------------------------------------------------

export function LineUp({ fixture, squad, preselect }: { fixture: Fixture; squad: Member[]; preselect?: number[] }) {
  const qc = useQueryClient();
  const players = useMemo(() => availablePlayers(squad, fixture), [squad, fixture]);
  // Starts from the pre-match selection (starters + subs) when there is one.
  const [picked, setPicked] = useState<number[]>(() => (preselect ?? []).filter((id) => players.some((p) => p.id === id)));
  const start = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/live/start");

  function toggle(id: number) {
    setPicked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  }

  async function kickOff() {
    try {
      const d = await start.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: { player_ids: picked },
      });
      qc.setQueryData(fixtureKey(fixture.id), d);
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      toast.success("Kick off!");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="space-y-8 pb-24">
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <SectionTitle className="mb-0">Who&apos;s playing</SectionTitle>
          <span className="tnum text-xs text-muted-foreground">{picked.length} of {players.length}</span>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {players.map((p) => (
            <Chip key={p.id} selected={picked.includes(p.id)} onClick={() => toggle(p.id)}>
              {p.display_name}
            </Chip>
          ))}
        </div>
        {players.length === 0 && <p className="text-sm text-muted-foreground">No players in this season&apos;s squad.</p>}
      </section>

      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto max-w-lg">
          <Button type="button" className="h-12 w-full text-base" onClick={kickOff} disabled={start.isPending || picked.length === 0}>
            {start.isPending ? "Starting…" : "Kick off"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- During the match ---------------------------------------------------------------

type LastAction = { kind: "goal"; eventId: number } | { kind: "against" } | null;

export function LiveMatch({ fixture, squad, teamName, base }: { fixture: Fixture; squad: Member[]; teamName: string; base: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const players = useMemo(() => availablePlayers(squad, fixture), [squad, fixture]);
  const playing = fixture.appearances.map((a) => a.player);
  const [goalSheet, setGoalSheet] = useState(false);
  const [squadSheet, setSquadSheet] = useState(false);
  // Native confirm() is unreliable inside web views and the desktop app, so these are dialogs.
  const [confirming, setConfirming] = useState<"finish" | "abandon" | null>(null);
  const [last, setLast] = useState<LastAction>(null);

  const path = { params: { path: { fixture_id: fixture.id } } };
  // A retried goal is safe: the server recognises the sequence and returns the goal it
  // already has. "Against" has no such key, so it is never retried automatically.
  const addGoal = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/live/goals", { retry: 2 });
  const removeGoal = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/live/goals/{event_id}");
  const against = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/live/against");
  const removeAgainst = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/live/against");
  const setSquad = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/live/squad", { retry: 2 });
  const finish = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/live/finish");
  const abandon = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/live");
  const busy = [addGoal, removeGoal, against, removeAgainst, setSquad, finish, abandon].some((m) => m.isPending);

  function apply(d: Fixture) {
    qc.setQueryData(fixtureKey(fixture.id), d);
  }

  async function run<T>(fn: () => Promise<T>, after?: (d: T) => void) {
    try {
      const d = await fn();
      after?.(d);
    } catch (err) {
      toast.error(errorMessage(err));
      qc.invalidateQueries({ queryKey: fixtureKey(fixture.id) });
    }
  }

  const nextSequence = fixture.goals.reduce((m, g) => Math.max(m, g.sequence), 0) + 2;

  function onGoal(g: Omit<Goal, "key">) {
    setGoalSheet(false);
    run(
      () => addGoal.mutateAsync({ ...path, body: { ...g, sequence: nextSequence } }),
      (d) => {
        apply(d);
        const added = d.goals.find((x) => x.sequence === nextSequence);
        setLast(added ? { kind: "goal", eventId: added.id } : null);
      },
    );
  }

  function onAgainst() {
    run(() => against.mutateAsync(path), (d) => { apply(d); setLast({ kind: "against" }); });
  }

  function onRemoveGoal(eventId: number) {
    run(() => removeGoal.mutateAsync({ params: { path: { fixture_id: fixture.id, event_id: eventId } } }), (d) => {
      apply(d);
      if (last?.kind === "goal" && last.eventId === eventId) setLast(null);
    });
  }

  function onRemoveAgainst() {
    run(() => removeAgainst.mutateAsync(path), (d) => { apply(d); if (last?.kind === "against") setLast(null); });
  }

  function onUndo() {
    if (!last) return;
    if (last.kind === "goal") onRemoveGoal(last.eventId);
    else onRemoveAgainst();
  }

  function onSquad(playerIds: number[]) {
    setSquadSheet(false);
    run(() => setSquad.mutateAsync({ ...path, body: { player_ids: playerIds } }), apply);
  }

  function onFinish() {
    setConfirming(null);
    run(() => finish.mutateAsync(path), (d) => {
      apply(d);
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/players"] });
      toast.success("Full time - now pick the player of the match");
      router.replace(`${base}/fixtures/${fixture.id}/entry`);
    });
  }

  function onAbandon() {
    setConfirming(null);
    run(() => abandon.mutateAsync(path), () => {
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      toast.success("Live match discarded");
      router.replace(`${base}/fixtures/${fixture.id}`);
    });
  }

  const ourGoals = fixture.goals.filter((g) => g.event_type !== "own_goal").length;
  const oppGoals = (fixture.their_score ?? 0) - fixture.goals.filter((g) => g.event_type === "own_goal").length;

  return (
    <div className="space-y-8 pb-28">
      {/* Score: pinned under the top bar so it's always in view */}
      <div className="sticky top-14 z-20 -mx-4 border-b border-border/60 bg-background/90 px-4 py-3 backdrop-blur md:static md:mx-0 md:border-0 md:bg-transparent md:p-0">
        <Card className="p-5">
          <div className="flex items-center justify-between gap-3">
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{teamName}</span>
            <div className="flex items-center gap-3 tnum">
              <span className="text-5xl font-semibold tracking-tighter">{fixture.our_score ?? 0}</span>
              <span className="text-2xl text-muted-foreground">–</span>
              <span className="text-5xl font-semibold tracking-tighter">{fixture.their_score ?? 0}</span>
            </div>
            <span className="min-w-0 flex-1 truncate text-right text-sm font-medium">{fixture.opposition.short_name ?? fixture.opposition.name}</span>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-current" />
              </span>
              Live
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground">
                <MoreHorizontal className="size-4" />
                <span className="sr-only">More</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setSquadSheet(true)}><Users className="size-4" /> Change squad</DropdownMenuItem>
                <DropdownMenuItem onSelect={onRemoveAgainst} disabled={oppGoals === 0}><X className="size-4" /> Remove opposition goal</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setConfirming("abandon")}><Trash2 className="size-4" /> Discard live match</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </Card>
      </div>

      {/* Goals */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <SectionTitle className="mb-0">Goals</SectionTitle>
          <span className="tnum text-xs text-muted-foreground">{ourGoals} for · {oppGoals} against</span>
        </div>
        {fixture.goals.length > 0 ? (
          <Card className="divide-y divide-border/40">
            {fixture.goals.map((g, i) => (
              <div key={g.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="tnum w-5 text-xs text-muted-foreground">{i + 1}</span>
                <div className="flex-1">
                  {g.event_type === "opp_own_goal" ? (
                    <span className="font-medium">Opposition own goal</span>
                  ) : (
                    <span className={cn("font-medium", g.event_type === "own_goal" && "text-rose-600 dark:text-rose-400")}>
                      {g.scorer?.display_name}{g.event_type === "own_goal" && " (OG)"}
                    </span>
                  )}
                  {g.assisted_by && <span className="ml-1.5 text-xs text-muted-foreground">assist {g.assisted_by.display_name}</span>}
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveGoal(g.id)}
                  disabled={busy}
                  className="flex size-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
                  aria-label="Remove goal"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </Card>
        ) : (
          <p className="text-sm text-muted-foreground">No goals yet. Tap <span className="font-medium text-foreground">Goal</span> when one goes in.</p>
        )}
      </section>

      {/* Squad */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <SectionTitle className="mb-0">Playing</SectionTitle>
          <button type="button" className="text-xs font-medium text-primary" onClick={() => setSquadSheet(true)}>Change</button>
        </div>
        <Card className="divide-y divide-border/40">
          {fixture.appearances.map((a) => (
            <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="flex-1 font-medium">{a.player.display_name}</span>
            </div>
          ))}
        </Card>
      </section>

      {/* Sticky actions: thumb-reachable above the bottom nav */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto grid max-w-lg grid-cols-[1fr_auto_auto] gap-2">
          <Button type="button" className="h-14 text-base font-semibold" onClick={() => setGoalSheet(true)} disabled={busy || playing.length === 0}>
            Goal
          </Button>
          <Button type="button" variant="outline" className="h-14 px-4" onClick={onAgainst} disabled={busy}>
            Against
          </Button>
          <Button type="button" variant="outline" className="h-14 px-3" onClick={onUndo} disabled={busy || !last} aria-label="Undo last">
            <Undo2 className="size-5" />
          </Button>
          <Button type="button" variant="secondary" className="col-span-3 h-11" onClick={() => setConfirming("finish")} disabled={busy}>
            <Flag className="size-4" /> Full time
          </Button>
        </div>
      </div>

      <Dialog open={confirming !== null} onOpenChange={(o) => { if (!o) setConfirming(null); }}>
        <DialogContent>
          {confirming === "abandon" ? (
            <>
              <DialogHeader>
                <DialogTitle>Discard this live match?</DialogTitle>
                <DialogDescription>Everything recorded so far is removed and the fixture goes back to scheduled.</DialogDescription>
              </DialogHeader>
              <DialogFooter className="gap-2">
                <Button variant="outline" className="h-11" onClick={() => setConfirming(null)}>Keep going</Button>
                <Button variant="destructive" className="h-11" onClick={onAbandon} disabled={busy}>Discard</Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Full time?</DialogTitle>
                <DialogDescription className="tnum text-base text-foreground">
                  {teamName} {fixture.our_score ?? 0} – {fixture.their_score ?? 0} {fixture.opposition.name}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="gap-2">
                <Button variant="outline" className="h-11" onClick={() => setConfirming(null)}>Not yet</Button>
                <Button className="h-11" onClick={onFinish} disabled={busy}>
                  <Flag className="size-4" /> Full time
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <GoalSheet open={goalSheet} onOpenChange={setGoalSheet} players={playing} onAdd={onGoal} />
      <SquadSheet
        key={fixture.appearances.map((a) => a.player.id).join(",")}
        open={squadSheet}
        onOpenChange={setSquadSheet}
        players={players}
        initial={fixture.appearances.map((a) => a.player.id)}
        locked={fixture.goals.flatMap((g) => [g.scorer?.id, g.assisted_by?.id]).filter((id): id is number => id != null)}
        onSave={onSquad}
      />
    </div>
  );
}

// --- Sheets -----------------------------------------------------------------------

function SquadSheet({
  open,
  onOpenChange,
  players,
  initial,
  locked,
  onSave,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  players: Player[];
  initial: number[];
  locked: number[];
  onSave: (playerIds: number[]) => void;
}) {
  const [picked, setPicked] = useState<number[]>(initial);

  function reset() {
    setPicked(initial);
  }

  function toggle(id: number) {
    if (locked.includes(id) && picked.includes(id)) {
      toast.info("They have a goal or assist - remove that first");
      return;
    }
    setPicked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  }

  return (
    <Sheet open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <SheetHeader className="text-left">
          <SheetTitle>Who&apos;s playing?</SheetTitle>
        </SheetHeader>
        <div className="space-y-6 px-4">
          <div className="grid grid-cols-3 gap-2">
            {players.map((p) => (
              <Chip key={p.id} selected={picked.includes(p.id)} onClick={() => toggle(p.id)}>{p.display_name}</Chip>
            ))}
          </div>
          <Button className="h-12 w-full" onClick={() => onSave(picked)} disabled={picked.length === 0}>Save</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
