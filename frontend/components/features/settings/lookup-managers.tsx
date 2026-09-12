"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/features/fixtures/fixture-form";

const TYPES: Schema["CompetitionType"][] = ["league", "cup", "friendly", "tournament"];

export function CompetitionsManager() {
  const qc = useQueryClient();
  const list = $api.useQuery("get", "/api/v1/competitions");
  const create = $api.useMutation("post", "/api/v1/competitions");
  const update = $api.useMutation("patch", "/api/v1/competitions/{competition_id}");
  const remove = $api.useMutation("delete", "/api/v1/competitions/{competition_id}");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<Schema["CompetitionType"]>("league");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["get", "/api/v1/competitions"] });

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({ body: { name: name.trim(), type } });
      invalidate();
      setOpen(false);
      setName("");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function toggleActive(id: number, is_active: boolean) {
    try {
      await update.mutateAsync({ params: { path: { competition_id: id } }, body: { is_active } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete(id: number) {
    try {
      await remove.mutateAsync({ params: { path: { competition_id: id } } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Plus className="size-4" /> New competition</Button>
      </div>
      <Card className="divide-y divide-border/40">
        {(list.data ?? []).map((c) => (
          <div key={c.id} className="flex min-h-14 items-center gap-3 px-4 py-2 text-sm">
            <span className={c.is_active ? "font-medium" : "text-muted-foreground line-through"}>{c.name}</span>
            <Badge variant="outline" className="capitalize">{c.type}</Badge>
            <span className="flex-1" />
            <Switch checked={c.is_active} onCheckedChange={(v) => toggleActive(c.id, v)} aria-label="Active" />
            <button type="button" onClick={() => onDelete(c.id)} className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-destructive" aria-label="Delete">
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
      </Card>
      <p className="mt-2 text-xs text-muted-foreground">League-only stats use every competition of type &ldquo;league&rdquo;.</p>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New competition</DialogTitle></DialogHeader>
          <form onSubmit={onCreate} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} placeholder="Hampshire Cup" required autoFocus /></Field>
            <Field label="Type">
              <Select value={type} onValueChange={(v) => setType(v as Schema["CompetitionType"])}>
                <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending}>Add</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function TeamsManager() {
  const qc = useQueryClient();
  const list = $api.useQuery("get", "/api/v1/teams");
  const create = $api.useMutation("post", "/api/v1/teams");
  const update = $api.useMutation("patch", "/api/v1/teams/{team_id}");
  const remove = $api.useMutation("delete", "/api/v1/teams/{team_id}");
  const [editing, setEditing] = useState<Schema["TeamRead"] | "new" | null>(null);
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["get", "/api/v1/teams"] });

  function openFor(t: Schema["TeamRead"] | "new") {
    setEditing(t);
    setName(t === "new" ? "" : t.name);
    setShortName(t === "new" ? "" : (t.short_name ?? ""));
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    const body = { name: name.trim(), short_name: shortName.trim() || null };
    try {
      if (editing === "new") await create.mutateAsync({ body });
      else if (editing) await update.mutateAsync({ params: { path: { team_id: editing.id } }, body });
      invalidate();
      setEditing(null);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete(id: number) {
    try {
      await remove.mutateAsync({ params: { path: { team_id: id } } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="outline" onClick={() => openFor("new")}><Plus className="size-4" /> New team</Button>
      </div>
      <Card className="divide-y divide-border/40">
        {(list.data ?? []).map((t) => (
          <div key={t.id} className="flex min-h-14 items-center gap-3 px-4 py-2 text-sm">
            <button type="button" onClick={() => openFor(t)} className="min-w-0 flex-1 text-left">
              <span className="font-medium">{t.name}</span>
              {t.short_name && <span className="ml-2 text-xs text-muted-foreground">{t.short_name}</span>}
            </button>
            <button type="button" onClick={() => onDelete(t.id)} className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-destructive" aria-label="Delete">
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
        {list.data && !list.data.length && <p className="p-4 text-sm text-muted-foreground">Opposition teams appear here as you add fixtures.</p>}
      </Card>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing === "new" ? "New team" : "Edit team"}</DialogTitle></DialogHeader>
          <form onSubmit={onSave} className="space-y-4">
            <Field label="Name"><Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></Field>
            <Field label="Short name"><Input className="h-11" value={shortName} onChange={(e) => setShortName(e.target.value)} placeholder="Shown in tight spaces" /></Field>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending || update.isPending}>Save</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
