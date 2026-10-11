"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, LogOut, Mail, Plus, Trash2, UserCheck, UserRound, UserX } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema, invalidatePath } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { cn } from "@/lib/utils";

type Row = Schema["PlayerAccessRead"];
type Invite = Schema["InviteRead"];
type Created = Schema["InviteCreated"];
type Guardian = Schema["GuardianRead"];
/** A parent to act on, and which action. */
type Action = {
  user: { id: number; name: string };
  kind: "close" | "sign-out" | "reopen" | "unlink";
  /** unlink only: which child's access is being taken away. */
  player?: { id: number; name: string };
};

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
  const reopen = $api.useMutation("post", "/api/v1/parents/{user_id}/reopen");
  const unlink = $api.useMutation("delete", "/api/v1/parents/{user_id}/children/{player_id}");

  function invalidate() {
    invalidatePath(qc, "/api/v1/team-seasons");
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
    const path = { user_id: acting.user.id };
    try {
      if (acting.kind === "unlink" && acting.player) {
        await unlink.mutateAsync({
          params: { path: { ...path, player_id: acting.player.id } },
        });
        toast.success(`${acting.user.name} can no longer see ${acting.player.name}`);
      } else if (acting.kind === "close") {
        await close.mutateAsync({ params: { path } });
        toast.success(`${acting.user.name} can no longer sign in`);
      } else if (acting.kind === "reopen") {
        await reopen.mutateAsync({ params: { path } });
        toast.success(`${acting.user.name} can sign in again`);
      } else {
        await signOut.mutateAsync({ params: { path } });
        toast.success(`${acting.user.name} signed out on every device`);
      }
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setActing(null);
    }
  }

  const BUSY = [close, signOut, reopen, unlink].some((m) => m.isPending);
  const COPY: Record<Action["kind"], { title: (a: Action) => string; body: string; cta: string; danger: boolean }> = {
    unlink: {
      title: (a) => `Stop ${a.user.name} seeing ${a.player?.name}?`,
      body: "Their account stays, along with any other children they have here. If this was their only one, they lose access altogether.",
      cta: "Remove",
      danger: true,
    },
    close: {
      title: (a) => `Close ${a.user.name}'s account?`,
      body: "They won't be able to sign in again until you re-open it. Nothing they can see is deleted.",
      cta: "Close account",
      danger: true,
    },
    reopen: {
      title: (a) => `Let ${a.user.name} back in?`,
      body: "They'll be able to sign in again with the same email or passkey. Nothing else changes.",
      cta: "Re-open",
      danger: false,
    },
    "sign-out": {
      title: (a) => `Sign ${a.user.name} out everywhere?`,
      body: "Every phone and computer they're signed in on is signed out. They keep their access and can sign in again.",
      cta: "Sign out",
      danger: false,
    },
  };

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
          <div key={r.player.id} className="px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">
                {r.player.display_name}
              </span>
              {r.guardians.length === 0 && r.pending.length === 0 && (
                <span className="text-xs text-muted-foreground">Nobody yet</span>
              )}
              <Button size="sm" variant="outline" className="h-9 shrink-0" onClick={() => setInviting(r)}>
                <Plus className="size-4" /> {r.pending.length ? "Resend" : "Invite"}
              </Button>
            </div>

            {/* One line per person: at phone width, three icons and a name cannot share
                a row with the child's name without the name becoming "S…". */}
            {(r.guardians.length > 0 || r.pending.length > 0) && (
              <ul className="mt-2 space-y-1.5">
                {r.guardians.map((g) => (
                  <GuardianRow
                    key={g.id}
                    guardian={g}
                    onAct={(kind) =>
                      setActing({
                        user: { id: g.user_id, name: g.display_name ?? g.email ?? "They" },
                        kind,
                        player: { id: r.player.id, name: r.player.display_name },
                      })
                    }
                  />
                ))}
                {r.pending.map((p) => (
                  <li key={p.id} className="flex items-center gap-2 text-xs">
                    <Mail className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate text-muted-foreground">
                      {p.email} · invited
                    </span>
                    <button
                      type="button"
                      onClick={() => setRevoking(p)}
                      aria-label={`Cancel the invitation to ${p.email}`}
                      className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
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
          {acting && (
            <>
              <DialogHeader>
                <DialogTitle>{COPY[acting.kind].title(acting)}</DialogTitle>
                <DialogDescription>{COPY[acting.kind].body}</DialogDescription>
              </DialogHeader>
              <DialogFooter className="gap-2">
                <Button variant="outline" className="h-11" onClick={() => setActing(null)}>Cancel</Button>
                <Button
                  variant={COPY[acting.kind].danger ? "destructive" : "default"}
                  className="h-11"
                  onClick={onAct}
                  disabled={BUSY}
                >
                  {COPY[acting.kind].cta}
                </Button>
              </DialogFooter>
            </>
          )}
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

function GuardianRow({
  guardian: g,
  onAct,
}: {
  guardian: Guardian;
  onAct: (kind: Action["kind"]) => void;
}) {
  const name = g.display_name ?? g.email ?? "This parent";
  return (
    <li className="flex items-center gap-2 text-xs">
      <UserRound className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1 truncate">
        {name}
        {!g.is_active && <span className="text-muted-foreground"> · closed</span>}
        {g.passkey_count > 0 && <span className="text-muted-foreground"> · passkey</span>}
      </span>
      {g.is_active ? (
        <>
          <RowButton label={`Sign ${name} out everywhere`} title="Sign out everywhere" onClick={() => onAct("sign-out")}>
            <LogOut className="size-3.5" />
          </RowButton>
          <RowButton label={`Stop ${name} seeing this child`} title="Remove access to this child" danger onClick={() => onAct("unlink")}>
            <Trash2 className="size-3.5" />
          </RowButton>
          <RowButton label={`Close ${name}'s account`} title="Close their account" danger onClick={() => onAct("close")}>
            <UserX className="size-3.5" />
          </RowButton>
        </>
      ) : (
        <RowButton label={`Let ${name} back in`} title="Re-open this account" onClick={() => onAct("reopen")}>
          <UserCheck className="size-3.5" />
        </RowButton>
      )}
    </li>
  );
}

function RowButton({
  label,
  title,
  danger,
  onClick,
  children,
}: {
  label: string;
  title: string;
  danger?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={title}
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent",
        danger ? "hover:text-destructive" : "hover:text-foreground",
      )}
    >
      {children}
    </button>
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

  /** WhatsApp sends nothing: the coach gets the link and the parent types their own
   *  address on the way in, because a coach with a phone number rarely has an email. */
  async function invite(withEmail: boolean) {
    if (!row) return;
    try {
      const c = await create.mutateAsync({
        body: {
          player_id: row.player.id,
          ...(withEmail ? { email: email.trim().toLowerCase() } : {}),
        },
      });
      setEmail("");
      onCreated(c);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await invite(true);
  }

  return (
    <Sheet open={row !== null} onOpenChange={(o) => { if (!o) { onClose(); setEmail(""); } }}>
      <SheetContent side="bottom" className="rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
        <SheetHeader className="text-left">
          <SheetTitle>Invite {row?.player.display_name}&apos;s parent</SheetTitle>
          <SheetDescription>
            They get a link, tap it, and they&apos;re in. No password to set up.
          </SheetDescription>
        </SheetHeader>
        <div className="mx-auto w-full max-w-lg space-y-5 px-4">
          <div className="space-y-2">
            <Button
              type="button"
              className="h-12 w-full"
              onClick={() => invite(false)}
              disabled={create.isPending}
            >
              <WhatsAppIcon className="size-4" /> Send on WhatsApp
            </Button>
            <p className="text-xs text-muted-foreground">
              Nothing is emailed. You get the link to send to that parent, and they give
              us their email when they open it.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" /> or email it <span className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={onSubmit} className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="parent-email">Their email address</Label>
              <Input
                id="parent-email"
                type="email"
                inputMode="email"
                autoCapitalize="none"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="parent@example.com"
                className="h-11"
              />
            </div>
            <Button
              type="submit"
              variant="outline"
              className="h-12 w-full"
              disabled={create.isPending || !email.trim()}
            >
              {create.isPending ? "Sending…" : "Email the invitation"}
            </Button>
          </form>
        </div>
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
              : created?.email
                ? `The email couldn't be sent, so send ${created.email} this link yourself.`
                : "Send this to that parent. They'll give us their email when they open it."}
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
