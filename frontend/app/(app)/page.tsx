"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { homeFor, useMe } from "@/lib/me-context";

/** Landing: send the user to their team (or wherever they belong). */
export default function Home() {
  const { me } = useMe();
  const router = useRouter();
  useEffect(() => {
    router.replace(homeFor(me));
  }, [me, router]);
  return null;
}
