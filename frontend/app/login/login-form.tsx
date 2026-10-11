"use client";

import { useSearchParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { fetchClient, errorMessage } from "@/lib/api/client";
import { PasskeyCancelled, passkeysSupported, signInWithPasskey } from "@/lib/passkeys";
import { Fingerprint } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Coaches have a password; parents are emailed a link. Password stays the default so
  // nothing changes for the people who sign in every week.
  const [mode, setMode] = useState<"password" | "link">("password");
  const canUsePasskey = useSyncExternalStore(() => () => {}, passkeysSupported, () => false);
  const [email, setEmail] = useState("");
  const [linkSent, setLinkSent] = useState(false);

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

  async function onPasskey() {
    setPending(true);
    setError(null);
    try {
      await signInWithPasskey();
      // Full reload on purpose: nothing cached for a previous user may survive.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/");
    } catch (err) {
      setPending(false);
      // Dismissing the Face ID sheet isn't a failure worth a red message.
      if (err instanceof PasskeyCancelled) return;
      setError("That didn't work. Try the sign-in link below, or ask your coach.");
    }
  }

  async function onRequestLink(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { error } = await fetchClient.POST("/api/v1/auth/signin-link", {
      body: { email: email.trim().toLowerCase() },
    });
    setPending(false);
    if (error) {
      setError(errorMessage(error, "Couldn't send the link"));
      return;
    }
    // Deliberately the same message whether or not that address has an account.
    setLinkSent(true);
  }

  if (linkSent) {
    return (
      <div className="space-y-3 rounded-xl bg-card p-6 text-center shadow-sm ring-1 ring-border/60">
        <h2 className="text-base font-semibold">Check your email</h2>
        <p className="text-sm text-muted-foreground">
          If {email.trim().toLowerCase()} has an account, a sign-in link is on its way. It
          lasts 15 minutes.
        </p>
        <Button type="button" variant="ghost" className="h-11 w-full" onClick={() => { setLinkSent(false); setEmail(""); }}>
          Use a different address
        </Button>
      </div>
    );
  }

  if (mode === "link") {
    return (
      <form onSubmit={onRequestLink} className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <Input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-11"
            autoFocus
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-11 w-full" disabled={pending || !email.trim()}>
          {pending ? "Sending…" : "Email me a sign-in link"}
        </Button>
        <button
          type="button"
          onClick={() => { setMode("password"); setError(null); }}
          className="w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          Sign in with a password instead
        </button>
      </form>
    );
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
      {canUsePasskey && (
        <>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
          </div>
          <Button type="button" variant="outline" className="h-11 w-full" onClick={onPasskey} disabled={pending}>
            <Fingerprint className="size-4" /> Sign in with Face ID or a fingerprint
          </Button>
        </>
      )}
      <button
        type="button"
        onClick={() => { setMode("link"); setError(null); }}
        className="w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
      >
        Parent with no passkey? Email me a link
      </button>
    </form>
  );
}
