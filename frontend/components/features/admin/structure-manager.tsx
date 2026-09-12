"use client";

import Link from "next/link";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { Card } from "@/components/stat-card";
import { SectionTitle } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/features/fixtures/fixture-form";

const SWATCHES = ["oklch(0.5 0.2 258)", "oklch(0.3 0.01 260)", "oklch(0.55 0.2 25)", "oklch(0.6 0.02 260)", "oklch(0.55 0.18 145)", "oklch(0.7 0.18 80)", "oklch(0.55 0.2 300)"];

/** Age groups and the teams inside them. Club admins can add both. */
export function StructureManager() {
  const qc = useQueryClient();
  const { isClubAdmin, me } = useMe();
  const cohorts = $api.useQuery("get", "/api/v1/cohorts");
  const teams = $api.useQuery("get", "/api/v1/club-teams");
  const createCohort = $api.useMutation("post", "/api/v1/cohorts");
  const createTeam = $api.useMutation("post", "/api/v1/club-teams");
  const updateTeam = $api.useMutation("patch", "/api/v1/club-teams/{team_id}");
  const [cohortOpen, setCohortOpen] = useState(false);
  const [teamOpen, setTeamOpen] = useState<number | null>(null); // cohort id
  const [editTeam, setEditTeam] = useState<Schema["ClubTeamRead"] | null>(null);
  const [name, setName] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [colour, setColour] = useState(SWATCHES[0]);
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/cohorts"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/club-teams"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/me"] });
  };

  async function onCohort(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createCohort.mutateAsync({ body: { name: name.trim(), birth_year_start: birthYear ? Number(birthYear) : null } });
      invalidate(); setCohortOpen(false); setName(""); setBirthYear("");
    } catch (err) { toast.error(errorMessage(err)); }
  }
  async function onTeam(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editTeam) {
        await updateTeam.mutateAsync({ params: { path: { team_id: editTeam.id } }, body: { name: name.trim(), colour } });
      } else if (teamOpen !== null) {
        await createTeam.mutateAsync({ body: { cohort_id: teamOpen, name: name.trim(), colour } });
      }
      invalidate(); setTeamOpen(null); setEditTeam(null); setName("");
    } catch (err) { toast.error(errorMessage(err)); }
  }

  const canAdminCohort = (id: number) => isClubAdmin || me.roles.some((r) => r.role === "admin" && r.scope_type === "cohort" && r.scope_id === id);

  return (
    <>
      {isClubAdmin && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" variant="outline" onClick={() => { setName(""); setCohortOpen(true); }}><Plus className="size-4" /> New age group</Button>
        </div>
      )}
      <div className="space-y-6">
        {(cohorts.data ?? []).map((c) => (
          <section key={c.id}>
            <div className="mb-2 flex items-center justify-between">
              <SectionTitle className="mb-0">{c.name}{c.birth_year_start ? ` · born ${c.birth_year_start}/${String(c.birth_year_start + 1).slice(2)}` : ""}</SectionTitle>
              <div className="flex gap-1">
                <Button asChild size="sm" variant="ghost"><Link href={`/cohorts/${c.id}`}>Overview</Link></Button>
                {canAdminCohort(c.id) && (
                  <Button size="sm" variant="ghost" onClick={() => { setName(""); setColour(SWATCHES[0]); setEditTeam(null); setTeamOpen(c.id); }}><Plus className="size-4" /> Team</Button>
                )}
              </div>
            </div>
            <Card className="divide-y divide-border/40">
              {(teams.data ?? []).filter((t) => t.cohort_id === c.id).map((t) => (
                <div key={t.id} className="flex min-h-14 items-center gap-3 px-4 py-2 text-sm">
                  <span className="size-3 rounded-full ring-1 ring-border" style={{ background: t.colour ?? "transparent" }} />
                  <Link href={`/${t.slug}`} className="font-medium hover:underline">{t.name}</Link>
                  <span className="text-xs text-muted-foreground">/{t.slug}</span>
                  <span className="flex-1" />
                  {canAdminCohort(c.id) && (
                    <Button size="sm" variant="ghost" onClick={() => { setEditTeam(t); setName(t.name); setColour(t.colour ?? SWATCHES[0]); setTeamOpen(c.id); }}>Edit</Button>
                  )}
                </div>
              ))}
              {teams.data && !teams.data.some((t) => t.cohort_id === c.id) && <p className="p-4 text-sm text-muted-foreground">No teams yet.</p>}
            </Card>
          </section>
        ))}
      </div>

      <Dialog open={cohortOpen} onOpenChange={setCohortOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New age group</DialogTitle></DialogHeader>
          <form onSubmit={onCohort} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} placeholder="Born 2017/18" required autoFocus /></Field>
            <Field label="School year starts (Sept)"><Input type="number" inputMode="numeric" className="h-11" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} placeholder="2017" /></Field>
            <p className="text-xs text-muted-foreground">Used to work out the age group each season (2017 → U10 in 2027/28).</p>
            <Button type="submit" className="h-11 w-full" disabled={createCohort.isPending}>Create</Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={teamOpen !== null} onOpenChange={(o) => { if (!o) { setTeamOpen(null); setEditTeam(null); } }}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editTeam ? `Edit ${editTeam.name}` : "New team"}</DialogTitle></DialogHeader>
          <form onSubmit={onTeam} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} placeholder="Greens" required autoFocus /></Field>
            <Field label="Colour">
              <Select value={colour} onValueChange={setColour}>
                <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SWATCHES.map((c) => (
                    <SelectItem key={c} value={c}><span className="flex items-center gap-2"><span className="size-3 rounded-full" style={{ background: c }} />{c}</span></SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Button type="submit" className="h-11 w-full" disabled={createTeam.isPending || updateTeam.isPending}>{editTeam ? "Save" : "Create"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
