"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Flag, MoreHorizontal, Star, Trash2, Undo2, Users, X } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
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

// --- Before kick-off: who's playing, who's captain ------------------------------------

export function LineUp({ fixture, squad }: { fixture: Fixture; squad: Member[] }) {
  const qc = useQueryClient();
  const players = useMemo(() => availablePlayers(squad, fixture), [squad, fixture]);
  const [picked, setPicked] = useState<number[]>([]);
  const [captain, setCaptain] = useState<number | null>(null);
  const [captainSheet, setCaptainSheet] = useState(false);
  const start = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/live/start");

  function toggle(id: number) {
    setPicked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
    if (captain === id) setCaptain(null);
  }

  async function kickOff() {
    try {
      const d = await start.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: { player_ids: picked, captain_id: captain },
      });
      qc.setQueryData(fixtureKey(fixture.id), d);
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      toast.success("Kick off!");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const nameOf = (id: number | null) => players.find((p) => p.id === id)?.display_name;

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

      <section>
        <SectionTitle>Captain</SectionTitle>
        <Button type="button" variant="outline" className="h-12 w-full justify-start" onClick={() => setCaptainSheet(true)} disabled={picked.length === 0}>
          <Star className={cn("size-4", captain ? "fill-current text-primary" : "text-muted-foreground")} />
          {captain ? nameOf(captain) : "Pick a captain (optional)"}
        </Button>
      </section>

      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto max-w-lg">
          <Button type="button" className="h-12 w-full text-base" onClick={kickOff} disabled={start.isPending || picked.length === 0}>
            {start.isPending ? "Starting…" : "Kick off"}
          </Button>
        </div>
      </div>

      <PlayerPickSheet
        open={captainSheet}
        onOpenChange={setCaptainSheet}
        title="Who's captain?"
        players={players.filter((p) => picked.includes(p.id))}
        selected={captain}
        onPick={(id) => { setCaptain(id); setCaptainSheet(false); }}
        onClear={() => { setCaptain(null); setCaptainSheet(false); }}
      />
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

  function onSquad(playerIds: number[], captainId: number | null) {
    setSquadSheet(false);
    run(() => setSquad.mutateAsync({ ...path, body: { player_ids: playerIds, captain_id: captainId } }), apply);
  }

  function onFinish() {
    if (!confirm(`Full time? ${teamName} ${fixture.our_score} – ${fixture.their_score} ${fixture.opposition.name}`)) return;
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
    if (!confirm("Discard everything recorded and put the fixture back to scheduled?")) return;
    run(() => abandon.mutateAsync(path), () => {
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      toast.success("Live match discarded");
      router.replace(`${base}/fixtures/${fixture.id}`);
    });
  }

  const captain = fixture.appearances.find((a) => a.captain)?.player;
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
                <DropdownMenuItem variant="destructive" onSelect={onAbandon}><Trash2 className="size-4" /> Discard live match</DropdownMenuItem>
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
              {a.captain && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Star className="size-3 fill-current text-primary" /> Captain</span>}
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
          <Button type="button" variant="secondary" className="col-span-3 h-11" onClick={onFinish} disabled={busy}>
            <Flag className="size-4" /> Full time
          </Button>
        </div>
      </div>

      <GoalSheet open={goalSheet} onOpenChange={setGoalSheet} players={playing} onAdd={onGoal} />
      <SquadSheet
        key={fixture.appearances.map((a) => `${a.player.id}${a.captain ? "c" : ""}`).join(",")}
        open={squadSheet}
        onOpenChange={setSquadSheet}
        players={players}
        initial={fixture.appearances.map((a) => a.player.id)}
        initialCaptain={captain?.id ?? null}
        locked={fixture.goals.flatMap((g) => [g.scorer?.id, g.assisted_by?.id]).filter((id): id is number => id != null)}
        onSave={onSquad}
      />
    </div>
  );
}

// --- Sheets -----------------------------------------------------------------------

function PlayerPickSheet({
  open,
  onOpenChange,
  title,
  players,
  selected,
  onPick,
  onClear,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  players: Player[];
  selected: number | null;
  onPick: (id: number) => void;
  onClear: () => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <SheetHeader className="text-left">
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <div className="px-4">
          <div className="grid grid-cols-3 gap-2">
            {players.map((p) => (
              <Chip key={p.id} selected={selected === p.id} onClick={() => onPick(p.id)} accent>{p.display_name}</Chip>
            ))}
          </div>
          <Button variant="ghost" className="mt-4 h-11 w-full" onClick={onClear}>No captain</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function SquadSheet({
  open,
  onOpenChange,
  players,
  initial,
  initialCaptain,
  locked,
  onSave,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  players: Player[];
  initial: number[];
  initialCaptain: number | null;
  locked: number[];
  onSave: (playerIds: number[], captainId: number | null) => void;
}) {
  const [picked, setPicked] = useState<number[]>(initial);
  const [captain, setCaptain] = useState<number | null>(initialCaptain);

  function reset() {
    setPicked(initial);
    setCaptain(initialCaptain);
  }

  function toggle(id: number) {
    if (locked.includes(id) && picked.includes(id)) {
      toast.info("They have a goal or assist - remove that first");
      return;
    }
    setPicked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
    if (captain === id) setCaptain(null);
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
          <div>
            <SectionTitle>Captain</SectionTitle>
            <div className="grid grid-cols-3 gap-2">
              {players.filter((p) => picked.includes(p.id)).map((p) => (
                <Chip key={p.id} selected={captain === p.id} onClick={() => setCaptain(captain === p.id ? null : p.id)} accent>{p.display_name}</Chip>
              ))}
            </div>
          </div>
          <Button className="h-12 w-full" onClick={() => onSave(picked, captain)} disabled={picked.length === 0}>Save</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
