"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
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

export function AwardTypesManager() {
  const qc = useQueryClient();
  const { team, canEdit } = useTeam();
  const list = $api.useQuery("get", "/api/v1/award-types", { params: { query: { club_team_id: team.id, active_only: false } } });
  const create = $api.useMutation("post", "/api/v1/award-types");
  const update = $api.useMutation("patch", "/api/v1/award-types/{award_type_id}");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/award-types"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
  };

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({ body: { name: name.trim(), club_team_id: team.id } });
      invalidate();
      setOpen(false);
      setName("");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function toggle(id: number, is_active: boolean) {
    try {
      await update.mutateAsync({ params: { path: { award_type_id: id } }, body: { is_active } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <>
      {canEdit && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Plus className="size-4" /> New award</Button>
        </div>
      )}
      <Card className="divide-y divide-border/40">
        {(list.data ?? []).map((a) => (
          <div key={a.id} className="flex min-h-14 items-center gap-3 px-4 py-2 text-sm">
            <span className={a.is_active ? "font-medium" : "text-muted-foreground line-through"}>{a.name}</span>
            <Badge variant="outline">{a.club_team_id === null ? "Club" : team.name}</Badge>
            <span className="flex-1" />
            {canEdit && a.club_team_id !== null && (
              <Switch checked={a.is_active} onCheckedChange={(v) => toggle(a.id, v)} aria-label="Active" />
            )}
          </div>
        ))}
      </Card>
      <p className="mt-2 text-xs text-muted-foreground">Awards are given per match on the result screen and counted on the leaderboard. Club-wide awards are managed by the club admin.</p>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New {team.name} award</DialogTitle></DialogHeader>
          <form onSubmit={onCreate} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} placeholder="Most improved" required autoFocus /></Field>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending}>Add</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
