"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ExternalLink, Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { useTeam } from "@/lib/team-context";
import { formatDate } from "@/lib/format";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Row = Schema["ImportRow"];
type Decision = Schema["ImportRowDecision"];

const NEW = "__new__";

const ACTION_STYLE: Record<Row["action"], string> = {
  create: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  existing: "bg-muted text-muted-foreground",
  conflict: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  skip: "bg-muted text-muted-foreground",
};
const ACTION_LABEL: Record<Row["action"], string> = { create: "New", existing: "Already in", conflict: "Check", skip: "Other team" };

export default function ImportFixturesPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { team, teamSeason, base } = useTeam();
  const [text, setText] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const preview = $api.useMutation("post", "/api/v1/team-seasons/{team_season_id}/fixtures/import/preview");
  const apply = $api.useMutation("post", "/api/v1/team-seasons/{team_season_id}/fixtures/import");
  const teams = $api.useQuery("get", "/api/v1/teams");
  const comps = $api.useQuery("get", "/api/v1/competitions");
  const [rows, setRows] = useState<Row[] | null>(null);
  // Per line: opposition choice (team id | NEW | SKIP), competition choice (id | NEW), include flag
  const [opp, setOpp] = useState<Record<number, string>>({});
  const [comp, setComp] = useState<Record<number, string>>({});
  const [include, setInclude] = useState<Record<number, boolean>>({});

  function onPaste(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    // The clipboard's HTML keeps the FA fixture links (stable ids); plain text doesn't.
    const h = e.clipboardData.getData("text/html");
    setHtml(h && h.includes("<tr") ? h : null);
  }

  async function onPreview() {
    if (!teamSeason) return;
    try {
      const p = await preview.mutateAsync({ params: { path: { team_season_id: teamSeason.id } }, body: { text: text || null, html } });
      setRows(p.rows);
      const o: Record<number, string> = {}, c: Record<number, string> = {}, inc: Record<number, boolean> = {};
      for (const r of p.rows) {
        o[r.line] = r.opposition ? String(r.opposition.id) : NEW;
        c[r.line] = r.competition ? String(r.competition.id) : NEW;
        inc[r.line] = r.action === "create" || r.action === "existing";
      }
      setOpp(o); setComp(c); setInclude(inc);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onApply() {
    if (!teamSeason || !rows) return;
    const decisions: Decision[] = rows.map((r) => {
      const base: Decision = {
        line: r.line, action: "skip", date: r.date, time: r.time, our_venue: r.our_venue, venue_notes: r.venue_notes,
        external_id: r.external_id, status: r.status, existing_fixture_id: r.existing_fixture_id, derby_club_team_id: r.derby_club_team_id,
      };
      if (!include[r.line] || r.action === "skip") return base;
      if (r.action === "existing") return { ...base, action: "update" };
      const o = opp[r.line], c = comp[r.line];
      return {
        ...base,
        action: "create",
        opposition_team_id: o && o !== NEW ? Number(o) : null,
        new_opposition_name: o === NEW ? r.opposition_raw : null,
        competition_id: c && c !== NEW ? Number(c) : null,
        new_competition_name: c === NEW ? cleanCompetition(r.competition_raw) : null,
        new_competition_type: c === NEW ? guessType(r.competition_raw) : null,
      };
    });
    try {
      const res = await apply.mutateAsync({ params: { path: { team_season_id: teamSeason.id } }, body: { rows: decisions } });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/teams"] });
      qc.invalidateQueries({ queryKey: ["get", "/api/v1/competitions"] });
      const extras = [
        res.new_teams.length ? `${res.new_teams.length} new opposition` : null,
        res.new_competitions.length ? `${res.new_competitions.length} new competition${res.new_competitions.length > 1 ? "s" : ""}` : null,
      ].filter(Boolean).join(", ");
      toast.success(`Imported ${res.created} fixture${res.created === 1 ? "" : "s"}, updated ${res.updated}${extras ? ` (${extras})` : ""}`);
      router.push(`${base}/fixtures`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const toImport = rows ? rows.filter((r) => include[r.line] && r.action === "create").length : 0;
  const toUpdate = rows ? rows.filter((r) => include[r.line] && r.action === "existing").length : 0;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Import fixtures" description={`${team.name} · ${teamSeason?.season.name ?? ""} · from FA Full-Time`} />

      {!rows ? (
        <Card className="space-y-4 p-5">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Open your team&apos;s fixtures on <a href="https://fulltime.thefa.com" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-foreground underline">FA Full-Time <ExternalLink className="size-3" /></a> and set <em>Date: All</em>.</li>
            <li>Select the whole fixtures table (drag from &ldquo;Type&rdquo; to the last row) and copy it.</li>
            <li>Paste below. Nothing is saved until you&apos;ve checked the preview.</li>
          </ol>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onPaste={onPaste}
            rows={10}
            placeholder={"Type\tDate / Time\tHome Team\t\tAway Team\tVenue\tCompetition\nL\t19/09/26 08:00\tAldershot B&G U10M Blacks\t…"}
            className="font-mono text-xs"
          />
          {html && <p className="text-xs text-muted-foreground"><Check className="mr-1 inline size-3" />Pasted from the FA page — fixture ids captured, so re-importing later won&apos;t duplicate.</p>}
          <Button className="h-11 w-full" onClick={onPreview} disabled={!text.trim() || preview.isPending}>
            {preview.isPending ? "Checking…" : "Preview"}
          </Button>
        </Card>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="secondary">{toImport} to add</Badge>
            <Badge variant="secondary">{toUpdate} to update</Badge>
            {rows.some((r) => r.action === "conflict") && <Badge className="bg-amber-500/15 text-amber-700 hover:bg-amber-500/15 dark:text-amber-400">{rows.filter((r) => r.action === "conflict").length} need a look</Badge>}
            <span className="flex-1" />
            <Button variant="ghost" size="sm" onClick={() => setRows(null)}>Start again</Button>
          </div>

          <Card className="divide-y divide-border/40 overflow-hidden">
            {rows.map((r) => {
              const on = include[r.line] && r.action !== "skip";
              return (
                <div key={r.line} className={cn("space-y-2 px-4 py-3", !on && "opacity-60")}>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      disabled={r.action === "skip"}
                      onClick={() => setInclude((m) => ({ ...m, [r.line]: !m[r.line] }))}
                      className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg ring-1 ring-border", on ? "bg-primary text-primary-foreground ring-primary" : "bg-background text-muted-foreground")}
                      aria-label={on ? "Exclude" : "Include"}
                    >
                      {on ? <Check className="size-4" /> : <Minus className="size-4" />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {formatDate(r.date)}{r.time && r.time !== "00:00" ? `, ${r.time}` : ""} · {r.our_venue === "home" ? "H" : r.our_venue === "away" ? "A" : ""} v {r.opposition_raw ?? `${r.home} v ${r.away}`}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">{[r.competition_raw, r.venue_notes].filter(Boolean).join(" · ")}</p>
                    </div>
                    <span className={cn("shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold", ACTION_STYLE[r.action])}>{ACTION_LABEL[r.action]}</span>
                  </div>
                  {r.reason && (
                    <p className={cn("ml-11 flex items-start gap-1 text-xs", r.action === "conflict" ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground")}>
                      {r.action === "conflict" && <AlertTriangle className="mt-0.5 size-3 shrink-0" />}{r.reason}
                    </p>
                  )}
                  {on && (r.action === "create" || r.action === "conflict") && (
                    <div className="ml-11 grid gap-2 sm:grid-cols-2">
                      <Select value={opp[r.line]} onValueChange={(v) => setOpp((m) => ({ ...m, [r.line]: v }))}>
                        <SelectTrigger className={cn("h-10 w-full min-w-0", !r.opposition && "ring-1 ring-amber-500/40")}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NEW}><span className="flex items-center gap-1"><Plus className="size-3" /> Create &ldquo;{stripAge(r.opposition_raw)}&rdquo;</span></SelectItem>
                          {(teams.data ?? []).map((t) => (
                            <SelectItem key={t.id} value={String(t.id)}>{t.name}{r.opposition?.id === t.id ? ` (match ${Math.round(r.opposition.confidence * 100)}%)` : ""}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select value={comp[r.line]} onValueChange={(v) => setComp((m) => ({ ...m, [r.line]: v }))}>
                        <SelectTrigger className={cn("h-10 w-full min-w-0", !r.competition && "ring-1 ring-amber-500/40")}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NEW}><span className="flex items-center gap-1"><Plus className="size-3" /> Create &ldquo;{cleanCompetition(r.competition_raw)}&rdquo; ({guessType(r.competition_raw)})</span></SelectItem>
                          {(comps.data ?? []).filter((c) => c.is_active).map((c) => (
                            <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              );
            })}
          </Card>

          <div className="sticky bottom-20 z-20 mt-4 md:static">
            <Button className="h-12 w-full shadow-lg md:w-auto md:shadow-none" onClick={onApply} disabled={apply.isPending || (toImport + toUpdate === 0)}>
              {apply.isPending ? "Importing…" : `Import ${toImport} fixture${toImport === 1 ? "" : "s"}${toUpdate ? ` and update ${toUpdate}` : ""}`}
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Kick-off times come from Full-Time as listed (08:00 is often a placeholder) — edit a fixture afterwards for the real time. Existing fixtures are never changed except to fill in a missing ground or FA id.
          </p>
          <p className="mt-1 text-xs text-muted-foreground"><Link href={`${base}/opposition`} className="underline">Opposition list</Link> — merge duplicates there if the same club appears twice.</p>
        </>
      )}
    </div>
  );
}

/** "Mytchett Athletic U10M Kestrels" → "Mytchett Athletic Kestrels" (the server does the same). */
function stripAge(name: string | null | undefined): string {
  return (name ?? "").split(/\s+/).filter((t) => !/^U\d{1,2}[A-Z]?$/i.test(t)).join(" ");
}

/** "U10M Conference League Group Stage" → "Conference League"; "U10M Pele" → "U10M Pele" (the coaches kept those). */
function cleanCompetition(raw: string | null | undefined): string {
  if (!raw) return "";
  const s = raw.replace(/\s+Group Stage$/i, "").trim();
  return /league/i.test(s) ? s.replace(/^U\d{1,2}[A-Z]?\s+/i, "") : s;
}

function guessType(raw: string | null | undefined): Schema["CompetitionType"] {
  const s = (raw ?? "").toLowerCase();
  if (/cup|trophy|shield|champions league|europa/.test(s)) return "cup";
  if (/friendly/.test(s)) return "friendly";
  if (/tournament|festival/.test(s)) return "tournament";
  return "league";
}
