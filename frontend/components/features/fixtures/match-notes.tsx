"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { MessageSquareText, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { formatDate, formatTime, toLocalInput } from "@/lib/format";
import { SectionTitle } from "@/components/page-header";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field } from "@/components/features/fixtures/fixture-form";

type Note = Schema["MatchNoteRead"];

/** WhatsApp match reports pasted onto a fixture. */
export function MatchNotes({ fixtureId, canEdit }: { fixtureId: number; canEdit: boolean }) {
  const qc = useQueryClient();
  const notes = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}/notes", { params: { path: { fixture_id: fixtureId } } });
  const create = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/notes");
  const update = $api.useMutation("patch", "/api/v1/fixtures/{fixture_id}/notes/{note_id}");
  const remove = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/notes/{note_id}");
  const [editing, setEditing] = useState<Note | "new" | null>(null);
  const [body, setBody] = useState("");
  const [author, setAuthor] = useState("");
  const [sentAt, setSentAt] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures/{fixture_id}/notes"] });

  function open(n: Note | "new") {
    setEditing(n);
    setBody(n === "new" ? "" : n.body);
    setAuthor(n === "new" ? "" : (n.author ?? ""));
    setSentAt(n === "new" ? "" : n.sent_at ? toLocalInput(n.sent_at) : "");
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    const payload = { body, author: author.trim() || null, sent_at: sentAt ? `${sentAt}:00` : null };
    try {
      if (editing === "new") await create.mutateAsync({ params: { path: { fixture_id: fixtureId } }, body: payload });
      else if (editing) await update.mutateAsync({ params: { path: { fixture_id: fixtureId, note_id: editing.id } }, body: payload });
      invalidate();
      setEditing(null);
      toast.success(editing === "new" ? "Report added" : "Report updated");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete(n: Note) {
    if (!confirm("Delete this report?")) return;
    try {
      await remove.mutateAsync({ params: { path: { fixture_id: fixtureId, note_id: n.id } } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const list = notes.data ?? [];
  if (!canEdit && list.length === 0) return null;

  return (
    <section className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <SectionTitle className="mb-0">Match report</SectionTitle>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => open("new")}>
            <Plus className="size-4" /> Add
          </Button>
        )}
      </div>
      {list.length === 0 ? (
        <p className="text-sm text-muted-foreground">Paste the WhatsApp report here after the game so it&apos;s kept with the match.</p>
      ) : (
        <div className="space-y-3">
          {list.map((n) => (
            <Card key={n.id} className="p-4">
              <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                <MessageSquareText className="size-3.5" />
                <span className="font-medium text-foreground">{n.author ?? "Match report"}</span>
                {n.sent_at && <span>· {formatDate(n.sent_at)}, {formatTime(n.sent_at)}</span>}
                {n.added_by && <span className="hidden sm:inline">· added by {n.added_by}</span>}
                {canEdit && (
                  <span className="ml-auto flex gap-1">
                    <button type="button" onClick={() => open(n)} className="flex size-8 items-center justify-center rounded-md hover:bg-accent hover:text-foreground" aria-label="Edit"><Pencil className="size-3.5" /></button>
                    <button type="button" onClick={() => onDelete(n)} className="flex size-8 items-center justify-center rounded-md hover:bg-accent hover:text-destructive" aria-label="Delete"><Trash2 className="size-3.5" /></button>
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{n.body}</p>
            </Card>
          ))}
        </div>
      )}

      <Sheet open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
          <SheetHeader className="text-left"><SheetTitle>{editing === "new" ? "Add match report" : "Edit match report"}</SheetTitle></SheetHeader>
          <form onSubmit={onSave} className="mx-auto w-full max-w-lg space-y-4 px-4">
            <Field label="Message">
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} placeholder="Paste the WhatsApp message…" required autoFocus className="text-base" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="From"><Input className="h-11" value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Stuart" /></Field>
              <Field label="Sent"><Input type="datetime-local" className="h-11" value={sentAt} onChange={(e) => setSentAt(e.target.value)} /></Field>
            </div>
            <Button type="submit" className="h-12 w-full" disabled={create.isPending || update.isPending || !body.trim()}>
              {editing === "new" ? "Add report" : "Save"}
            </Button>
          </form>
        </SheetContent>
      </Sheet>
    </section>
  );
}
