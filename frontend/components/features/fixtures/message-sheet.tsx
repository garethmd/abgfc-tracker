"use client";

import { useState, useSyncExternalStore } from "react";
import { Copy, Share } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

/** The parents' message listing who's available. The text comes from the server (the
 *  template lives there); the coach can edit it, then share it through the phone's share
 *  sheet or copy it and pick the WhatsApp group themselves. */
export function MessageSheet({ fixtureId, open, onOpenChange }: { fixtureId: number; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [dateLine, setDateLine] = useState(false);
  // null = showing the server's text; a string = the coach has edited it. Changing a toggle
  // regenerates, so edits are dropped then (the toggles say so).
  const [edited, setEdited] = useState<string | null>(null);
  const canShare = useSyncExternalStore(() => () => {}, () => typeof navigator !== "undefined" && !!navigator.share, () => false);

  const q = $api.useQuery(
    "get",
    "/api/v1/fixtures/{fixture_id}/selection/message",
    { params: { path: { fixture_id: fixtureId }, query: { date_line: dateLine } } },
    { enabled: open },
  );
  const text = edited ?? q.data?.text ?? "";

  function toggle(setter: (v: boolean) => void) {
    return (v: boolean) => { setter(v); setEdited(null); };
  }

  async function share() {
    try {
      await navigator.share({ text });
    } catch (err) {
      if ((err as { name?: string }).name !== "AbortError") toast.error("Couldn't open the share sheet");
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Message copied");
    } catch {
      toast.error("Couldn't copy - select the text and copy it instead");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
        <SheetHeader className="text-left">
          <SheetTitle>Message parents</SheetTitle>
          <SheetDescription>Edit if you like, then share or copy it into the group.</SheetDescription>
        </SheetHeader>
        <div className="mx-auto w-full max-w-lg space-y-4 px-4">
          {q.isPending ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : q.error ? (
            <p className="text-sm text-destructive">{errorMessage(q.error)}</p>
          ) : (
            <Textarea
              value={text}
              onChange={(e) => setEdited(e.target.value)}
              rows={Math.min(18, Math.max(8, text.split("\n").length + 1))}
              className="text-base leading-relaxed"
              aria-label="Message"
            />
          )}
          <label className="flex h-11 items-center justify-between gap-3 rounded-xl bg-muted/50 px-3 text-sm">
            <Label htmlFor="date-line" className="font-normal">Add the date as the first line</Label>
            <Switch id="date-line" checked={dateLine} onCheckedChange={toggle(setDateLine)} />
          </label>
          {edited !== null && <p className="text-xs text-muted-foreground">Edited - the toggle regenerates the message.</p>}
          <div className={canShare ? "grid grid-cols-2 gap-2" : ""}>
            {canShare && (
              <Button type="button" className="h-12" onClick={share} disabled={!text}>
                <Share className="size-4" /> Share…
              </Button>
            )}
            <Button type="button" variant={canShare ? "outline" : "default"} className="h-12 w-full" onClick={copy} disabled={!text}>
              <Copy className="size-4" /> Copy message
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
