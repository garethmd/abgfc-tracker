import Image from "next/image";
import { Suspense } from "react";
import { LoginForm } from "./login-form";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <Image src="/crest.png" alt="Aldershot Boys & Girls FC crest" width={96} height={96} priority className="size-24" />
          <h1 className="mt-4 text-xl font-semibold tracking-tight">Aldershot Boys &amp; Girls FC</h1>
          <p className="mt-1 text-sm text-muted-foreground">Coaches only. Sign in to continue.</p>
        </div>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
    </div>
  );
}
