import { PlainShell } from "@/components/plain-shell";
import { EmptyState } from "@/components/empty-state";

export default function NoAccessPage() {
  return (
    <PlainShell>
      <EmptyState
        title="No team yet"
        description="Your account isn't attached to a team. Ask your club admin or age-group coach to add you."
      />
    </PlainShell>
  );
}
