# 12. Roadmap and design seams

Things the schema and code were built to accommodate but that aren't finished, with the
concrete path for each. Ordered roughly by value.

## Parent onboarding: the unfinished half

Parents can be invited, can sign in and can be removed, and that is in production. What
follows was specified alongside it (each decision tied to a named standard — the reasoning
lives in [Parents](13-parents.md)) and not built. In order:

1. **A common-password deny list.** The highest-priority item in this file. Cyber
   Essentials v3.3 allows an 8-character minimum **only** where common passwords are
   blocked automatically, and that is the minimum we ship — so right now the policy is
   half-implemented, and the half that is missing is the half doing the work. A word list
   in the repo (the top few thousand from a public breach corpus is plenty at club scale),
   checked in `schemas/auth.py` alongside `min_length`, with the message naming the
   problem: *"that password appears in lists attackers try first"*. Comparison should be
   case-folded and should also catch the obvious padding (`password1`, `Password!`).
2. **Offer a passkey during onboarding.** FIDO's guidance is to prompt at account creation
   and after a recovery, not during sign-in. Today the only offer is Settings → Signing in,
   which a parent has to go looking for — and the 30-day session means roughly twelve
   sign-ins a season, which is exactly when a one-touch option earns its place. One
   skippable screen after `accept` (and after a reset), "Not now" equally prominent, and a
   failure there is a shrug rather than an error: registration is unreliable inside
   WhatsApp's WebView, which is precisely why the passkey can never be the only way in.
   This screen existed in the passkey-only version and was removed with it (`f63a6fa`).
3. **A second child should need the existing password, not an email.** `_claim_existing`
   currently spends the invitation and emails a sign-in link, because the address might not
   be the inviter's to claim. OWASP's rule for linking an identity to an existing account
   is an authenticated session with that account: ask for the password on the spot instead,
   and **don't spend the invitation** when it fails.
4. **Show the address back, and mark the ones that never arrived.** The welcome screen
   should repeat the address the parent will sign in with — a typo is otherwise discovered
   30 days later, at the worst moment — and the Parents tab should flag an invitation whose
   email bounced or was never sent, since a send failure is deliberately not fatal.
5. **Smaller things.** Label the login field "Email address or username"; list outstanding
   invitations for a coach so a lost one is visible; drop the vestigial
   `users.allow_email_signin`; fix the docstrings in `services/auth.py` and
   `api/routers/auth.py` that still say parents have no password.

## Operational

**Photo backups.** `/data/media` isn't in the nightly SQLite backup. Extend
`deploy/backup.sh` to `tar` the media folder alongside the DB (same retention) and
`make backup` to pull it. Small; do this before photos accumulate.

**Session revocation on a password change.** Both halves of this are now built — login is
throttled (`core/ratelimit.py`) and `users.session_version` rides in the cookie — except
that `POST /auth/change-password` doesn't bump it, so a voluntary change leaves other
devices signed in. A password *reset* does. One line in `AuthService.change_password`.

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

**Fixture photos and goal clips.** YouTube video on a fixture is **done** (see
[Features](11-features.md#fixture-video)). Still open: photo/file uploads on a fixture
(generalise the `PlayerPhotoService` pipeline, keep files behind the authenticated
endpoint) and a "clip" link per goal, which is a `media_links` row with `match_event_id`
plus a button on each goal row.

**Month/season awards.** `award_types.scope` and `awards.period_label` support "Goal of
the month" without a fixture. Needs a small UI to award them and a place to show them.

## Integrations

**Parse a pasted match report into a draft result.** Match notes already capture the
text. Send note + squad + fixture to Claude, get `ResultSubmit` back, open the result
screen pre-filled for the coach to confirm. Never write without confirmation. Needs an
Anthropic API key as a server secret.

**Share to WhatsApp.** Done as *Message parents* ([Features](11-features.md#availability-and-the-parents-message)):
the text is built server-side and handed to WhatsApp's `wa.me` link (or copied). Group posting
via the official API is not viable; unofficial clients are ruled out for this app. Next
steps if wanted: a **scheduled reminder** — a
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

**Parents as viewers.** Done — see [Parents](13-parents.md). Invited by email or a
WhatsApp link, they choose a password on the way in and hold `viewer` at cohort scope. The
product questions were answered by the club: parents see everything a viewer can across
the whole age group, and nothing is withheld. The onboarding *flow* is not finished —
below.

**Parents contributing to their own child.** The `player_guardians` link exists and grants
nothing yet. The intended next step: a guardian may add a photo, a note or a video to
*their own* child and no one else's — gated on the link, never on a role, and never
extending to `display_name`, `squad_number` or `left_date`. Needs one decision first:
whether a parent's contribution is visible to the whole team or only to coaches and that
parent. `players.notes` stays coach admin; parent text belongs in its own table with an
author.

## Explicitly out of scope

- League tables (FA rule at U10)
- CSV import from the old Google Sheet (the season was seeded directly instead)
- Unofficial WhatsApp automation
