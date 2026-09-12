"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Card } from "@/components/stat-card";
import { SectionTitle } from "@/components/page-header";
import { cn } from "@/lib/utils";

type Fixture = Schema["FixtureDetail"];
type Member = Schema["SquadMemberRead"];
type AwardType = Schema["AwardTypeRead"];

interface Goal {
  key: number;
  event_type: "goal" | "own_goal" | "opp_own_goal";
  scorer_id: number | null;
  assisted_by_id: number | null;
}

export function ResultEntry({ fixture, squad, awardTypes, base }: { fixture: Fixture; squad: Member[]; awardTypes: AwardType[]; base: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const players = useMemo(() => {
    const fromSquad = squad.filter((m) => !m.left_at && !m.player.left_date).map((m) => m.player);
    // Anyone recorded on this fixture but no longer in the squad still needs to be selectable.
    const extra = fixture.appearances.map((a) => a.player).filter((p) => !fromSquad.some((s) => s.id === p.id));
    return [...fromSquad, ...extra];
  }, [squad, fixture.appearances]);

  const isEdit = fixture.status === "played";
  // Fresh entry: preselect the whole squad — most kids play every week, so deselecting is fewer taps.
  const [playing, setPlaying] = useState<Set<number>>(
    () => new Set(isEdit ? fixture.appearances.map((a) => a.player.id) : players.map((p) => p.id)),
  );
  const [ourScore, setOurScore] = useState(fixture.our_score ?? 0);
  const [theirScore, setTheirScore] = useState(fixture.their_score ?? 0);
  const [goals, setGoals] = useState<Goal[]>(() =>
    fixture.goals.map((g, i) => ({
      key: i,
      event_type: g.event_type as Goal["event_type"],
      scorer_id: g.scorer?.id ?? null,
      assisted_by_id: g.assisted_by?.id ?? null,
    })),
  );
  const [awards, setAwards] = useState<Record<number, Set<number>>>(() => {
    const init: Record<number, Set<number>> = {};
    for (const at of awardTypes) init[at.id] = new Set();
    for (const a of fixture.awards) init[a.award_type.id]?.add(a.player.id);
    return init;
  });
  const [goalSheet, setGoalSheet] = useState(false);

  const submit = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/result");
  const playingPlayers = players.filter((p) => playing.has(p.id));
  const nameOf = (id: number | null) => players.find((p) => p.id === id)?.display_name ?? "?";

  function togglePlaying(id: number) {
    setPlaying((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        // Drop any goals/awards for someone who's now not playing.
        setGoals((gs) => gs.filter((g) => g.scorer_id !== id).map((g) => (g.assisted_by_id === id ? { ...g, assisted_by_id: null } : g)));
        setAwards((aw) => Object.fromEntries(Object.entries(aw).map(([k, set]) => [k, new Set([...set].filter((p) => p !== id))])));
      } else next.add(id);
      return next;
    });
  }

  function addGoal(goal: Omit<Goal, "key">) {
    setGoals((gs) => [...gs, { ...goal, key: Date.now() }]);
    if (goal.event_type === "own_goal") setTheirScore((s) => Math.max(s, goals.filter((g) => g.event_type === "own_goal").length + 1));
    else setOurScore((s) => Math.max(s, goals.filter((g) => g.event_type !== "own_goal").length + 1));
    setGoalSheet(false);
  }

  function toggleAward(typeId: number, playerId: number) {
    setAwards((prev) => {
      const set = new Set(prev[typeId]);
      if (set.has(playerId)) set.delete(playerId);
      else set.add(playerId);
      return { ...prev, [typeId]: set };
    });
  }

  async function onSave() {
    try {
      await submit.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: {
          our_score: ourScore,
          their_score: theirScore,
          appearances: playingPlayers.map((p) => ({ player_id: p.id, started: true })),
          goals: goals.map((g) => ({ event_type: g.event_type, scorer_id: g.scorer_id, assisted_by_id: g.assisted_by_id })),
          awards: Object.entries(awards).flatMap(([typeId, set]) => [...set].map((player_id) => ({ award_type_id: Number(typeId), player_id }))),
        },
      });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/players"] });
      toast.success("Result saved");
      router.replace(`${base}/fixtures/${fixture.id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const ourGoalsRecorded = goals.filter((g) => g.event_type !== "own_goal").length;

  return (
    <div className="space-y-8 pb-24">
      {/* Score */}
      <section>
        <SectionTitle>Score</SectionTitle>
        <Card className="grid grid-cols-2 divide-x divide-border/60">
          <ScoreStepper label="Blues" value={ourScore} onChange={setOurScore} />
          <ScoreStepper label={fixture.opposition.short_name ?? fixture.opposition.name} value={theirScore} onChange={setTheirScore} />
        </Card>
      </section>

      {/* Who played */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <SectionTitle className="mb-0">Who played</SectionTitle>
          <span className="tnum text-xs text-muted-foreground">{playing.size} of {players.length}</span>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {players.map((p) => (
            <Chip key={p.id} selected={playing.has(p.id)} onClick={() => togglePlaying(p.id)}>
              {p.display_name}
            </Chip>
          ))}
        </div>
        {players.length === 0 && <p className="text-sm text-muted-foreground">No players in this season&apos;s squad.</p>}
      </section>

      {/* Goals */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <SectionTitle className="mb-0">Goals</SectionTitle>
          {ourGoalsRecorded !== ourScore && (
            <span className="text-xs text-amber-600">{ourGoalsRecorded} of {ourScore} recorded</span>
          )}
        </div>
        {goals.length > 0 && (
          <Card className="mb-3 divide-y divide-border/40">
            {goals.map((g, i) => (
              <div key={g.key} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="tnum w-5 text-xs text-muted-foreground">{i + 1}</span>
                <div className="flex-1">
                  {g.event_type === "opp_own_goal" ? (
                    <span className="font-medium">Opposition own goal</span>
                  ) : (
                    <span className={cn("font-medium", g.event_type === "own_goal" && "text-rose-600 dark:text-rose-400")}>
                      {nameOf(g.scorer_id)}{g.event_type === "own_goal" && " (OG)"}
                    </span>
                  )}
                  {g.assisted_by_id && <span className="ml-1.5 text-xs text-muted-foreground">assist {nameOf(g.assisted_by_id)}</span>}
                </div>
                <button
                  type="button"
                  onClick={() => setGoals((gs) => gs.filter((x) => x.key !== g.key))}
                  className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
                  aria-label="Remove goal"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </Card>
        )}
        <Button type="button" variant="outline" className="h-11 w-full" onClick={() => setGoalSheet(true)} disabled={playingPlayers.length === 0}>
          <Plus className="size-4" /> Add goal
        </Button>
      </section>

      {/* Awards */}
      {awardTypes.map((at) => (
        <section key={at.id}>
          <SectionTitle>{at.name}</SectionTitle>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {playingPlayers.map((p) => (
              <Chip key={p.id} selected={awards[at.id]?.has(p.id) ?? false} onClick={() => toggleAward(at.id, p.id)} accent>
                {p.display_name}
              </Chip>
            ))}
          </div>
          {playingPlayers.length === 0 && <p className="text-sm text-muted-foreground">Pick who played first.</p>}
        </section>
      ))}

      {/* Sticky save: thumb-reachable above the bottom nav */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border/60 bg-background/90 p-3 backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
        <div className="mx-auto max-w-lg">
          <Button type="button" className="h-12 w-full text-base" onClick={onSave} disabled={submit.isPending || playing.size === 0}>
            {submit.isPending ? "Saving…" : isEdit ? "Save changes" : "Save result"}
          </Button>
        </div>
      </div>

      <GoalSheet open={goalSheet} onOpenChange={setGoalSheet} players={playingPlayers} onAdd={addGoal} />
    </div>
  );
}

function ScoreStepper({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-col items-center p-4">
      <span className="mb-2 max-w-full truncate text-xs font-medium text-muted-foreground">{label}</span>
      <span className="tnum text-5xl font-semibold tracking-tighter">{value}</span>
      <div className="mt-3 flex gap-2">
        <StepButton onClick={() => onChange(Math.max(0, value - 1))} aria-label={`${label} minus one`}><Minus className="size-5" /></StepButton>
        <StepButton onClick={() => onChange(value + 1)} aria-label={`${label} plus one`}><Plus className="size-5" /></StepButton>
      </div>
    </div>
  );
}

function StepButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="flex size-12 items-center justify-center rounded-full bg-muted text-foreground transition-colors active:bg-accent"
    />
  );
}

function Chip({ selected, onClick, children, accent }: { selected: boolean; onClick: () => void; children: React.ReactNode; accent?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "h-12 truncate rounded-xl px-2 text-sm font-medium ring-1 transition-all active:scale-[0.97]",
        selected
          ? accent
            ? "bg-primary text-primary-foreground ring-primary"
            : "bg-foreground text-background ring-foreground"
          : "bg-card text-muted-foreground ring-border/60 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function GoalSheet({
  open,
  onOpenChange,
  players,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  players: Schema["PlayerSummary"][];
  onAdd: (g: Omit<Goal, "key">) => void;
}) {
  const [scorer, setScorer] = useState<number | null>(null);
  const [kind, setKind] = useState<Goal["event_type"]>("goal");

  function reset() {
    setScorer(null);
    setKind("goal");
  }

  return (
    <Sheet open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <SheetHeader className="text-left">
          <SheetTitle>{scorer === null ? "Who scored?" : `Assist for ${players.find((p) => p.id === scorer)?.display_name}?`}</SheetTitle>
        </SheetHeader>
        <div className="px-4">
          {scorer === null ? (
            <>
              <div className="grid grid-cols-3 gap-2">
                {players.map((p) => (
                  <Chip key={p.id} selected={false} onClick={() => { setKind("goal"); setScorer(p.id); }}>{p.display_name}</Chip>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="ghost" className="h-11" onClick={() => { onAdd({ event_type: "opp_own_goal", scorer_id: null, assisted_by_id: null }); reset(); }}>
                  Opposition own goal
                </Button>
                <Button variant="ghost" className="h-11 text-rose-600" onClick={() => setKind("own_goal")}>
                  Our own goal…
                </Button>
              </div>
              {kind === "own_goal" && (
                <div className="mt-4">
                  <p className="mb-2 text-sm text-muted-foreground">Whose own goal?</p>
                  <div className="grid grid-cols-3 gap-2">
                    {players.map((p) => (
                      <Chip key={p.id} selected={false} onClick={() => { onAdd({ event_type: "own_goal", scorer_id: p.id, assisted_by_id: null }); reset(); }}>
                        {p.display_name}
                      </Chip>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2">
                {players.filter((p) => p.id !== scorer).map((p) => (
                  <Chip key={p.id} selected={false} onClick={() => { onAdd({ event_type: "goal", scorer_id: scorer, assisted_by_id: p.id }); reset(); }}>
                    {p.display_name}
                  </Chip>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="outline" className="h-11" onClick={() => { onAdd({ event_type: "goal", scorer_id: scorer, assisted_by_id: null }); reset(); }}>
                  No assist
                </Button>
                <Button variant="ghost" className="h-11" onClick={() => setScorer(null)}>Back</Button>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
