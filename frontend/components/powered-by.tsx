import { cn } from "@/lib/utils";

/** Who built the thing. Quiet, but on every way in and at the foot of every page -
 *  parents and coaches mostly live on one screen, so a single placement would never
 *  be seen. */
export function PoweredBy({ className }: { className?: string }) {
  return (
    <p className={cn("text-center text-xs text-muted-foreground", className)}>
      Powered by{" "}
      <a
        href="https://neuralaspect.com"
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline-offset-4 hover:underline"
      >
        Neural Aspect
      </a>
    </p>
  );
}
