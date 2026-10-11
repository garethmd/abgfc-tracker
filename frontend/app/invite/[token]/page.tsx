"use client";

import Image from "next/image";
import { use, useState, useSyncExternalStore } from "react";
import { fetchClient, errorMessage, type Schema } from "@/lib/api/client";
import { PasskeyCancelled, passkeysSupported, registerPasskey } from "@/lib/passkeys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";

type Preview = Schema["InvitePreview"];

/** Where an invitation email lands. Looking at this page does not use the invitation
 *  up - that only happens when the parent presses the button, so a mail scanner
 *  following the link can't burn it before they get here. */
export default function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = use(params);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Set once the account exists: from here the only thing left is the passkey.
  const [registering, setRegistering] = useState(false);
  const canUsePasskey = useSyncExternalStore(() => () => {}, passkeysSupported, () => false);

  const q = useQuery({
    queryKey: ["invite", token],
    retry: false,
    queryFn: async () => {
      const { data, error } = await fetchClient.GET("/api/v1/auth/invitations/{token}", {
        params: { path: { token } },
      });
      if (error) throw error;
      return data as Preview;
    },
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { error } = await fetchClient.POST("/api/v1/auth/invitations/{token}/accept", {
      params: { path: { token } },
      body: {
        display_name: name.trim(),
        // Only when the coach sent the link by hand and we don't know it yet.
        ...(q.data?.email ? {} : { email: email.trim().toLowerCase() }),
      },
    });
    setPending(false);
    if (error) {
      setError(errorMessage(error, "That didn't work"));
      return;
    }
    // The account exists and we're signed in. Offer the passkey before leaving - this
    // is the one moment they're guaranteed to be here, and it's what they'll use from
    // now on. A phone that can't hold one just goes straight in.
    if (canUsePasskey) {
      setRegistering(true);
      return;
    }
    // Full reload on purpose: the session cookie is new, and nothing cached for a
    // previous user may survive a sign-in (see docs/06-frontend.md).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  async function onCreatePasskey() {
    setPending(true);
    setError(null);
    try {
      await registerPasskey();
    } catch (err) {
      setPending(false);
      if (!(err instanceof PasskeyCancelled)) {
        setError("That didn't work - you can set it up later in Settings.");
        return;
      }
      // Dismissed: they're still signed in, so let them carry on without one.
    }
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  if (registering) {
    return (
      <Shell>
        <div className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
          <h2 className="text-base font-semibold">One last thing</h2>
          <p className="text-sm text-muted-foreground">
            Set up Face ID, your fingerprint or your phone&apos;s PIN so you can get back in
            with a tap. There&apos;s no password to remember, and it only works on this app.
          </p>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="button" className="h-12 w-full text-base" onClick={onCreatePasskey} disabled={pending}>
            {pending ? "Setting up…" : "Set it up"}
          </Button>
          <button
            type="button"
            onClick={() => {
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination
              window.location.assign("/");
            }}
            className="w-full text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            Not now
          </button>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      {q.isPending ? (
        <Skeleton className="h-56 rounded-xl" />
      ) : q.error ? (
        <Card>
          <h2 className="text-base font-semibold">This link has expired</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Invitations last a fortnight and can only be used once. Ask your coach to send
            another one.
          </p>
        </Card>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
          <div>
            <h2 className="text-base font-semibold">
              {q.data.invited_by ?? "Your coach"} has invited you
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              See {q.data.player_name}&apos;s fixtures, results and availability
              {q.data.team_names.length > 0 && <> with {q.data.team_names.join(" and ")}</>}.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Your name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jo Smith"
              className="h-11"
              autoFocus
              required
            />
          </div>
          {!q.data.email && (
            <div className="space-y-2">
              <Label htmlFor="email">Your email address</Label>
              <Input
                id="email"
                type="email"
                inputMode="email"
                autoCapitalize="none"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="h-11"
                required
              />
              <p className="text-xs text-muted-foreground">
                Only so we can send you a link when you need to sign in again.
              </p>
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            type="submit"
            className="h-12 w-full text-base"
            disabled={pending || !name.trim() || (!q.data.email && !email.trim())}
          >
            {pending ? "Getting you in…" : "Get started"}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            No password needed. Next time, we&apos;ll email you a link to sign in
            {q.data.email ? ` at ${q.data.email}` : ""}.
          </p>
        </form>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <Image src="/crest.png" alt="Aldershot Boys & Girls FC crest" width={96} height={96} priority className="size-24" />
          <h1 className="mt-4 text-center text-xl font-semibold tracking-tight">
            Aldershot Boys &amp; Girls FC
          </h1>
        </div>
        {children}
      </div>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">{children}</div>;
}
