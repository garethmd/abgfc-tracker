"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

/** The parents' message listing who's available. The text comes from the server (the
 *  template lives there); the coach can edit it, then hand it to WhatsApp or copy it.
 *  WhatsApp's link opens the app (or WhatsApp Desktop/Web) with the text typed and the
 *  chat picker up - a deep link can't name a group, so the coach picks the U10s group
 *  themselves. */
export function MessageSheet({ fixtureId, open, onOpenChange }: { fixtureId: number; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [dateLine, setDateLine] = useState(false);
  // null = showing the server's text; a string = the coach has edited it. Changing a toggle
  // regenerates, so edits are dropped then (the toggles say so).
  const [edited, setEdited] = useState<string | null>(null);

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
          <SheetDescription>Edit if you like, then send it to the parents&apos; WhatsApp group.</SheetDescription>
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
          <div className="grid grid-cols-2 gap-2">
            <Button asChild className="h-12" aria-disabled={!text}>
              <a href={whatsAppUrl(text)} target="_blank" rel="noopener noreferrer" onClick={(e) => { if (!text) e.preventDefault(); }}>
                <WhatsAppIcon className="size-4" /> WhatsApp
              </a>
            </Button>
            <Button type="button" variant="outline" className="h-12 w-full" onClick={copy} disabled={!text}>
              <Copy className="size-4" /> Copy message
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">WhatsApp opens with the message typed - pick the parents&apos; group and send.</p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** WhatsApp's universal link: the app on a phone, WhatsApp Desktop or Web on a computer.
 *  It takes text only - there is no way to address a group, by design on their side. */
function whatsAppUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z" />
    </svg>
  );
}
