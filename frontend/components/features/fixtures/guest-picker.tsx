"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { $api, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

type Player = Schema["PlayerSummary"];

/** "Noah played for the Blacks today." A child can turn out for another team in the age
 *  group without joining its squad: the appearance and any goals count for the team they
 *  played for, and still show on their own player page. The squad itself is untouched —
 *  squad size, availability and the matchday sheet's fairness column stay honest. */
export function GuestPicker({
  exclude,
  onAdd,
  label = "Add a guest",
}: {
  /** Player ids already on the list (the squad, plus guests added so far). */
  exclude: number[];
  onAdd: (player: Player) => void;
  label?: string;
}) {
  const { team } = useTeam();
  const [open, setOpen] = useState(false);
  const pool = $api.useQuery(
    "get",
    "/api/v1/players",
    { params: { query: { cohort_id: team.cohort_id, include_left: false } } },
    { enabled: open },
  );
  const candidates = (pool.data ?? []).filter((p) => !exclude.includes(p.id));

  return (
    <>
      <Button type="button" variant="outline" className="mt-3 h-11" onClick={() => setOpen(true)}>
        <UserPlus className="size-4" /> {label}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="max-h-[80dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none">
          <SheetHeader className="text-left">
            <SheetTitle>Add a guest</SheetTitle>
            <SheetDescription>
              Anyone in the age group who isn&apos;t in the {team.name} squad. Their appearance and goals
              count for {team.name} today, and still count on their own player page.
            </SheetDescription>
          </SheetHeader>
          <div className="mx-auto w-full max-w-lg space-y-2 px-4 pb-2">
            {pool.isPending ? (
              <Skeleton className="h-40 rounded-xl" />
            ) : candidates.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Everyone in the age group is already on the list.
              </p>
            ) : (
              candidates.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="flex h-12 w-full items-center rounded-xl border border-border/60 px-4 text-left text-sm font-medium transition-colors hover:bg-accent active:bg-accent"
                  onClick={() => {
                    onAdd({ id: p.id, display_name: p.display_name, photo_key: p.photo_key });
                    setOpen(false);
                  }}
                >
                  {p.display_name}
                </button>
              ))
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
