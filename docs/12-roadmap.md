# 12. Roadmap and design seams

Things the schema and code were built to accommodate but that aren't finished, with the
concrete path for each. Ordered roughly by value.

## Operational

**Photo backups.** `/data/media` isn't in the nightly SQLite backup. Extend
`deploy/backup.sh` to `tar` the media folder alongside the DB (same retention) and
`make backup` to pull it. Small; do this before photos accumulate.

**Login rate limiting and session revocation.** See [Security → Known gaps](08-security.md#known-gaps-recommended-next-steps).
Rate limit: a small in-memory/SQLite counter keyed by IP and username in
`AuthService.authenticate`. Revocation: add `users.session_version`, include it in the
cookie payload, bump on password change/reset.

**Automated off-box backup.** A GitHub Action (cron) that SSHes in and commits the nightly
copy to a *private* repo — free, and removes the "remember to run `make backup`" step.

## Features designed into the schema

**Positions per appearance.** `appearances.position_id` exists and the API accepts it in
`ResultSubmit`; the entry UI sends `null`. Add a position chip per selected player on the
result screen (default from `squad_members.primary_position_id`). The PDF and player page
can then show a position breakdown.

**Time on pitch (rolling subs).** `player_stints(appearance_id, on_minute, off_minute,
position_id)` exists; `stats.minutes_for_appearance` computes minutes and
`PlayerStatsRow.minutes` flips from `None` once every appearance has stints. Needed: a
"subs" step on the result screen, or subs + a clock on the live screen
(`services/live.py` - a sub would close the leaver's stint and open one for the player
coming on; kick-off would give starters a stint from minute 0), writing stints per
appearance. The cohort overview's *Mins* column then lights up. If a starters/bench
split is ever wanted before kick-off, a `bench` flag on the availability rows is the
place; today it only records who's out.

**Captain as a first-class field.** `appearances.captain` exists but nothing writes it;
the Blues record the captain as a team award ("Captain", `club_team_id` set), which
works through the existing POTM chips and counts on the leaderboard. Making it
first-class means a captain picker on the result screen (and the live line-up), a
captaincies column, and a one-off script that converts the existing Captain award rows
into `appearances.captain` and deactivates the award type. Until then, keep the award
convention - don't write `appearances.captain` from one path and not the other.

**Player cards.** Photos, memberships history and per-season stats exist. Add: a
season-by-season block (`GET /players/{id}/memberships` + stats per team season),
milestones (first goal, 10th appearance — derive from events/appearances), form (last
five appearances with G/A).

**Fixture media and goal clips.** `media` + `media_links` handle `fixture_id` and
`match_event_id` already. Add `POST /fixtures/{id}/media` (YouTube URL or file via the
same `PlayerPhotoService` pipeline generalised), list on the fixture page, and a "clip"
link on each goal row (`GoalLine`). Keep files behind the authenticated endpoint.

**Month/season awards.** `award_types.scope` and `awards.period_label` support "Goal of
the month" without a fixture. Needs a small UI to award them and a place to show them.

## Integrations

**Parse a pasted match report into a draft result.** Match notes already capture the
text. Send note + squad + fixture to Claude, get `ResultSubmit` back, open the result
screen pre-filled for the coach to confirm. Never write without confirmation. Needs an
Anthropic API key as a server secret.

**Share to WhatsApp.** Done as *Message parents* ([Features](11-features.md#availability-and-the-parents-message)):
the text is built server-side and handed to `navigator.share` (or copied). Group posting
via the official API is not viable; unofficial clients are ruled out for this app. Next
steps if wanted: attach the matchday PDF to the share, and a **scheduled reminder** — a
cron hitting `GET /fixtures/{id}/selection/message` for the coming Saturday and emailing
it to the coach (the template is reusable by design; needs an email provider). A per-match
override of the arrival lead time would be a nullable column on `fixture_selections`.

**Weekly email of the matchday sheet.** A cron on the droplet (or GitHub Action) hitting
the PDF endpoint with a service credential and emailing it. Needs an email provider.

## Platform

**Offline / optimistic entry.** `PUT /fixtures/{id}/result` is idempotent by design, and
the live endpoints are small (goals are retry-safe via `sequence`). Persist TanStack
Query's mutation cache (`persistQueryClient` + `onMutate`) so a result or a live goal
saved without signal is retried when the phone reconnects, and the page shows the
optimistic state meanwhile. Today live goals retry twice on a network error and the
screen refetches on focus; a persisted queue is the next step.

**Postgres.** Only if SQLite becomes limiting (it won't at club scale). Portability
work: boolean `server_default="1"` → `true`, the partial unique index needs
`postgresql_where`, add `psycopg`, re-verify migrations. `DATABASE_URL` is already the
only switch.

**Parents as viewers.** The `viewer` role exists. Missing: self-signup/invite flow,
per-child visibility (a parent should see only their child's photo?), and a decision on
what parents may see. Product question before code.

## Explicitly out of scope

- League tables (FA rule at U10)
- CSV import from the old Google Sheet (the season was seeded directly instead)
- Unofficial WhatsApp automation
