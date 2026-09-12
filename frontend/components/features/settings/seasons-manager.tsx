"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/features/fixtures/fixture-form";

function suggestName(latest?: string) {
  if (latest && /^\d{4}\/\d{2}$/.test(latest)) {
    const start = Number(latest.slice(0, 4)) + 1;
    return `${start}/${String(start + 1).slice(2)}`;
  }
  const y = new Date().getFullYear();
  const start = new Date().getMonth() >= 6 ? y : y - 1;
  return `${start}/${String(start + 1).slice(2)}`;
}

export function SeasonsManager() {
  const qc = useQueryClient();
  const { team, teamSeason, teamSeasons, setTeamSeasonId, canEdit } = useTeam();
  const [open, setOpen] = useState(false);
  const latest = teamSeasons[0];
  const [name, setName] = useState(suggestName(latest?.season.name));
  const [minutes, setMinutes] = useState(String(latest?.match_minutes ?? 50));
  const [format, setFormat] = useState(latest?.format ?? "7v7");
  const [copySquad, setCopySquad] = useState(true);
  const start = $api.useMutation("post", "/api/v1/club-teams/{team_id}/seasons");
  const makeCurrent = $api.useMutation("post", "/api/v1/team-seasons/{team_season_id}/make-current");
  const update = $api.useMutation("patch", "/api/v1/team-seasons/{team_season_id}");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/club-teams"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/me"] });
  };

  async function onStart(e: React.FormEvent) {
    e.preventDefault();
    try {
      const ts = await start.mutateAsync({
        params: { path: { team_id: team.id } },
        body: {
          season_name: name.trim(),
          match_minutes: Number(minutes),
          format: format || null,
          copy_squad_from_team_season_id: copySquad && latest ? latest.id : null,
        },
      });
      invalidate();
      setTeamSeasonId(ts.id);
      setOpen(false);
      toast.success(`${team.name} ${ts.season.name} started${ts.age_group ? ` (${ts.age_group})` : ""}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onMakeCurrent(id: number) {
    try {
      await makeCurrent.mutateAsync({ params: { path: { team_season_id: id } } });
      invalidate();
      setTeamSeasonId(id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onMinutes(id: number, value: string) {
    const n = Number(value);
    if (!n || n < 10) return;
    try {
      await update.mutateAsync({ params: { path: { team_season_id: id } }, body: { match_minutes: n } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <>
      {canEdit && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Plus className="size-4" /> Start next season</Button>
        </div>
      )}
      <Card className="divide-y divide-border/40">
        {teamSeasons.map((s) => (
          <div key={s.id} className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-sm">
            <span className="tnum font-medium">{s.season.name}</span>
            <span className="text-xs text-muted-foreground">{[s.age_group, s.format].filter(Boolean).join(" · ")}</span>
            <span className="flex-1" />
            {canEdit ? (
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Input
                  type="number"
                  inputMode="numeric"
                  min={10}
                  max={120}
                  defaultValue={s.match_minutes}
                  onBlur={(e) => Number(e.target.value) !== s.match_minutes && onMinutes(s.id, e.target.value)}
                  className="h-8 w-16 text-right"
                />
                min
              </label>
            ) : (
              <span className="text-xs text-muted-foreground">{s.match_minutes} min</span>
            )}
            {s.is_current ? (
              <Badge variant="secondary"><Check className="size-3" /> Current</Badge>
            ) : canEdit ? (
              <Button size="sm" variant="ghost" onClick={() => onMakeCurrent(s.id)}>Make current</Button>
            ) : null}
            {s.id === teamSeason?.id && !s.is_current && <span className="text-xs text-muted-foreground">viewing</span>}
          </div>
        ))}
        {!teamSeasons.length && <p className="p-4 text-sm text-muted-foreground">No seasons yet.</p>}
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Start {team.name}&apos; next season</DialogTitle></DialogHeader>
          <form onSubmit={onStart} className="space-y-4">
            <Field label="Season"><Input className="h-11 tnum" value={name} onChange={(e) => setName(e.target.value)} placeholder="2027/28" required /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Format"><Input className="h-11" value={format} onChange={(e) => setFormat(e.target.value)} placeholder="9v9" /></Field>
              <Field label="Match length (min)"><Input type="number" inputMode="numeric" min={10} max={120} className="h-11" value={minutes} onChange={(e) => setMinutes(e.target.value)} /></Field>
            </div>
            {latest && (
              <div className="flex items-center justify-between rounded-lg bg-muted/40 p-3">
                <div>
                  <p className="text-sm font-medium">Copy the {latest.season.name} squad</p>
                  <p className="text-xs text-muted-foreground">Players who haven&apos;t left, with their numbers.</p>
                </div>
                <Switch checked={copySquad} onCheckedChange={setCopySquad} />
              </div>
            )}
            <p className="text-xs text-muted-foreground">The age group (U10 → U11) is worked out from the cohort automatically.</p>
            <Button type="submit" className="h-11 w-full" disabled={start.isPending}>Start season</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
