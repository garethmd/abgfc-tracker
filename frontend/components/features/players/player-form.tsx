"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/features/fixtures/fixture-form";
import { cn } from "@/lib/utils";

type Player = Schema["PlayerRead"];
type Member = Schema["SquadMemberRead"];

export function PlayerForm({ player, member, onSaved }: { player?: Player; member?: Member | null; onSaved?: (p: Player) => void }) {
  const qc = useQueryClient();
  const { team, teamSeason } = useTeam();
  const positions = $api.useQuery("get", "/api/v1/positions");
  // Existing players in the age group who aren't already in this squad - so a child moving
  // from another team, or re-joining, isn't created twice.
  const cohortPlayers = $api.useQuery(
    "get",
    "/api/v1/players",
    { params: { query: { cohort_id: team.cohort_id, include_left: false } } },
    { enabled: !player },
  );
  const squad = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/squad",
    { params: { path: { team_season_id: teamSeason?.id ?? 0 } } },
    { enabled: !player && !!teamSeason },
  );
  const inSquadIds = new Set((squad.data ?? []).map((m) => m.player.id));
  const candidates = (cohortPlayers.data ?? []).filter((p) => !inSquadIds.has(p.id));

  const [mode, setMode] = useState<"new" | "existing">("new");
  const [existingId, setExistingId] = useState("");
  const [firstName, setFirstName] = useState(player?.first_name ?? "");
  const [lastName, setLastName] = useState(player?.last_name ?? "");
  const [displayName, setDisplayName] = useState(player?.display_name ?? "");
  const [dob, setDob] = useState(player?.date_of_birth ?? "");
  const [notes, setNotes] = useState(player?.notes ?? "");
  const [hasLeft, setHasLeft] = useState(!!player?.left_date);
  const [leftDate, setLeftDate] = useState(player?.left_date ?? new Date().toISOString().slice(0, 10));
  const [inSquad, setInSquad] = useState(player ? !!member : true);
  const [number, setNumber] = useState(member?.squad_number ? String(member.squad_number) : "");
  const [positionId, setPositionId] = useState(member?.primary_position ? String(member.primary_position.id) : "none");

  const create = $api.useMutation("post", "/api/v1/players");
  const update = $api.useMutation("patch", "/api/v1/players/{player_id}");
  const upsertMember = $api.useMutation("put", "/api/v1/team-seasons/{team_season_id}/squad/{player_id}");
  const removeMember = $api.useMutation("delete", "/api/v1/team-seasons/{team_season_id}/squad/{player_id}");
  const pending = create.isPending || update.isPending || upsertMember.isPending || removeMember.isPending;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const squadBody = {
        squad_number: number ? Number(number) : null,
        primary_position_id: positionId === "none" ? null : Number(positionId),
      };
      let saved: Player;
      if (!player && mode === "existing") {
        if (!teamSeason) return;
        const chosen = candidates.find((p) => p.id === Number(existingId));
        if (!chosen) return;
        await upsertMember.mutateAsync({ params: { path: { team_season_id: teamSeason.id, player_id: chosen.id } }, body: squadBody });
        saved = chosen;
      } else {
        const body = {
          first_name: firstName.trim(),
          last_name: lastName.trim() || null,
          display_name: displayName.trim() || null,
          date_of_birth: dob || null,
          notes: notes || null,
        };
        if (player) {
          saved = await update.mutateAsync({ params: { path: { player_id: player.id } }, body: { ...body, left_date: hasLeft ? leftDate : null } });
        } else {
          saved = await create.mutateAsync({ body: { ...body, cohort_id: team.cohort_id } });
        }
        if (teamSeason) {
          if (inSquad) {
            await upsertMember.mutateAsync({ params: { path: { team_season_id: teamSeason.id, player_id: saved.id } }, body: squadBody });
          } else if (member) {
            await removeMember.mutateAsync({ params: { path: { team_season_id: teamSeason.id, player_id: saved.id } } });
          }
        }
      }
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/players"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
      toast.success(player ? "Player updated" : "Player added");
      onSaved?.(saved);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const showSquadFields = teamSeason && (player ? inSquad : mode === "existing" || inSquad);

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {!player && candidates.length > 0 && (
        <div className="flex rounded-lg bg-muted p-0.5 text-sm font-medium">
          {(["new", "existing"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn("h-9 flex-1 rounded-md transition-colors", mode === m ? "bg-background shadow-sm" : "text-muted-foreground")}
            >
              {m === "new" ? "New player" : "Already at the club"}
            </button>
          ))}
        </div>
      )}

      {!player && mode === "existing" ? (
        <Field label="Player">
          <Select value={existingId} onValueChange={setExistingId} required>
            <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Choose…" /></SelectTrigger>
            <SelectContent>
              {candidates.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.display_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <Field label="First name">
              <Input className="h-11" value={firstName} onChange={(e) => setFirstName(e.target.value)} required autoFocus={!player} />
            </Field>
            <Field label="Last name">
              <Input className="h-11" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </Field>
          </div>
          <Field label="Shown as">
            <Input className="h-11" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={firstName || "Defaults to first name"} />
          </Field>
          <Field label="Date of birth">
            <Input type="date" className="h-11" value={dob} onChange={(e) => setDob(e.target.value)} />
          </Field>
        </>
      )}

      {teamSeason && (
        <div className="space-y-4 rounded-xl bg-muted/40 p-4">
          {(player || mode === "new") && (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">In the {team.name} {teamSeason.season.name} squad</span>
              <Switch checked={inSquad} onCheckedChange={setInSquad} />
            </div>
          )}
          {showSquadFields && (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Squad no.">
                <Input type="number" inputMode="numeric" min={1} max={99} className="h-11 bg-background" value={number} onChange={(e) => setNumber(e.target.value)} />
              </Field>
              <Field label="Position">
                <Select value={positionId} onValueChange={setPositionId}>
                  <SelectTrigger className="h-11 w-full bg-background"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">—</SelectItem>
                    {(positions.data ?? []).map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          )}
        </div>
      )}

      {player && (
        <div className="space-y-4 rounded-xl bg-muted/40 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Left the club</p>
              <p className="text-xs text-muted-foreground">Their stats are kept.</p>
            </div>
            <Switch checked={hasLeft} onCheckedChange={setHasLeft} />
          </div>
          {hasLeft && <Input type="date" className="h-11 bg-background" value={leftDate} onChange={(e) => setLeftDate(e.target.value)} />}
        </div>
      )}

      {(player || mode === "new") && (
        <Field label="Notes">
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
      )}

      <Button
        type="submit"
        className="h-12 w-full"
        disabled={pending || (mode === "existing" && !player ? !existingId : !firstName.trim())}
      >
        {pending ? "Saving…" : player ? "Save changes" : mode === "existing" ? "Add to squad" : "Add player"}
      </Button>
    </form>
  );
}
