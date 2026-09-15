# 11. Reports, exports and media

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
