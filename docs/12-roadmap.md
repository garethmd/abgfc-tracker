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
"subs" step on the result screen (or a live match clock), writing stints per appearance.
The cohort overview's *Mins* column then lights up.

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

**Share to WhatsApp.** A *Share* button that builds "Blues v Alton, Sat 08:00, Aldershot
Park — squad: …" and hands it (plus optionally the PDF) to the phone's share sheet
(`navigator.share`). No integration, no ToS issue. Group posting via the official API is
not viable; unofficial clients are ruled out for this app.

**Weekly email of the matchday sheet.** A cron on the droplet (or GitHub Action) hitting
the PDF endpoint with a service credential and emailing it. Needs an email provider.

## Platform

**Offline / optimistic entry.** `PUT /fixtures/{id}/result` is idempotent by design.
Persist TanStack Query's mutation cache (`persistQueryClient` + `onMutate`) so a result
saved without signal is retried when the phone reconnects, and the fixture page shows
the optimistic result meanwhile.

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
