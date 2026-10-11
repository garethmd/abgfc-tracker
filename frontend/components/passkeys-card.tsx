"use client";

import { useState, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Fingerprint, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { PasskeyCancelled, passkeysSupported, registerPasskey } from "@/lib/passkeys";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/format";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** The devices this person can sign in with. Only shown to accounts that have no
 *  password - a coach signs in with one and has no use for this. */
export function PasskeysCard() {
  const { me } = useMe();
  const qc = useQueryClient();
  const supported = useSyncExternalStore(() => () => {}, passkeysSupported, () => false);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<{ id: number; label: string } | null>(null);

  const list = $api.useQuery("get", "/api/v1/auth/passkeys", {}, { enabled: !me.has_password });
  const remove = $api.useMutation("delete", "/api/v1/auth/passkeys/{passkey_id}");

  if (me.has_password) return null;

  async function onAdd() {
    setAdding(true);
    try {
      await registerPasskey(deviceGuess());
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/passkeys"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/me"] });
      toast.success("This device can now sign you in");
    } catch (err) {
      if (!(err instanceof PasskeyCancelled)) toast.error(errorMessage(err, "That didn't work"));
    } finally {
      setAdding(false);
    }
  }

  async function onRemove() {
    if (!removing) return;
    try {
      await remove.mutateAsync({ params: { path: { passkey_id: removing.id } } });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/passkeys"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/me"] });
      toast.success(`${removing.label} removed`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRemoving(null);
    }
  }

  const keys = list.data ?? [];

  return (
    <>
      <Card className="p-4">
        {list.isPending ? (
          <Skeleton className="h-12" />
        ) : keys.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            You sign in with a link emailed to you. Set up Face ID, a fingerprint or your
            phone&apos;s PIN and you can get in with a tap instead.
          </p>
        ) : (
          <ul className="divide-y divide-border/40">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center gap-3 py-2 text-sm first:pt-0">
                <Fingerprint className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{k.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    Added {formatDate(k.created_at)}
                    {k.last_used_at ? ` · last used ${formatDate(k.last_used_at)}` : " · not used yet"}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => setRemoving({ id: k.id, label: k.label })}
                  aria-label={`Remove ${k.label}`}
                  className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-destructive"
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        {supported ? (
          <Button variant="outline" className="mt-3 h-11 w-full" onClick={onAdd} disabled={adding}>
            <Plus className="size-4" /> {adding ? "Setting up…" : "Add this device"}
          </Button>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            This device can&apos;t hold a passkey. Try it on your phone, or ask your coach to
            keep email sign-in on for you.
          </p>
        )}
      </Card>

      <Dialog open={removing !== null} onOpenChange={(o) => !o && setRemoving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove {removing?.label}?</DialogTitle>
            <DialogDescription>
              That device won&apos;t be able to sign in any more. If it&apos;s your only one,
              add another first — otherwise you&apos;ll need your coach to let you back in.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setRemoving(null)}>Keep</Button>
            <Button variant="destructive" className="h-11" onClick={onRemove} disabled={remove.isPending}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** A name the owner will recognise in a list. The browser won't tell us the device, so
 *  this is a guess from the user agent, and they can't rename it - good enough to tell
 *  "iPhone" from "Laptop". */
function deviceGuess(): string {
  if (typeof navigator === "undefined") return "This device";
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android phone";
  if (/Mac/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows PC";
  return "This device";
}
