"use client";

import Link from "next/link";
import { useState } from "react";
import { ClipboardList, MessageCircle, Pencil } from "lucide-react";
import { $api, type Schema } from "@/lib/api/client";
import { Card } from "@/components/stat-card";
import { SectionTitle } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageSheet } from "@/components/features/fixtures/message-sheet";
import { arrivalTime, selectionSummary } from "@/components/features/fixtures/squad-selection";

type Fixture = Schema["FixtureRead"];
type Selection = Schema["SelectionRead"];

/** Availability on a scheduled fixture's page: who can play, arrival, coaching, notes -
 *  and the two coach actions, Availability and Message parents. */
export function SelectionCard({ fixture, base, canEdit }: { fixture: Fixture; base: string; canEdit: boolean }) {
  const q = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}/selection", { params: { path: { fixture_id: fixture.id } } });
  const [message, setMessage] = useState(false);

  if (q.isPending) return <Skeleton className="mt-8 h-32 rounded-xl" />;
  if (q.error) return null;
  const sel = q.data;
  if (!sel && !canEdit) return null;

  return (
    <section className="mt-8">
      <SectionTitle>Availability</SectionTitle>
      <Card className="p-4">
        {sel ? (
          <>
            <div className="tnum text-sm font-medium">{selectionSummary(sel)}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {fixture.kickoff_at.endsWith("T00:00:00")
                ? "Kick-off time not set"
                : `Arrive ${arrivalTime(fixture.kickoff_at, sel.arrival_lead_minutes)}`}
              {sel.coaching && <> · {sel.coaching} coaching</>}
            </div>
            <dl className="mt-4 space-y-2 text-sm">
              <Group label="Can play" people={sel.available} />
              <Group label="Can't" people={sel.unavailable} withReason />
            </dl>
            {sel.notes && <p className="mt-4 whitespace-pre-wrap text-sm text-muted-foreground">{sel.notes}</p>}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Not recorded yet. Mark who can play and send the parents the details.</p>
        )}
        {canEdit && (
          <div className={sel ? "mt-4 grid grid-cols-2 gap-2" : "mt-4"}>
            {sel && (
              <Button type="button" className="h-11" onClick={() => setMessage(true)}>
                <MessageCircle className="size-4" /> Message parents
              </Button>
            )}
            <Button asChild variant="outline" className="h-11 w-full">
              <Link href={`${base}/fixtures/${fixture.id}/selection`}>
                {sel ? <><Pencil className="size-4" /> Edit</> : <><ClipboardList className="size-4" /> Availability</>}
              </Link>
            </Button>
          </div>
        )}
      </Card>
      {canEdit && <MessageSheet fixtureId={fixture.id} open={message} onOpenChange={setMessage} />}
    </section>
  );
}

function Group({ label, people, withReason }: { label: string; people: Selection["available"]; withReason?: boolean }) {
  if (people.length === 0) return null;
  return (
    <div className="flex gap-3">
      <dt className="w-16 shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="min-w-0 flex-1">
        {people.map((p, i) => (
          <span key={p.player.id}>
            {i > 0 && ", "}
            {p.player.display_name}
            {withReason && p.reason && <span className="text-muted-foreground"> ({p.reason.toLowerCase()})</span>}
          </span>
        ))}
      </dd>
    </div>
  );
}
