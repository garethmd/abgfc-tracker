"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/features/fixtures/fixture-form";

type Player = Schema["PlayerRead"];
type Member = Schema["SquadMemberRead"];

export function PlayerForm({ player, member, onSaved }: { player?: Player; member?: Member | null; onSaved?: (p: Player) => void }) {
  const qc = useQueryClient();
  const { season } = useSeason();
  const positions = $api.useQuery("get", "/api/v1/positions");

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
  const upsertMember = $api.useMutation("put", "/api/v1/seasons/{season_id}/squad/{player_id}");
  const removeMember = $api.useMutation("delete", "/api/v1/seasons/{season_id}/squad/{player_id}");
  const pending = create.isPending || update.isPending || upsertMember.isPending || removeMember.isPending;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const body = {
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
        display_name: displayName.trim() || null,
        date_of_birth: dob || null,
        notes: notes || null,
      };
      let saved: Player;
      if (player) {
        saved = await update.mutateAsync({ params: { path: { player_id: player.id } }, body: { ...body, left_date: hasLeft ? leftDate : null } });
      } else {
        saved = await create.mutateAsync({ body });
      }
      if (season) {
        if (inSquad) {
          await upsertMember.mutateAsync({
            params: { path: { season_id: season.id, player_id: saved.id } },
            body: { squad_number: number ? Number(number) : null, primary_position_id: positionId === "none" ? null : Number(positionId) },
          });
        } else if (member) {
          await removeMember.mutateAsync({ params: { path: { season_id: season.id, player_id: saved.id } } });
        }
      }
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/players"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/seasons"] });
      toast.success(player ? "Player updated" : "Player added");
      onSaved?.(saved);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
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

      {season && (
        <div className="space-y-4 rounded-xl bg-muted/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">In the {season.name} squad</span>
            <Switch checked={inSquad} onCheckedChange={setInSquad} />
          </div>
          {inSquad && (
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

      <Field label="Notes">
        <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>

      <Button type="submit" className="h-12 w-full" disabled={pending || !firstName.trim()}>
        {pending ? "Saving…" : player ? "Save changes" : "Add player"}
      </Button>
    </form>
  );
}
