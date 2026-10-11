"use client";

import Link from "next/link";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Pencil, Plus, Shield, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema, invalidatePath } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Field } from "@/components/features/fixtures/fixture-form";

type Team = Schema["TeamRead"];

/** Every team we play, with the head-to-head behind each one. Coaches also add, rename,
 *  merge and delete here - this is the only place opposition is maintained. */
export function OppositionList() {
  const qc = useQueryClient();
  const { base, canEdit } = useTeam();
  const list = $api.useQuery("get", "/api/v1/teams");
  const create = $api.useMutation("post", "/api/v1/teams");
  const update = $api.useMutation("patch", "/api/v1/teams/{team_id}");
  const remove = $api.useMutation("delete", "/api/v1/teams/{team_id}");
  const merge = $api.useMutation("post", "/api/v1/teams/{team_id}/merge");

  const [editing, setEditing] = useState<Team | "new" | null>(null);
  const [deleting, setDeleting] = useState<Team | null>(null);
  const [merging, setMerging] = useState<{ from: Team; into: Team } | null>(null);
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [homeGround, setHomeGround] = useState("");
  const [mergeInto, setMergeInto] = useState("");

  const invalidate = () => invalidatePath(qc, "/api/v1/teams");

  function openFor(t: Team | "new") {
    setEditing(t);
    setName(t === "new" ? "" : t.name);
    setShortName(t === "new" ? "" : (t.short_name ?? ""));
    setHomeGround(t === "new" ? "" : (t.home_ground ?? ""));
    setMergeInto("");
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    const body = {
      name: name.trim(),
      short_name: shortName.trim() || null,
      home_ground: homeGround.trim() || null,
    };
    try {
      if (editing === "new") await create.mutateAsync({ body });
      else if (editing) await update.mutateAsync({ params: { path: { team_id: editing.id } }, body });
      invalidate();
      setEditing(null);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await remove.mutateAsync({ params: { path: { team_id: deleting.id } } });
      invalidate();
      toast.success(`${deleting.name} removed`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(null);
    }
  }

  async function onMerge() {
    if (!merging) return;
    try {
      await merge.mutateAsync({
        params: { path: { team_id: merging.from.id } },
        body: { into_team_id: merging.into.id },
      });
      invalidatePath(qc, "/api/v1/fixtures");
      invalidate();
      toast.success(`Merged into ${merging.into.name}`);
      setMerging(null);
      setEditing(null);
    } catch (err) {
      toast.error(errorMessage(err));
      setMerging(null);
    }
  }

  if (list.isPending) return <Skeleton className="h-96 rounded-xl" />;
  if (list.error) return <ErrorState error={list.error} onRetry={() => list.refetch()} />;

  const teams = list.data;
  const target = (id: string) => teams.find((t) => t.id === Number(id));

  return (
    <>
      {canEdit && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" onClick={() => openFor("new")}>
            <Plus className="size-4" /> Add
          </Button>
        </div>
      )}

      {!teams.length ? (
        <EmptyState
          icon={Shield}
          title="No opposition yet"
          description="Teams appear here as fixtures are added, or add one now."
        />
      ) : (
        <Card className="divide-y divide-border/40 overflow-hidden">
          {teams.map((t) => (
            <div key={t.id} className="flex min-h-14 items-center">
              <Link
                href={`${base}/opposition/${t.id}`}
                className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 hover:bg-accent/50 active:bg-accent"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{t.name}</span>
                  {(t.short_name || t.home_ground) && (
                    <span className="block truncate text-xs text-muted-foreground">
                      {[t.short_name, t.home_ground].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </span>
                {t.club_team_id && (
                  <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                    ABGFC
                  </span>
                )}
                {!canEdit && <ChevronRight className="size-4 shrink-0 text-muted-foreground" />}
              </Link>
              {canEdit && (
                <button
                  type="button"
                  onClick={() => openFor(t)}
                  aria-label={`Edit ${t.name}`}
                  className="flex size-11 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
                >
                  <Pencil className="size-4" />
                </button>
              )}
            </div>
          ))}
        </Card>
      )}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing === "new" ? "Add opposition" : "Edit opposition"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSave} className="space-y-4">
            <Field label="Name">
              <Input className="h-11" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </Field>
            <Field label="Short name">
              <Input className="h-11" value={shortName} onChange={(e) => setShortName(e.target.value)} placeholder="Shown in tight spaces" />
            </Field>
            <Field label="Home ground">
              <Input className="h-11" value={homeGround} onChange={(e) => setHomeGround(e.target.value)} placeholder="Where they play at home" />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Filled in on away fixtures against them as they&apos;re created. Changing it never
                moves a fixture already arranged.
              </p>
            </Field>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending || update.isPending}>
              Save
            </Button>
          </form>

          {editing !== "new" && editing && (
            <>
              <div className="mt-2 space-y-2 rounded-lg bg-muted/40 p-3">
                <p className="text-xs font-medium">Duplicate of another team?</p>
                <div className="flex gap-2">
                  <Select value={mergeInto} onValueChange={setMergeInto}>
                    <SelectTrigger className="h-10 flex-1"><SelectValue placeholder="Merge into…" /></SelectTrigger>
                    <SelectContent>
                      {teams.filter((t) => t.id !== editing.id).map((t) => (
                        <SelectItem key={t.id} value={String(t.id)}>{t.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10"
                    disabled={!mergeInto}
                    onClick={() => {
                      const into = target(mergeInto);
                      if (into) setMerging({ from: editing, into });
                    }}
                  >
                    Merge
                  </Button>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Fixtures against this team move to the other one and this entry is removed.
                </p>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-11 text-destructive"
                  onClick={() => setDeleting(editing)}
                >
                  <Trash2 className="size-4" /> Delete
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {deleting?.name}?</DialogTitle>
            <DialogDescription>
              Only possible while no fixture refers to them. If one does, merge them into the
              right team instead.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setDeleting(null)}>Keep</Button>
            <Button variant="destructive" className="h-11" onClick={onDelete} disabled={remove.isPending}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={merging !== null} onOpenChange={(o) => !o && setMerging(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge {merging?.from.name} into {merging?.into.name}?</DialogTitle>
            <DialogDescription>
              Every fixture against {merging?.from.name} moves across, and {merging?.from.name} is
              deleted. This can&apos;t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setMerging(null)}>Cancel</Button>
            <Button className="h-11" onClick={onMerge} disabled={merge.isPending}>Merge</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
