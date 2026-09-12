"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/features/fixtures/fixture-form";

type TeamRec = Schema["CohortTeamRecord"];

export function MovePlayerDialog({
  open,
  onOpenChange,
  player,
  teams,
  fromTeamSeasonId,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  player: Schema["PlayerSummary"] | null;
  teams: TeamRec[];
  fromTeamSeasonId: number | null;
}) {
  const qc = useQueryClient();
  const [to, setTo] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [number, setNumber] = useState("");
  const move = $api.useMutation("post", "/api/v1/players/{player_id}/move");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!player || fromTeamSeasonId === null) return;
    try {
      await move.mutateAsync({
        params: { path: { player_id: player.id } },
        body: { from_team_season_id: fromTeamSeasonId, to_team_season_id: Number(to), left_at: date, squad_number: number ? Number(number) : null },
      });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/cohorts"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
      toast.success(`${player.display_name} moved`);
      onOpenChange(false);
      setTo("");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const options = teams.filter((t) => t.team_season_id !== fromTeamSeasonId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Move {player?.display_name}</DialogTitle></DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="To">
            <Select value={to} onValueChange={setTo} required>
              <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Choose a team" /></SelectTrigger>
              <SelectContent>
                {options.map((t) => <SelectItem key={t.team_season_id} value={String(t.team_season_id)}>{t.team_name}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="From"><Input type="date" className="h-11" value={date} onChange={(e) => setDate(e.target.value)} required /></Field>
            <Field label="New squad no."><Input type="number" inputMode="numeric" min={1} max={99} className="h-11" value={number} onChange={(e) => setNumber(e.target.value)} /></Field>
          </div>
          <p className="text-xs text-muted-foreground">Appearances and goals for the old team are kept; new ones count for the new team.</p>
          <Button type="submit" className="h-11 w-full" disabled={move.isPending || !to}>Move</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
