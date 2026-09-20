"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { toLocalInput, VENUE_LABEL, STATUS_LABEL } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Card } from "@/components/stat-card";

type Fixture = Schema["FixtureDetail"];

function defaultKickoff() {
  const d = new Date();
  d.setDate(d.getDate() + ((6 - d.getDay() + 7) % 7 || 7)); // next Saturday
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T10:00`;
}

export function FixtureForm({ fixture }: { fixture?: Fixture }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { teamSeason, base } = useTeam();
  const competitions = $api.useQuery("get", "/api/v1/competitions");
  const teams = $api.useQuery("get", "/api/v1/teams");

  const [competitionId, setCompetitionId] = useState(fixture ? String(fixture.competition.id) : "");
  const [teamId, setTeamId] = useState(fixture ? String(fixture.opposition.id) : "");
  const [newTeam, setNewTeam] = useState("");
  const [kickoff, setKickoff] = useState(fixture ? toLocalInput(fixture.kickoff_at) : defaultKickoff());
  const [venue, setVenue] = useState<Schema["Venue"]>(fixture?.venue ?? "home");
  const [status, setStatus] = useState<Schema["FixtureStatus"]>(fixture?.status ?? "scheduled");
  const [matchNumber, setMatchNumber] = useState(fixture?.match_number ? String(fixture.match_number) : "");
  const [venueNotes, setVenueNotes] = useState(fixture?.venue_notes ?? "");
  const [notes, setNotes] = useState(fixture?.notes ?? "");

  const create = $api.useMutation("post", "/api/v1/fixtures");
  const update = $api.useMutation("patch", "/api/v1/fixtures/{fixture_id}");
  const createTeam = $api.useMutation("post", "/api/v1/teams");
  const pending = create.isPending || update.isPending || createTeam.isPending;

  const activeCompetitions = (competitions.data ?? []).filter((c) => c.is_active || c.id === fixture?.competition.id);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!teamSeason) return;
    try {
      let oppositionId = Number(teamId);
      if (teamId === "__new__") {
        const t = await createTeam.mutateAsync({ body: { name: newTeam.trim() } });
        oppositionId = t.id;
        qc.invalidateQueries({ queryKey: ["get", "/api/v1/teams"] });
      }
      const common = {
        competition_id: Number(competitionId),
        opposition_team_id: oppositionId,
        // Kick-off is stored as UK wall-clock time (no zone), exactly as typed.
        kickoff_at: kickoff.length === 16 ? `${kickoff}:00` : kickoff,
        venue,
        venue_notes: venueNotes || null,
        notes: notes || null,
        match_number: matchNumber ? Number(matchNumber) : null,
      };
      let saved: Fixture;
      if (fixture) {
        saved = await update.mutateAsync({
          params: { path: { fixture_id: fixture.id } },
          body: { ...common, status: fixture.status === "played" || fixture.status === "live" ? undefined : status },
        });
      } else {
        saved = await create.mutateAsync({ body: { ...common, team_season_id: teamSeason.id, status } });
      }
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      toast.success(fixture ? "Fixture updated" : "Fixture added");
      router.replace(`${base}/fixtures/${saved.id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Card className="space-y-5 p-5">
        <Field label="Competition">
          <Select value={competitionId} onValueChange={setCompetitionId} required>
            <SelectTrigger className="h-11 w-full">
              <SelectValue placeholder="Choose…" />
            </SelectTrigger>
            <SelectContent>
              {activeCompetitions.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Opposition">
          <Select value={teamId} onValueChange={setTeamId} required>
            <SelectTrigger className="h-11 w-full">
              <SelectValue placeholder="Choose…" />
            </SelectTrigger>
            <SelectContent>
              {(teams.data ?? []).map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.name}
                </SelectItem>
              ))}
              <SelectItem value="__new__">+ New team…</SelectItem>
            </SelectContent>
          </Select>
          {teamId === "__new__" && (
            <Input
              className="mt-2 h-11"
              placeholder="Team name"
              value={newTeam}
              onChange={(e) => setNewTeam(e.target.value)}
              required
              autoFocus
            />
          )}
        </Field>

        <Field label="Kick-off">
          <Input type="datetime-local" className="h-11" value={kickoff} onChange={(e) => setKickoff(e.target.value)} required />
        </Field>

        <Field label="Venue">
          <ToggleGroup type="single" value={venue} onValueChange={(v) => v && setVenue(v as Schema["Venue"])} className="w-full" variant="outline">
            {(["home", "away", "neutral"] as const).map((v) => (
              <ToggleGroupItem key={v} value={v} className="h-11 flex-1">
                {VENUE_LABEL[v]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <Input className="mt-2 h-11" placeholder="Pitch / meeting point (optional)" value={venueNotes} onChange={(e) => setVenueNotes(e.target.value)} />
        </Field>
      </Card>

      <Card className="space-y-5 p-5">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Match no.">
            <Input type="number" inputMode="numeric" min={1} className="h-11" placeholder="Auto" value={matchNumber} onChange={(e) => setMatchNumber(e.target.value)} />
          </Field>
          {fixture?.status !== "played" && fixture?.status !== "live" && (
            <Field label="Status">
              <Select value={status} onValueChange={(v) => setStatus(v as Schema["FixtureStatus"])}>
                <SelectTrigger className="h-11 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(["scheduled", "postponed", "cancelled", "abandoned"] as const).map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}
        </div>
        <Field label="Notes">
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Anything worth remembering" />
        </Field>
      </Card>

      <div className="sticky bottom-20 z-20 md:static">
        <Button type="submit" className="h-12 w-full shadow-lg md:w-auto md:shadow-none" disabled={pending || !competitionId || !teamId}>
          {pending ? "Saving…" : fixture ? "Save changes" : "Add fixture"}
        </Button>
      </div>
    </form>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}
