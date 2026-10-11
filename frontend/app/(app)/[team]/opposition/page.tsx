"use client";

import { PageHeader } from "@/components/page-header";
import { OppositionList } from "@/components/features/opposition/opposition-list";

export default function OppositionListPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Opposition"
        description="Every team we've played or are due to play. Tap one for the head-to-head."
      />
      <OppositionList />
    </div>
  );
}
