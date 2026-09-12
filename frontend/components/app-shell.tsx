"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

function isActive(pathname: string, item: NavItem) {
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

export function AppShell({
  nav,
  brand,
  aside,
  headerRight,
  children,
}: {
  nav: NavItem[];
  /** Crest + name (or a switcher) shown top-left. */
  brand: React.ReactNode;
  /** Extra content at the bottom of the desktop sidebar (e.g. season switcher). */
  aside?: React.ReactNode;
  /** Right side of the mobile top bar. */
  headerRight?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:border-border/60 md:bg-card/40">
        <div className="flex h-16 items-center px-4">{brand}</div>
        <nav className="flex flex-1 flex-col gap-1 px-3 py-2">
          {nav.map((item) => {
            const active = isActive(pathname, item);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                  active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon className="size-4" strokeWidth={active ? 2.25 : 2} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        {aside && <div className="border-t border-border/60 p-3">{aside}</div>}
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/60 bg-background/80 px-3 backdrop-blur md:hidden">
        {brand}
        {headerRight}
      </header>

      <main className={cn("flex-1", nav.length > 0 && "pb-24 md:pb-0")}>
        <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8 md:py-10">{children}</div>
      </main>

      {nav.length > 0 && (
        <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/90 backdrop-blur md:hidden">
          <div className="mx-auto grid max-w-md pb-[env(safe-area-inset-bottom)]" style={{ gridTemplateColumns: `repeat(${nav.length}, minmax(0, 1fr))` }}>
            {nav.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium",
                    active ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  <Icon className="size-5" strokeWidth={active ? 2.5 : 2} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}

/** The club crest; a coloured dot marks which of our teams you're looking at. */
export function Crest({ colour, size = 32 }: { colour?: string | null; size?: number }) {
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <Image src="/crest.png" alt="" width={size} height={size} className="size-full object-contain" priority />
      {colour && (
        <span
          className="absolute -bottom-0.5 -right-0.5 size-3 rounded-full ring-2 ring-background"
          style={{ background: colour }}
        />
      )}
    </span>
  );
}
