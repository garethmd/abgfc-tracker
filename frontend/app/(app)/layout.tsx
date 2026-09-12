"use client";

import { MeProvider, useMeQuery } from "@/lib/me-context";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";

export default function AppLayout({ children }: LayoutProps<"/">) {
  const me = useMeQuery();
  if (me.isPending) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <Skeleton className="mb-6 h-8 w-40" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  // A 401 here is already redirecting to /login (see lib/api/client.ts).
  if (me.error || !me.data) return <div className="p-6"><ErrorState error={me.error} onRetry={() => me.refetch()} /></div>;
  return <MeProvider me={me.data} refetch={() => me.refetch()}>{children}</MeProvider>;
}
