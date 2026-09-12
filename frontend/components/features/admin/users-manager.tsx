"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/features/fixtures/fixture-form";

type Role = Schema["RoleAssignment"];
type User = Schema["UserAdminRead"];

const ROLE_LABEL: Record<string, string> = { viewer: "Viewer", coach: "Coach", admin: "Admin" };

/** "coach · Blues", "admin · Born 2016/17", "admin · Club" */
function describe(r: Schema["RoleRead"], teams: Schema["ClubTeamRead"][], cohorts: Schema["CohortRead"][]) {
  const where =
    r.scope_type === "club" ? "Club"
    : r.scope_type === "cohort" ? (cohorts.find((c) => c.id === r.scope_id)?.name ?? `age group ${r.scope_id}`)
    : (teams.find((t) => t.id === r.scope_id)?.name ?? `team ${r.scope_id}`);
  return `${ROLE_LABEL[r.role]} · ${where}`;
}

export function UsersManager() {
  const qc = useQueryClient();
  const { me, isClubAdmin } = useMe();
  const users = $api.useQuery("get", "/api/v1/users");
  const teams = $api.useQuery("get", "/api/v1/club-teams");
  const cohorts = $api.useQuery("get", "/api/v1/cohorts");
  const create = $api.useMutation("post", "/api/v1/users");
  const update = $api.useMutation("patch", "/api/v1/users/{user_id}");
  const setRoles = $api.useMutation("put", "/api/v1/users/{user_id}/roles");
  const setPassword = $api.useMutation("post", "/api/v1/users/{user_id}/password");

  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword_] = useState("");
  const [roles, setRolesState] = useState<Role[]>([]);
  const [resetFor, setResetFor] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["get", "/api/v1/users"] });

  function openNew() {
    setEditing("new");
    setUsername("");
    setDisplayName("");
    setPassword_("");
    setRolesState([{ role: "coach", scope_type: "team", scope_id: teams.data?.[0]?.id ?? null }]);
  }
  function openEdit(u: User) {
    setEditing(u);
    setDisplayName(u.display_name ?? "");
    setRolesState(u.roles.map((r) => ({ role: r.role, scope_type: r.scope_type, scope_id: r.scope_id })));
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editing === "new") {
        await create.mutateAsync({ body: { username: username.trim(), display_name: displayName.trim() || null, password, roles } });
        toast.success(`Added ${username}`);
      } else if (editing) {
        await update.mutateAsync({ params: { path: { user_id: editing.id } }, body: { display_name: displayName.trim() || null } });
        await setRoles.mutateAsync({ params: { path: { user_id: editing.id } }, body: roles });
        toast.success("Saved");
      }
      invalidate();
      if (editing !== "new" && editing?.id === me.id) qc.invalidateQueries({ queryKey: ["get", "/api/v1/auth/me"] });
      setEditing(null);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onToggleActive(u: User, is_active: boolean) {
    try {
      await update.mutateAsync({ params: { path: { user_id: u.id } }, body: { is_active } });
      invalidate();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onReset(e: React.FormEvent) {
    e.preventDefault();
    if (!resetFor) return;
    try {
      await setPassword.mutateAsync({ params: { path: { user_id: resetFor.id } }, body: { new_password: newPassword } });
      toast.success(`Password reset for ${resetFor.username}`);
      setResetFor(null);
      setNewPassword("");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const updateRole = (i: number, patch: Partial<Role>) =>
    setRolesState((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="outline" onClick={openNew}><Plus className="size-4" /> Add coach</Button>
      </div>
      <Card className="divide-y divide-border/40">
        {(users.data ?? []).map((u) => (
          <div key={u.id} className="flex min-h-16 items-center gap-3 px-4 py-2 text-sm">
            <button type="button" onClick={() => openEdit(u)} className="min-w-0 flex-1 text-left">
              <p className={u.is_active ? "font-medium" : "font-medium text-muted-foreground line-through"}>
                {u.display_name ?? u.username}
                {u.display_name && <span className="ml-1.5 text-xs font-normal text-muted-foreground">{u.username}</span>}
              </p>
              <p className="mt-0.5 flex flex-wrap gap-1">
                {u.roles.map((r, i) => (
                  <Badge key={i} variant="outline" className="text-[10px]">{describe(r, teams.data ?? [], cohorts.data ?? [])}</Badge>
                ))}
              </p>
            </button>
            <button type="button" onClick={() => setResetFor(u)} className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent" aria-label="Reset password">
              <KeyRound className="size-4" />
            </button>
            {u.id !== me.id && <Switch checked={u.is_active} onCheckedChange={(v) => onToggleActive(u, v)} aria-label="Active" />}
          </div>
        ))}
        {users.data && !users.data.length && <p className="p-4 text-sm text-muted-foreground">No coaches in your scope yet.</p>}
      </Card>
      <p className="mt-2 text-xs text-muted-foreground">
        A <strong>team</strong> coach sees only their team. An <strong>age-group</strong> coach sees every team in the cohort. Admins can also manage coaches within their scope.
      </p>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing === "new" ? "Add coach" : `Edit ${editing?.username}`}</DialogTitle></DialogHeader>
          <form onSubmit={onSave} className="space-y-4">
            {editing === "new" && (
              <>
                <Field label="Username"><Input className="h-11" value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none" required autoFocus /></Field>
                <Field label="Temporary password"><Input type="password" autoComplete="new-password" className="h-11" value={password} onChange={(e) => setPassword_(e.target.value)} minLength={8} required /></Field>
              </>
            )}
            <Field label="Name"><Input className="h-11" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Stuart" /></Field>
            <Field label="Access">
              <div className="space-y-2">
                {roles.map((r, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Select value={r.role} onValueChange={(v) => updateRole(i, { role: v as Role["role"] })}>
                      <SelectTrigger className="h-10 w-28"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {(["viewer", "coach", "admin"] as const).map((x) => <SelectItem key={x} value={x}>{ROLE_LABEL[x]}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Select
                      value={`${r.scope_type}:${r.scope_id ?? ""}`}
                      onValueChange={(v) => {
                        const [scope_type, id] = v.split(":");
                        updateRole(i, { scope_type: scope_type as Role["scope_type"], scope_id: id ? Number(id) : null });
                      }}
                    >
                      <SelectTrigger className="h-10 flex-1"><SelectValue placeholder="Where" /></SelectTrigger>
                      <SelectContent>
                        {(teams.data ?? []).map((t) => <SelectItem key={`t${t.id}`} value={`team:${t.id}`}>{t.name}</SelectItem>)}
                        {(cohorts.data ?? []).map((c) => <SelectItem key={`c${c.id}`} value={`cohort:${c.id}`}>{c.name} (all teams)</SelectItem>)}
                        {isClubAdmin && <SelectItem value="club:">Whole club</SelectItem>}
                      </SelectContent>
                    </Select>
                    <button type="button" onClick={() => setRolesState((rs) => rs.filter((_, j) => j !== i))} className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent" aria-label="Remove"><X className="size-4" /></button>
                  </div>
                ))}
                <Button type="button" variant="ghost" size="sm" onClick={() => setRolesState((rs) => [...rs, { role: "coach", scope_type: "team", scope_id: teams.data?.[0]?.id ?? null }])}>
                  <Plus className="size-4" /> Add another
                </Button>
              </div>
            </Field>
            <Button type="submit" className="h-11 w-full" disabled={create.isPending || setRoles.isPending || roles.length === 0}>Save</Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={resetFor !== null} onOpenChange={(o) => !o && setResetFor(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reset password for {resetFor?.username}</DialogTitle></DialogHeader>
          <form onSubmit={onReset} className="space-y-4">
            <Field label="New password"><Input type="password" autoComplete="new-password" className="h-11" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={8} required autoFocus /></Field>
            <p className="text-xs text-muted-foreground">Tell them to change it after signing in (Settings → Account).</p>
            <Button type="submit" className="h-11 w-full" disabled={setPassword.isPending}>Reset</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
