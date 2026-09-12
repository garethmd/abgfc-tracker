import Link from "next/link";
import type { Schema } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const STYLE: Record<"W" | "D" | "L", string> = {
  W: "bg-emerald-500/15 text-emerald-700 ring-emerald-500/30 dark:text-emerald-400",
  D: "bg-muted text-muted-foreground ring-border",
  L: "bg-rose-500/15 text-rose-700 ring-rose-500/30 dark:text-rose-400",
};

export function FormPips({ form, size = "md", base = "" }: { form: Schema["FormEntry"][]; size?: "sm" | "md"; base?: string }) {
  if (!form.length) {
    return (
      <div className="flex gap-1.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <span key={i} className="size-8 rounded-full border border-dashed border-border" />
        ))}
      </div>
    );
  }
  return (
    <div className="flex gap-1.5">
      {form.map((f) => (
        <Link
          key={f.fixture_id}
          href={`${base}/fixtures/${f.fixture_id}`}
          title={`${f.our_score}–${f.their_score} v ${f.opposition}`}
          className={cn(
            "flex items-center justify-center rounded-full text-xs font-semibold ring-1 transition-transform active:scale-95",
            size === "md" ? "size-8" : "size-6 text-[10px]",
            STYLE[f.result],
          )}
        >
          {f.result}
        </Link>
      ))}
    </div>
  );
}
