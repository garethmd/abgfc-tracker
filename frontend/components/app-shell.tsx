"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, LayoutDashboard, Settings, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { SeasonSwitcher } from "@/components/season-switcher";

const NAV = [
  { href: "/", label: "Home", icon: LayoutDashboard },
  { href: "/fixtures", label: "Fixtures", icon: CalendarDays },
  { href: "/players", label: "Squad", icon: Users },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:border-border/60 md:bg-card/40">
        <div className="flex h-16 items-center gap-2 px-6">
          <Crest />
          <span className="font-semibold tracking-tight">ABGFC Blues</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3 py-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon className="size-4" strokeWidth={active ? 2.25 : 2} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border/60 p-3">
          <SeasonSwitcher />
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/60 bg-background/80 px-4 backdrop-blur md:hidden">
        <div className="flex items-center gap-2">
          <Crest />
          <span className="font-semibold tracking-tight">Blues</span>
        </div>
        <SeasonSwitcher compact />
      </header>

      <main className="flex-1 pb-24 md:pb-0">
        <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8 md:py-10">{children}</div>
      </main>

      {/* Mobile bottom nav: big targets, thumb reach */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/90 backdrop-blur md:hidden">
        <div className="mx-auto grid max-w-md grid-cols-4 pb-[env(safe-area-inset-bottom)]">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <Icon className="size-5" strokeWidth={active ? 2.5 : 2} />
                {label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

function Crest() {
  return (
    <span className="flex size-7 items-center justify-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">
      B
    </span>
  );
}
