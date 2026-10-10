"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, LogOut, Mail, Plus, Trash2, UserRound, UserX } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState } from "@/components/error-state";
import { WhatsAppIcon, whatsAppUrl } from "@/components/whatsapp";
import { formatDate } from "@/lib/format";

type Row = Schema["PlayerAccessRead"];
type Invite = Schema["InviteRead"];
type Created = Schema["InviteCreated"];
type Guardian = Schema["GuardianRead"];
/** A parent to act on, and which action. */
type Action = { user: { id: number; name: string }; kind: "close" | "sign-out" };

/** Who can see the club because of a child in this squad, and inviting more.
 *  Parents sign in with an emailed link, so there is no password to hand out. */
export function ParentsManager() {
  const { teamSeason, canEdit } = useTeam();
  const qc = useQueryClient();
  const tsId = teamSeason?.id ?? 0;
  const q = $api.useQuery(
    "get",
    "/api/v1/team-seasons/{team_season_id}/parents",
    { params: { path: { team_season_id: tsId } } },
    { enabled: !!teamSeason && canEdit },
  );
  const [inviting, setInviting] = useState<Row | null>(null);
  const [created, setCreated] = useState<Created | null>(null);
  const [revoking, setRevoking] = useState<Invite | null>(null);
  const [acting, setActing] = useState<Action | null>(null);
  const revoke = $api.useMutation("delete", "/api/v1/invitations/{invite_id}");
  const close = $api.useMutation("post", "/api/v1/parents/{user_id}/close");
  const signOut = $api.useMutation("post", "/api/v1/parents/{user_id}/sign-out");

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
  }

  async function onRevoke() {
    if (!revoking) return;
    try {
      await revoke.mutateAsync({ params: { path: { invite_id: revoking.id } } });
      invalidate();
      toast.success("Invitation cancelled");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRevoking(null);
    }
  }

  if (!canEdit) {
    return <p className="text-sm text-muted-foreground">Coaches only.</p>;
  }
  async function onAct() {
    if (!acting) return;
    const m = acting.kind === "close" ? close : signOut;
    try {
      await m.mutateAsync({ params: { path: { user_id: acting.user.id } } });
      invalidate();
      toast.success(
        acting.kind === "close"
          ? `${acting.user.name} can no longer sign in`
          : `${acting.user.name} signed out on every device`,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setActing(null);
    }
  }

  if (q.isPending) return <Skeleton className="h-64 rounded-xl" />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;

  const rows = q.data.players;
  const leavers = q.data.leavers;
  const withAccess = rows.filter((r) => r.guardians.length > 0).length;

  return (
    <>
      <p className="mb-3 text-sm text-muted-foreground">
        Parents see the whole age group, read-only. They sign in with a link emailed to
        them - there is no password. {withAccess} of {rows.length} children have a parent
        signed up.
      </p>

      <Card className="divide-y divide-border/40">
        {rows.map((r) => (
          <div key={r.player.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
            <span className="min-w-28 flex-1 text-sm font-medium">{r.player.display_name}</span>
            <div className="flex min-w-0 flex-[2] flex-wrap items-center gap-1.5">
              {r.guardians.map((g) => (
                <GuardianBadge
                  key={g.id}
                  guardian={g}
                  onAct={(kind) =>
                    setActing({ user: { id: g.user_id, name: g.display_name ?? g.email ?? "They" }, kind })
                  }
                />
              ))}
              {r.pending.map((p) => (
                <Badge key={p.id} variant="outline" className="max-w-full gap-1 border-dashed">
                  <Mail className="size-3 shrink-0" />
                  <span className="truncate">{p.email}</span>
                  <span className="text-muted-foreground">· invited</span>
                  <button
                    type="button"
                    onClick={() => setRevoking(p)}
                    aria-label={`Cancel the invitation to ${p.email}`}
                    className="ml-0.5 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                  </button>
                </Badge>
              ))}
              {r.guardians.length === 0 && r.pending.length === 0 && (
                <span className="text-xs text-muted-foreground">Nobody yet</span>
              )}
            </div>
            <Button size="sm" variant="outline" className="h-9" onClick={() => setInviting(r)}>
              <Plus className="size-4" /> {r.pending.length ? "Resend" : "Invite"}
            </Button>
          </div>
        ))}
        {rows.length === 0 && (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            No players in this season&apos;s squad yet.
          </p>
        )}
      </Card>

      {leavers.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 text-sm font-medium">Children who have left</p>
          <p className="mb-3 text-xs text-muted-foreground">
            These parents can still sign in. Closing an account takes effect straight away.
          </p>
          <Card className="divide-y divide-border/40">
            {leavers.map((l) => (
              <div key={l.user_id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{l.display_name ?? l.email}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {l.children.join(", ")} · left
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9"
                  onClick={() =>
                    setActing({ user: { id: l.user_id, name: l.display_name ?? l.email ?? "They" }, kind: "close" })
                  }
                >
                  <UserX className="size-4" /> Close account
                </Button>
              </div>
            ))}
          </Card>
        </div>
      )}

      <InviteSheet
        row={inviting}
        onClose={() => setInviting(null)}
        onCreated={(c) => {
          setInviting(null);
          setCreated(c);
          invalidate();
        }}
      />
      <LinkDialog created={created} onClose={() => setCreated(null)} />

      <Dialog open={acting !== null} onOpenChange={(o) => !o && setActing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {acting?.kind === "close"
                ? `Close ${acting?.user.name}'s account?`
                : `Sign ${acting?.user.name} out everywhere?`}
            </DialogTitle>
            <DialogDescription>
              {acting?.kind === "close"
                ? "They won't be able to sign in again until you reopen it. Nothing they can see is deleted."
                : "Every phone and computer they're signed in on is signed out. They keep their access and can ask for a new link."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setActing(null)}>Cancel</Button>
            <Button
              variant={acting?.kind === "close" ? "destructive" : "default"}
              className="h-11"
              onClick={onAct}
              disabled={close.isPending || signOut.isPending}
            >
              {acting?.kind === "close" ? "Close account" : "Sign out"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={revoking !== null} onOpenChange={(o) => !o && setRevoking(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel this invitation?</DialogTitle>
            <DialogDescription>
              The link sent to {revoking?.email} stops working. You can invite them again
              at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="h-11" onClick={() => setRevoking(null)}>
              Keep it
            </Button>
            <Button variant="destructive" className="h-11" onClick={onRevoke} disabled={revoke.isPending}>
              Cancel invitation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function GuardianBadge({
  guardian: g,
  onAct,
}: {
  guardian: Guardian;
  onAct: (kind: "close" | "sign-out") => void;
}) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs">
      <UserRound className="size-3 shrink-0" />
      <span className="truncate">{g.display_name ?? g.email}</span>
      {!g.is_active && <span className="text-muted-foreground">· closed</span>}
      <button
        type="button"
        onClick={() => onAct("sign-out")}
        aria-label={`Sign ${g.display_name ?? g.email} out everywhere`}
        title="Sign out everywhere"
        className="ml-0.5 text-muted-foreground hover:text-foreground"
      >
        <LogOut className="size-3" />
      </button>
      {g.is_active && (
        <button
          type="button"
          onClick={() => onAct("close")}
          aria-label={`Close ${g.display_name ?? g.email}'s account`}
          title="Close account"
          className="text-muted-foreground hover:text-destructive"
        >
          <UserX className="size-3" />
        </button>
      )}
    </span>
  );
}

function InviteSheet({
  row,
  onClose,
  onCreated,
}: {
  row: Row | null;
  onClose: () => void;
  onCreated: (c: Created) => void;
}) {
  const [email, setEmail] = useState("");
  const create = $api.useMutation("post", "/api/v1/invitations");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!row) return;
    try {
      const c = await create.mutateAsync({
        body: { email: email.trim().toLowerCase(), player_id: row.player.id },
      });
      setEmail("");
      onCreated(c);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Sheet open={row !== null} onOpenChange={(o) => { if (!o) { onClose(); setEmail(""); } }}>
      <SheetContent side="bottom" className="rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
        <SheetHeader className="text-left">
          <SheetTitle>Invite {row?.player.display_name}&apos;s parent</SheetTitle>
          <SheetDescription>
            They&apos;ll get an email with a link. No password to set up.
          </SheetDescription>
        </SheetHeader>
        <form onSubmit={onSubmit} className="mx-auto w-full max-w-lg space-y-4 px-4">
          <div className="space-y-2">
            <Label htmlFor="parent-email">Email address</Label>
            <Input
              id="parent-email"
              type="email"
              inputMode="email"
              autoCapitalize="none"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="parent@example.com"
              className="h-11"
              required
            />
          </div>
          <Button type="submit" className="h-12 w-full" disabled={create.isPending || !email.trim()}>
            {create.isPending ? "Sending…" : "Send invitation"}
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

/** Shown once, straight after inviting. The link is never retrievable again - if it's
 *  lost, invite them afresh. Copying it covers a bounced email, a spam folder, or a
 *  parent who only ever looks at WhatsApp. */
function LinkDialog({ created, onClose }: { created: Created | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.share_text);
      setCopied(true);
      toast.success("Link copied");
    } catch {
      toast.error("Couldn't copy - select the link and copy it by hand");
    }
  }

  return (
    <Dialog open={created !== null} onOpenChange={(o) => { if (!o) { onClose(); setCopied(false); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {created?.emailed ? "Invitation sent" : "Invitation ready"}
          </DialogTitle>
          <DialogDescription>
            {created?.emailed
              ? `Emailed to ${created?.email}. If it doesn't arrive, send them this link yourself - it's the same invitation.`
              : `The email couldn't be sent, so send ${created?.email} this link yourself.`}
          </DialogDescription>
        </DialogHeader>
        <p className="break-all rounded-lg bg-muted/60 p-3 text-xs">{created?.link}</p>
        <p className="text-xs text-muted-foreground">
          <strong className="font-medium text-foreground">Send it to that one parent.</strong>{" "}
          Whoever opens it first becomes {created?.player.display_name}&apos;s parent on the
          app, so it mustn&apos;t go in a group. It works once and expires{" "}
          {created ? formatDate(created.expires_at) : ""}.
        </p>
        <div className="grid grid-cols-2 gap-2">
          <Button asChild className="h-11">
            <a
              href={created ? whatsAppUrl(created.share_text) : "#"}
              target="_blank"
              rel="noopener noreferrer"
            >
              <WhatsAppIcon className="size-4" /> WhatsApp
            </a>
          </Button>
          <Button variant="outline" className="h-11" onClick={copy}>
            {copied ? <><Check className="size-4" /> Copied</> : <><Copy className="size-4" /> Copy message</>}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          WhatsApp opens with the message typed - pick that parent&apos;s chat, not a group.
        </p>
        <DialogFooter>
          <Button variant="outline" className="h-11 w-full" onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
