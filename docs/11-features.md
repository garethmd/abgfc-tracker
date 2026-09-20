# 11. Reports, exports, media and live entry

## Matchday sheet (PDF)

`GET /team-seasons/{id}/reports/matchday.pdf?fixture_id=` — `services/reports.py`.
Coaches only (names children). fpdf2, core Helvetica (Latin-1 text only), the crest from
`app/assets/crest.png`, the team's colour (converted from oklch → sRGB in
`oklch_to_rgb`) for the header rule.

One A4 page:

1. Header — crest, "ABGFC Blues", age group · season · print date
2. **Next match** (or the given fixture) — day/time v opponent, home/away + ground,
   competition, match number, "Already played them: Drew 2-2 on Sat 12 Sep", fixture notes
3. **Season so far** (All and League P/W/D/L/GF/GA, last 5) beside **Last match**
   (result, scorers with assists, Coaches' and Parents' POTM)
4. **Squad table** — #, player, position, apps *out of matches played* (fewest shaded:
   the fairness nudge), goals, assists, one column per award type, an *Avail* tick box
5. Ruled **Plan / team talk** box filling the rest of the page

`gather()` collects the data (fixture, previous meetings, played fixtures, last match
detail, leaderboard rows); `render()` lays it out. Row height adapts to squad size
(≤12 / ≤15 / more). Tests extract text with `pypdf` and assert on it — no golden files.

UI: *Sheet* button beside *Enter result* on the Fixtures "Next up" card; ⋯ → *Matchday
sheet (PDF)* on a fixture. Plain `<a download>` — same origin, cookie goes along.

## Season spreadsheet (XLSX)

`GET /team-seasons/{id}/reports/season.xlsx` — `services/exports.py`, openpyxl. Coaches
only. Reproduces the coaches' original Google Sheet:

| Tab | Contents |
|---|---|
| Summary | title, record (all / league), last 5, squad table, highlights, about-this-file |
| Fixtures | 40 rows: match #, date, competition **type** (League/Cup/…), opposition, scores, Result (formula), scorers, both POTMs, notes (competition name · venue · ground · kick-off · status) |
| Match Stats | one row per player per played match with goals/assists/POTM Y flags; opposition looked up by formula |
| Appearances | one row per match, one column per squad player (header formulas from Squad), Y per appearance, "# Played" formula |
| Squad | player names, notes (#number · position · left date) |

Styling copied from the original: Arial, navy `1A3670` headers with white bold text,
grey `EEF0F3` calculated cells, `E0E9F5` totals, `ddd dd mmm yyyy` dates, W/D/L
conditional colours, dropdown validations, frozen panes, column widths.

**Formulas vs values.** Records, squad totals, results and lookups are live formulas
using only Excel-2007-era functions (`COUNTIF(S)`, `SUMIF(S)`, `INDEX/MATCH`, `VLOOKUP`,
`IFERROR`) so they evaluate in Excel, Numbers, Google Sheets and LibreOffice. The
original used Google-only `FILTER`/`TEXTJOIN`/`ARRAYFORMULA` for the scorers column,
last-5 and highlight *names*; the app writes those as values with a cell comment saying
so. The highlight *counts* remain formulas.

Verification: `test_exports.py` recalculates the file with LibreOffice (when installed)
and asserts the Summary equals `StatsService` for the demo season. After any formula
change run that test locally.

UI: spreadsheet button in the dashboard header; sheet icon per season in Settings →
Seasons (so past seasons export too).

## Match notes

`match_notes` table; `GET/POST /fixtures/{id}/notes`, `PATCH/DELETE …/{note_id}` —
`services/notes.py`. A note is verbatim text (typically a WhatsApp match report) with
optional `author` and `sent_at`; `created_by` records the coach who pasted it. Ordered by
`sent_at` (falling back to when added). Reads follow the fixture's team access; writes
need coach. Cascade with the fixture.

UI: *Match report* section on a played fixture's page (`MatchNotes` component) — bottom
sheet with a paste box, *From*, *Sent*; edit/delete per note for coaches. Distinct from
the fixture's one-line `notes` field (pitch/kit admin).

## Live match entry

A second way to record a match, alongside the post-match screen (which is unchanged).
`services/live.py`, routes under `/fixtures/{id}/live`, UI at `/[team]/fixtures/[id]/live`
(`LineUp` + `LiveMatch` in `components/features/fixtures/live-match.tsx`).

- **Start match** (fixture page and the *Next up* card, next to *Enter result*) → pick
  who's playing → *Kick off*. The fixture becomes `status=live`
  with `appearances` (all `started`) and a 0-0 score. No new tables: the result is
  written into its usual columns as it happens.
- **Goal** opens the same scorer → assist bottom sheet as the result screen and writes a
  `match_events` row (+ assist) immediately; **Against** bumps `their_score` (opposition
  goals have no event type); **Undo** reverses the last of either, and any goal row can be
  removed. Each write returns the whole `FixtureDetail`, which the screen drops into the
  query cache - nothing is held only in the browser, so a locked phone or a reload just
  shows the server's state. Goals carry a client `sequence`, so a retried request can't
  double-count. The page also polls every 15s while live, for a second phone watching.
- **Change squad** for a late arrival or no-show (anyone with a goal or assist stays).
- **Full time** → `status=played`, then straight to the existing *Edit result* screen for
  the POTM chips (and the captain, where a team records that as an award - see the
  [roadmap](12-roadmap.md)). From there on it is indistinguishable from a match entered
  after the game.
- **Discard live match** (⋯ menu) puts the fixture back to `scheduled` with nothing recorded.
- The two paths can't clash: `start` needs `scheduled`; `PUT /result` is refused while
  `live`; the UI shows only *Continue live match* on a live fixture. The fixtures list shows
  a red *Live* badge and the running score; the stats engine ignores `live` (only `played`
  counts).

No clock and no minutes: that's the *time on pitch* item on the [roadmap](12-roadmap.md).

## Player profile photos

`PUT /players/{id}/photo` (multipart `file`), `GET /players/{id}/photo?size=full|thumb`,
`DELETE` — `services/media.py::PlayerPhotoService`.

Pipeline on upload: size limit 15MB → `Image.open` (JPEG/PNG/WebP/HEIC via
`pillow-heif`) → `exif_transpose` (apply rotation) → convert to RGB → **re-encode** as
JPEG q85 at 1200px longest edge (`-full`) and a 256px centre-cropped square (`-thumb`).
Re-encoding drops all metadata (GPS, device). Files go to
`<media_dir>/players/<player_id>/<uuid>-{full,thumb}.jpg`, mode 600. A `media` row
(`kind=photo`, `storage_key=players/<id>/<uuid>`) and a `media_links` row
(`player_id`, `role=profile_photo`) are written; replacing deletes the old row and files.

`PlayerRead.photo_key` / `PlayerSummary.photo_key` expose the uuid so the UI can build
`…/photo?size=thumb&v=<key>` — a URL that changes on every upload (media ids get reused by
SQLite, so they're not a safe cache key). Responses carry `Cache-Control: private,
max-age=86400` and an ETag.

Access: view = player's cohort visible; upload/delete = coach on the cohort or on a team
whose squad has the player.

UI: `PlayerAvatar` (photo or initials) on the squad list and player page; `PhotoPicker`
(Add/Change/Remove, `<input type=file accept="image/*">` so phones offer camera or
library) on the player page for coaches. The upload uses `fetchClient.PUT` with a
`FormData` body and a pass-through `bodySerializer`.

Backups: **not** covered by the SQLite backup — see [Roadmap](12-roadmap.md).
