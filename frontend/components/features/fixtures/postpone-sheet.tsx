"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Field } from "@/components/features/fixtures/fixture-form";

type Fixture = Schema["FixtureDetail"];

/** Calling a match off. Winter takes pitches out most seasons.
 *
 *  The fixture keeps the date it was due - that a match should have been played that day
 *  is the record worth having, which is why this is not a delete. The league doesn't give
 *  it a new date: if the tie is replayed it comes round as a new fixture. */
export function PostponeSheet({
  fixture,
  open,
  onOpenChange,
}: {
  fixture: Fixture;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const router = useRouter();
  const [reason, setReason] = useState("");
  const postpone = $api.useMutation(
    "post",
    "/api/v1/fixtures/{fixture_id}/postpone",
  );

  async function onConfirm() {
    try {
      await postpone.mutateAsync({
        params: { path: { fixture_id: fixture.id } },
        body: { reason: reason.trim() || null },
      });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      qc.invalidateQueries({
        queryKey: $api.queryOptions("get", "/api/v1/fixtures/{fixture_id}", {
          params: { path: { fixture_id: fixture.id } },
        }).queryKey,
      });
      onOpenChange(false);
      toast.success("Match postponed");
      router.refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-w-none"
      >
        <SheetHeader className="text-left">
          <SheetTitle>Postpone this match?</SheetTitle>
          <SheetDescription>
            It stays on record for the day it was due and counts towards
            nothing. If the tie is replayed later it comes round as a new
            fixture.
          </SheetDescription>
        </SheetHeader>
        <div className="mx-auto w-full max-w-lg space-y-4 px-4 pb-2">
          <Field label="Reason (optional)">
            <Input
              className="h-11"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Waterlogged pitch"
            />
          </Field>
          <Button
            type="button"
            className="h-12 w-full"
            onClick={onConfirm}
            disabled={postpone.isPending}
          >
            {postpone.isPending ? "Postponing\u2026" : "Postpone"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
