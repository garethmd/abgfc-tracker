"use client";

import Image from "next/image";
import Link from "next/link";
import { use, useState } from "react";
import { fetchClient, errorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Where a "forgotten password" email lands. The link proves the inbox; choosing a new
 *  password here is what signs them in, and it ends every other session. */
export default function ResetPasswordPage({ params }: PageProps<"/reset/[token]">) {
  const { token } = use(params);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { error } = await fetchClient.POST("/api/v1/auth/reset-password/{token}", {
      params: { path: { token } },
      body: { new_password: password },
    });
    setPending(false);
    if (error) {
      setError(errorMessage(error, "That link has expired - ask for another"));
      return;
    }
    // Full reload on purpose: the session cookie is new, and nothing cached for a
    // previous user may survive a sign-in (see docs/06-frontend.md).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <Image src="/crest.png" alt="Aldershot Boys & Girls FC crest" width={96} height={96} priority className="size-24" />
          <h1 className="mt-4 text-xl font-semibold tracking-tight">Aldershot Boys &amp; Girls FC</h1>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
          <h2 className="text-base font-semibold">Choose a new password</h2>
          <div className="space-y-2">
            <Label htmlFor="password">New password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11"
              minLength={8}
              autoFocus
              required
            />
            <p className="text-xs text-muted-foreground">At least 8 characters.</p>
          </div>
          {error && (
            <div className="space-y-2">
              <p className="text-sm text-destructive">{error}</p>
              <Button asChild variant="outline" className="h-11 w-full">
                <Link href="/login">Ask for another</Link>
              </Button>
            </div>
          )}
          <Button type="submit" className="h-12 w-full text-base" disabled={pending || password.length < 8}>
            {pending ? "Saving…" : "Save and sign in"}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Anywhere else you&apos;re signed in will be signed out.
          </p>
        </form>
      </div>
    </div>
  );
}
