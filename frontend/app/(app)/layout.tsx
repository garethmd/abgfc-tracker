import { AppShell } from "@/components/app-shell";
import { SeasonProvider } from "@/lib/season-context";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <SeasonProvider>
      <AppShell>{children}</AppShell>
    </SeasonProvider>
  );
}
