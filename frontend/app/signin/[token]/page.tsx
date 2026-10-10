"use client";

import Image from "next/image";
import Link from "next/link";
import { use, useState } from "react";
import { fetchClient, errorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

/** The page an emailed sign-in link opens. The link is only spent when the button is
 *  pressed - mail security scanners follow links, and consuming on load would mean the
 *  parent's link was already used by the time they tapped it. */
export default function SigninLinkPage({ params }: PageProps<"/signin/[token]">) {
  const { token } = use(params);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function signIn() {
    setPending(true);
    setError(null);
    const { error } = await fetchClient.POST("/api/v1/auth/signin-link/{token}", {
      params: { path: { token } },
    });
    setPending(false);
    if (error) {
      setError(errorMessage(error, "That link has expired"));
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
        <div className="space-y-4 rounded-xl bg-card p-6 shadow-sm ring-1 ring-border/60">
          {error ? (
            <>
              <h2 className="text-base font-semibold">This link has expired</h2>
              <p className="text-sm text-muted-foreground">
                Sign-in links last 15 minutes and work once.
              </p>
              <Button asChild variant="outline" className="h-11 w-full">
                <Link href="/login">Send me another</Link>
              </Button>
            </>
          ) : (
            <>
              <h2 className="text-base font-semibold">Ready when you are</h2>
              <Button type="button" className="h-12 w-full text-base" onClick={signIn} disabled={pending}>
                {pending ? "Signing in…" : "Sign in"}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
