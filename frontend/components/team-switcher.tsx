"use client";

import Link from "next/link";
import { ChevronDown, Shield, Users2 } from "lucide-react";
import { useMe } from "@/lib/me-context";
import { Crest } from "@/components/app-shell";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Brand block. A single-team coach just sees their team name; anyone with more
 * places to go gets a dropdown. */
export function TeamSwitcher({ current }: { current?: { name: string; slug: string; colour: string | null } }) {
  const { me, cohortRoles, isAdminSomewhere } = useMe();
  const destinations = me.teams.length + cohortRoles.length + (isAdminSomewhere ? 1 : 0);
  const label = current?.name ?? "ABGFC";

  const brand = (
    <span className="flex items-center gap-2">
      <Crest letter={label[0]} colour={current?.colour} />
      <span className="font-semibold tracking-tight">{label}</span>
    </span>
  );
  if (destinations <= 1) return brand;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-10 items-center gap-1.5 rounded-lg pr-2 hover:bg-accent">
        {brand}
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-48">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Teams</DropdownMenuLabel>
        {me.teams.map((t) => (
          <DropdownMenuItem key={t.team.id} asChild>
            <Link href={`/${t.team.slug}`} className="flex items-center gap-2">
              <span className="size-2.5 rounded-full" style={{ background: t.team.colour ?? "currentColor" }} />
              {t.team.name}
              {t.team.slug === current?.slug && <span className="ml-auto text-xs text-muted-foreground">current</span>}
            </Link>
          </DropdownMenuItem>
        ))}
        {(cohortRoles.length > 0 || isAdminSomewhere) && <DropdownMenuSeparator />}
        {cohortRoles.map((c) => (
          <DropdownMenuItem key={c.cohort.id} asChild>
            <Link href={`/cohorts/${c.cohort.id}`}>
              <Users2 className="size-4" /> {c.cohort.name} overview
            </Link>
          </DropdownMenuItem>
        ))}
        {isAdminSomewhere && (
          <DropdownMenuItem asChild>
            <Link href="/admin">
              <Shield className="size-4" /> Club admin
            </Link>
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
