"use client";

import { useState } from "react";
import { KeyRound, LogOut } from "lucide-react";
import { toast } from "sonner";
import { $api, fetchClient, errorMessage } from "@/lib/api/client";
import { useMe } from "@/lib/me-context";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/features/fixtures/fixture-form";

export function AccountCard() {
  const { me } = useMe();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = $api.useMutation("post", "/api/v1/auth/change-password");

  async function logout() {
    await fetchClient.POST("/api/v1/auth/logout");
    // Full reload so the next person to sign in on this phone starts with an empty cache.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }

  async function onChange(e: React.FormEvent) {
    e.preventDefault();
    try {
      await change.mutateAsync({ body: { current_password: current, new_password: next } });
      toast.success("Password changed");
      setOpen(false);
      setCurrent("");
      setNext("");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const roleLabel = me.club_role
    ? `Club ${me.club_role}`
    : me.cohorts.some((c) => me.roles.some((r) => r.scope_type === "cohort" && r.scope_id === c.cohort.id))
      ? "Age-group coach"
      : me.teams.length ? `${me.teams[0].role} · ${me.teams.map((t) => t.team.name).join(", ")}` : "No team";

  return (
    <>
      <Card className="flex items-center justify-between gap-3 p-4">
        <div className="min-w-0 text-sm">
          <p className="truncate font-medium">{me.display_name ?? me.username}</p>
          <p className="truncate text-xs capitalize text-muted-foreground">{roleLabel}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}><KeyRound className="size-4" /><span className="hidden sm:inline">Password</span></Button>
          <Button variant="outline" size="sm" onClick={logout}><LogOut className="size-4" /><span className="hidden sm:inline">Sign out</span></Button>
        </div>
      </Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Change password</DialogTitle></DialogHeader>
          <form onSubmit={onChange} className="space-y-4">
            <Field label="Current password"><Input type="password" autoComplete="current-password" className="h-11" value={current} onChange={(e) => setCurrent(e.target.value)} required /></Field>
            <Field label="New password"><Input type="password" autoComplete="new-password" className="h-11" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required /></Field>
            <Button type="submit" className="h-11 w-full" disabled={change.isPending}>Change password</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
