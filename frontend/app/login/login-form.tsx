"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { fetchClient, errorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { error } = await fetchClient.POST("/api/v1/auth/login", { body: { username, password } });
    setPending(false);
    if (error) {
      setError(errorMessage(error, "Sign in failed"));
      return;
    }
    const next = params.get("next");
    // Full reload on purpose: nothing cached from a previous user may survive a sign-in.
    window.location.assign(next && next.startsWith("/") ? next : "/");
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
      <div className="space-y-2">
        <Label htmlFor="username">Username</Label>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="h-11"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="h-11"
          required
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" className="h-11 w-full" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
