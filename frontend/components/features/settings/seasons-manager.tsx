"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage } from "@/lib/api/client";
import { useSeason } from "@/lib/season-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/features/fixtures/fixture-form";

function suggestName() {
  const y = new Date().getFullYear();
  const start = new Date().getMonth() >= 6 ? y : y - 1;
  return `${start}/${String(start + 1).slice(2)}`;
}

export function SeasonsManager() {
  const qc = useQueryClient();
  const { seasons, setSeasonId } = useSeason();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(suggestName());
  const [minutes, setMinutes] = useState("50");
  const create = $api.useMutation("post", "/api/v1/seasons");
  const makeCurrent = $api.useMutation("post", "/api/v1/seasons/{season_id}/make-current");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["get", "/api/v1/seasons"] });

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const s = await create.mutateAsync({ body: { name: name.trim(), match_minutes: Number(minutes) } });
      invalidate();
      setSeasonId(s.id);
      setOpen(false);
      toast.success(`Season ${s.name} created`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onMakeCurrent(id: number) {
    try {
      await makeCurrent.mutateAsync({ params: { path: { season_id: id } } });
      invalidate();
      setSeasonId(id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Plus className="size-4" /> New season</Button>
      </div>
      <Card className="divide-y divide-border/40">
        {seasons.map((s) => (
          <div key={s.id} className="flex min-h-14 items-center gap-3 px-4 py-2 text-sm">
            <span className="tnum font-medium">{s.name}</span>
            <span className="text-xs text-muted-foreground">{s.match_minutes} min</span>
            <span className="flex-1" />
            {s.is_current ? (
              <Badge variant="secondary"><Check className="size-3" /> Current</Badge>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => onMakeCurrent(s.id)}>Make current</Button>
            )}
          </div>
        ))}
        {!seasons.length && <p className="p-4 text-sm text-muted-foreground">No seasons yet.</p>}
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New season</DialogTitle></DialogHeader>
          <form onSubmit={onCreate} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} placeholder="2027/28" required /></Field>
            <Field label="Match length (minutes)"><Input type="number" inputMode="numeric" min={10} max={120} className="h-11" value={minutes} onChange={(e) => setMinutes(e.target.value)} /></Field>
            <p className="text-xs text-muted-foreground">Players are added per season from the Squad page; nothing is copied automatically.</p>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending}>Create season</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
