# 11. Reports, exports, media, live entry and availability

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
   the fairness nudge), goals, assists, one column per award type, an *Avail* tick box —
   pre-filled from [availability](#availability-and-the-parents-message) when it has
   been recorded: ticked = available, crossed = not available (drawn, not glyphs — core
   Helvetica has no tick). The *Next match* block then also says "Available: 10 (1 not
   available) · arrive 10.30 · Adam & Dan coaching"
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

## Availability and the parents' message

Who can't play in an upcoming match (everyone else can), recorded on the phone during the
week, and the message that goes to the parents' group. `services/selections.py`, `services/messages.py`, routes
under `/fixtures/{id}/selection`, UI at `/[team]/fixtures/[id]/selection`
(`SquadSelection`), `SelectionCard` on the fixture page, `MessageSheet`.

- **Availability** (fixture page and the *Next up* card; coaches only, viewers see the
  result). Everyone in the squad starts as available; tap a player to mark them out, tap
  again to put them back. No reasons - in or out is all that's needed. *Save* confirms
  it even when nobody is out (that's what unlocks the message). Below the chips: the arrival time (kick-off minus the team-season's lead time,
  changed once in Settings → Seasons), *Coaching on the day* and *Notes for parents*.
  Saved as one `PUT`, editable until the match is played, then frozen (409). Nothing here
  touches `appearances`: knowing who *can* play is not a record of who *did*.
- **Message parents** (once availability is recorded) renders the club's house style server-side:

  ```
  REDS are home against Haslemere Town Panthers    TEAM in capitals; "are away against";
  This is an 11am kick off at Aldershot Park       neutral: "are playing". "a"/"an" by the
  Please arrive at 10.30                           spoken hour; "10.30am", "2pm"; " at <ground>"
  Adam & Dan coaching                              is the fixture's venue_notes, dropped if empty.
  Squad                                            Arrival: "10.30" / "10", no am/pm.
  Jackson                                          Coaching line omitted if empty.
  Adrian                                           Squad = the available players, one per
  ...                                              line in squad-number then name order.
                                                   Notes, if any, after one blank line, verbatim.
  ```

  *Add the date* puts "Saturday 26 September" first. No emoji, no blank lines except
  before notes. The coach can edit the text, then
  *WhatsApp* (`https://wa.me/?text=…`, which opens the app - or WhatsApp Desktop/Web on
  a computer - with the message typed and the chat picker up) or *Copy message*. A
  WhatsApp link cannot name a group, so the coach picks the U10s group themselves; there
  is deliberately no deeper WhatsApp integration (see the [roadmap](12-roadmap.md)). `tests/test_selections.py` asserts the exact text for the
  example above and every variant.
- **Every upcoming fixture, not just the next.** `FixtureRead.availability`
  (`{available, unavailable}` or null; filled in by the list route only, squad size counted
  once per team season) gives the Fixtures page a strip under each upcoming row - the
  headline plus *Availability*/*Edit* and *Message* for coaches - so a coach can plan and
  message parents for a game two or three weeks out.
- **Downstream defaults.** *Enter result* and the live *Start match* line-up start with the
  available players ticked instead of the whole squad — a default, not a change in
  behaviour; with nothing recorded they are as before. The matchday PDF pre-ticks the
  *Avail* boxes (above).
- **Kick-off time.** The screen has a `time` input for it, because fixtures imported from
  the FA list carry a placeholder (08:00, or 00:00 shown as "not set") and the real time is
  confirmed a week or so before - exactly when the coach is here recording availability.
  The arrival line recalculates as they type; *Save availability* then does two writes,
  `PATCH /fixtures/{id}` with the new `kickoff_at` first (so a failure there doesn't leave
  the two disagreeing) and the selection second. Clearing the field is a no-op - unsetting a
  time is the fixture form's job. Everything that quotes the time (parents' message,
  matchday sheet, fixtures list) follows from the fixture, so it is right everywhere.
- Times: `kickoff_at` is UK wall-clock; `arrival_time()` goes through Europe/London so a
  kick-off just after midnight or on a clock-change morning still comes out right.

## Fixture video

Matches that get filmed and posted to YouTube are watched on the fixture page, next to
the stats. `services/fixture_media.py`, routes under `/fixtures/{id}/media`, UI is
`FixtureVideos` on a played fixture.

**No new tables.** A `media` row (`kind='youtube'`, canonical `url`) plus a `media_links`
row carrying `fixture_id` and `role='match_video'` - exactly what `media_links` was built
for. Several per fixture (first half / second half / highlights), ordered by `sort_order`.

- **Pasting.** `parse_youtube_id()` takes whatever the coach pastes - `youtu.be/…` from
  the phone's share sheet, `watch?v=…&t=42s`, `/shorts/`, `/embed/`, `/live/`, or a bare
  id - and stores the canonical `https://www.youtube.com/watch?v=<id>`. Anything that
  isn't YouTube is a 422 while pasting, rather than a card that fails to play a week
  later. The same video twice on one fixture is refused.
- **Click to play.** The card shows a play button and title; the `youtube-nocookie.com`
  iframe is only mounted when someone taps it, so a page about children makes **no request
  to Google at all** until a viewer asks for the video (verified: zero iframes and zero
  requests to any Google domain before the tap). There is also an "open on YouTube" link.
- **Access** follows the fixture, like match notes: anyone who can see the fixture can
  watch, only coaches can add, retitle or remove.
- **Deleting a fixture** removes its videos. `media_links` cascades with the fixture, but
  the `media` rows it points at are its parents, not its children, so `FixtureService.delete`
  removes them explicitly - otherwise every deleted fixture left an orphan behind.
- What gets posted to YouTube, and whether it is public or unlisted, is between the club
  and the parents; the app only stores the link.

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

## Guest appearances

A child playing for another team in the age group ("Noah played for the Blacks today").
There is **no squad row**: a guest appearance is just an `appearances` row — plus any
`match_events` — on that team's fixture, which is all the schema ever needed, since both
reference the player, not the squad.

- **Recording.** *Add a guest* on *Enter result* and on the live line-up
  (`components/features/fixtures/guest-picker.tsx`) lists the age-group pool
  (`GET /players?cohort_id=`) minus whoever is already on the list, and ticks them as
  playing. The result and live flows accept any player **in the fixture's age group** —
  outside it is a mistake and 422s (`FixtureService.submit_result`, `LiveService._check_players`).
- **`is_guest` is derived, not stored**: `player_rows()` takes `member_ids` (the squad) and
  flags everyone else. A player who later joins the squad is not retrospectively a guest,
  because the flag is computed per team season from the squad as it is now.
- **Their own number travels with them.** Numbers belong to the player across the age group,
  so `StatsService._rows` fills a guest's `squad_number` from their own team's squad row
  (`SquadRepository.list_for_cohort_season`, one extra query and only when a guest played).
- **Where it shows.** The team's leaderboard (a `guest` chip, and "Squad + 1 guest" above
  the table) and the highlight tiles (a guest's goals count for the team that fielded them -
  the name reads "Noah (guest)").
- **The player's page is the footballer, not the team.** `GET /players/{id}/season-stats?season_id=`
  returns `{totals, teams}`: the headline adds up every appearance across every team in the
  age group (awards summed by type), and *By team* breaks it down a row per team, their own
  squad first, guest spells after. The page is therefore the same wherever you reach it from -
  opening Noah from the Blacks shows his whole season, not just the game he guested in.
  Memberships (`/memberships`) are now shown only for *earlier* seasons, since the breakdown
  covers the current one. The age-group overview already totalled across teams and still does.
- **Where it deliberately doesn't.** The Squad page (that's membership), the matchday
  sheet's squad table (it plans our own players, and a guest would skew the
  appearances-out-of-played fairness column), and availability - see below.
- **Named in advance on availability.** `fixture_selection_guests` (selection_id, player_id)
  holds the guests for one match, so **available = (squad + guests) - unavailable**.
  `PUT /fixtures/{id}/selection` takes `guest_player_ids` alongside `unavailable_player_ids`
  (both replaced whole); a player already in the squad is refused, and the age-group check
  is the same as everywhere else. `SelectionPlayerRead.is_guest` marks them, and they sort
  after the squad. Everything downstream then follows on its own: the **parents' message**
  lists them, the **matchday sheet** gives them a row at the bottom marked "(guest)" -
  outside the appearances-out-of-played shading, with the heading reading "Squad · N players
  + 1 guest" - and *Enter result* and the live line-up hand them over pre-ticked
  (`guestPlayers(selection)`), so nobody is added twice.

## Home grounds

`teams.home_ground` (where an opposition plays) and `club_teams.home_ground` (ours, Aldershot
Park). Both are plain text in the same shape as `fixtures.venue_notes`.

- **Copied, not looked up.** `default_ground()` in `services/fixtures.py` fills a fixture's
  `venue_notes` when it is **created** with none - ours at home, theirs away, nothing at a
  neutral - and when one is switched to the other venue while empty. After that the fixture
  owns its ground: changing a team's default never rewrites a match already arranged, which
  is what makes a one-off venue (a waterlogged pitch, a cup tie elsewhere) safe. An explicit
  blank stays blank.
- **The form shows what it will use**: the default appears as the ground field's placeholder
  with a line saying so, and typing over it is the override.
- **The FA import**: the FA's venue is for that match, so it wins; our stored ground only
  fills a gap. When the FA gives a venue for an away match against an opposition we have no
  ground for, the import **learns** it (fills a blank, never overwrites) and the result says
  how many it set. If the FA venue disagrees with what we have, the preview row says so
  (`ground_note`) - that is how an away fixture listed at our own ground gets spotted.
- **Edited** in Settings → Seasons (ours, at the top) and Settings → Opposition (theirs).
- **Maps.** Two halves, both keyless:
  - *Directions*: `components/ground-link.tsx` makes a ground a Google Maps **search link**,
    which opens the Maps app on a phone. No API key needed for a link.
  - *The map itself*: `components/ground-map.tsx` embeds **OpenStreetMap**. OSM rather than
    Google's Embed API because it needs no API key, no billing account and loads no
    third-party tracker into an app full of children's names. `GET /grounds/lookup?q=`
    (`services/grounds.py`) geocodes through Nominatim and caches the answer - misses
    included - in `grounds`, keyed by the normalised search text, so a name is looked up
    once ever and a one-off venue maps as readily as a league ground. A geocoder that is
    down or a ground nobody can place is not an error: the map just doesn't appear and the
    directions link carries on.
  - `map_query()` (backend, mirrored in the frontend link) drops the pitch off the end
    ("Hook Junior School 7v7" is searched as "Hook Junior School"), since the pitch matters
    on the day but not to a geocoder. `candidates()` then tries up to three things, best
    first: the name as written, the **postcode on its own** when the text contains one, and
    the name shorn of its postcode and trailing word. That is what rescues the two shapes
    Nominatim gives up on - an abbreviation glued to a postcode ("Grayshott Rec, GU26 6LS")
    and a trailing generic word ("Zebon Copse Centre") - and it stops at the first hit, with
    a second between requests as Nominatim asks.

## Opposition head-to-head

`GET /teams/{id}/head-to-head?club_team_id=` — `TeamService.head_to_head`. Every fixture
against one opposition team across all seasons, restricted to our teams the caller can
see (`access.visible_team_ids()`), optionally to one club team. Returns the opposition
row, a `TeamRecord` over the played ones, form (oldest → newest), and three lists:
`played` (newest first), `upcoming`, `other` (postponed/cancelled/abandoned), each item
carrying our team's name, season and competition so the list reads across seasons.

UI: `/[team]/opposition` (every opposition team; ABGFC badge on derby rows) and
`/[team]/opposition/[id]` (record card, form pips, the three lists linking to fixture
pages). Users with more than one team get a *this team / All ABGFC* toggle. Linked from
the opposition name on a fixture page and from Settings → Opposition.

## Importing fixtures from FA Full-Time

**Why paste, not fetch.** The FA site sits behind Cloudflare and challenges everything
that isn't a real, headed browser session — plain requests, browser-like headers and
headless Chromium all get a 403 (tested from a home IP and the droplet). There is no
official feed (no iCal/RSS/JSON), and the ECAL "sync to calendar" widget is present but
disabled for the NEHYL. Scraping would be fragile and against the FA's terms, so the
coach copies the fixtures table from the page and pastes it into the app. If the league
ever enables calendar sync, that ICS feed could drive the same matcher automatically.

**Parsing** (`services/imports.py::parse_fa_fixtures`). The page's copy carries both the
plain text (tab-separated; team names appear twice because of the logo cells) and HTML.
The import page captures the clipboard's `text/html` on paste; the HTML rows include
`displayFixture.html?id=…` links, which become `fixtures.external_id` (unique) — the
stable key for re-imports. Plain text works too, just without ids. Dates are `dd/mm/yy`.

**Matching.** `norm()` lower-cases, drops age tokens (U10M, U9) and punctuation;
`similarity()` is 1.0 for equal normalised names, 0.9 when one token set contains the
other ("Hook Tigers" ⊂ "Hook U10M Tigers"), else Jaccard overlap — so "Haslemere Town
Harriers" v "Haslemere Town Panthers" scores 0.5, not a match. Threshold 0.8 for
opposition, 0.75 for competitions ("U10M Conference League Group Stage" → "Conference
League"). Abbreviations the coaches typed ("CPR Hawks") don't match and are left for the
coach to pick. Rows where one side is another of our club teams are flagged as a derby
and the new opposition row is linked via `club_team_id`.

**Classification.** For the target team season: `skip` when neither side is this team;
`existing` when the FA id is already stored or a fixture exists on the same date against
a matching opponent (only `venue_notes` and `external_id` are filled if blank; kick-off,
status, scores untouched); `conflict` when the date is taken by a different opponent;
otherwise `create`. The preview writes nothing.

**Apply.** Per-row decisions (`ImportRowDecision`): create (existing opposition/
competition ids or new names — new opposition names get the age token stripped, new
competitions default to type league), update, or skip. Match numbers continue from the
team's highest. Re-pasting the same table yields all `existing` / "nothing to change".

**Merging duplicate opposition.** `POST /teams/{id}/merge {into_team_id}` re-points every
fixture and deletes the source, filling blank details on the target; requires coach on
every club team that has played the source. UI: Settings → Opposition → Edit → "Merge
into…".
