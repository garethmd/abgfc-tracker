"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Auto" },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // Theme is unknown until hydration; render a placeholder on the server.
  const mounted = useSyncExternalStore(() => () => {}, () => true, () => false);
  if (!mounted) return <div className="h-10 w-48 rounded-lg bg-muted" />;

  return (
    <div className="flex rounded-lg bg-muted p-0.5 text-sm font-medium">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => setTheme(o.value)}
          className={cn("h-9 flex-1 rounded-md px-4 transition-colors", theme === o.value ? "bg-background shadow-sm" : "text-muted-foreground")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
