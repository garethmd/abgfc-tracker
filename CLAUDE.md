# ABGFC Blues — team stats

Stats app for Aldershot Boys & Girls FC (started with the U10 Blues; now built for
the whole age group - Blues, Blacks, Reds, Whites - and future seasons). Coaches enter
results on a phone at the side of the pitch; the app derives everything else (record,
form, leaderboards, awards).

**Team-first.** A team coach signs in and sees only their team - no switcher, no other
teams' children. An age-group coach (Stuart) sees every team in the cohort plus a
cohort overview. A club admin sees everything and manages coaches.

**Children's data.** Everything sits behind a login and every query is scoped by the
caller's roles (`services/access.py`); media (when added) is served through the API
from a private volume, never a public bucket. No league tables — the FA doesn't allow
them at U10, so the app only ever reports our own teams' records.

## Running it

```bash
make install        # uv sync + npm install
make seed           # migrate, coach login, and the real 2026/27 season from the sheet
make seed-demo      # or: reset and load the fictional demo season the tests use
make dev            # API on :8000, Next on :3000 (both hot reload)
```

Login is `coach` / `changeme` - the club admin (override with `ABGFC_COACH_PASSWORD`, see
`.env.example`). Add coaches at `/admin`: team scope for a team coach, cohort scope for an
age-group coach.
Other targets: `make test`, `make lint`, `make api-client`, `make check-api`, `make up` (docker compose).

If port 3000 is busy, `npm run dev -- -p 3001` works; the API is reached through Next
rewrites (`/api/*` → `BACKEND_URL`), so the frontend port doesn't matter.

## Layout

```
backend/   FastAPI + SQLAlchemy 2 + Alembic, managed by uv (Python 3.13)
  app/models/         ORM. One module per aggregate; enums in enums.py; club.py = cohorts/teams
  app/schemas/        Pydantic v2 request/response models
  app/repositories/   All queries. Nothing else touches the session
  app/services/       Business rules; access.py (who sees what), stats.py (pure functions),
                      club.py (cohorts, teams, season roll-over), users.py, bootstrap.py (seeds)
  app/api/routers/    Thin routes: parse → service → schema
  alembic/versions/   Migrations (batch mode on, SQLite can't ALTER)
  scripts/            seed.py, export_openapi.py
  tests/              pytest; conftest builds an in-memory DB per test
frontend/  Next.js 16 App Router + TypeScript + Tailwind 4 + shadcn (radix)
  app/(app)/          Authenticated. layout loads /auth/me -> MeProvider; page.tsx routes
    [team]/           Everything a coach uses: dashboard, fixtures, players, settings
    cohorts/[id]/     Age-group overview (Stuart): team records + player game time + moves
    admin/            Coaches (users/roles/password reset), age groups & teams
    teams/            Picker for people with several teams
  app/login/
  components/features/<area>/   Feature components; components/ui/ is shadcn
  lib/api/            openapi.json → schema.d.ts (generated) → client.ts ($api hooks)
  lib/me-context.tsx            Signed-in user + what they can reach; homeFor() picks the landing page
  lib/team-context.tsx          Current team + selected team-season; sets the team's accent colour
  proxy.ts            Cookie-presence redirect to /login (Next 16's middleware)
data/      SQLite file + media (gitignored; docker volume in compose)
```

## Data model — the important part

Derived numbers are the point of the app, so the schema is built around **events**,
not spreadsheet columns. Full DDL is in `backend/alembic/versions/`; rationale here.

| Table | Purpose / decision |
|---|---|
| `cohorts` | An age group independent of season ("Born 2016/17", `birth_year_start`). U10 this year, U11 next: `Cohort.age_group_for(season)`. Teams and players belong to a cohort; so does the age-group coach's role. |
| `club_teams` | Our teams (Blues/Blacks/Reds/Whites) - `cohort_id`, `slug` (URL: `/blues`), `colour` (accent). Not to be confused with `teams` (opposition). |
| `seasons` | Club-wide: "2026/27" + dates. Nothing hangs off it directly any more. |
| `team_seasons` | A club team in a season: `age_group`, `format`, `match_minutes`, `is_current` (one per team). **This is what squads, fixtures, awards and stats hang off**, and what a coach is looking at. Roll-over (`TeamSeasonService.start`) creates it, derives the age group, and can copy the squad forward. |
| `players` | A person in a cohort (`cohort_id`), not a squad slot. Never hard-deleted — set `left_date`. Stats survive a player leaving or moving because appearances/events reference the player, not the squad row. |
| `squad_members` | Player ↔ team-season, with `squad_number`, `primary_position_id`, `left_at`. Moving a child between teams mid-season = `left_at` here and a new row on the other team (`POST /players/{id}/move`, cohort coaches). |
| `users` / `user_roles` | Login + roles at a scope: `club` (scope_id NULL), `cohort`, or `team`. Roles: viewer < coach < admin. Widen upwards - a cohort coach is a coach on every team in the cohort. Resolved per request into `Access` (`services/access.py`). Admins manage users only within scopes they administer. |
| `positions` | Lookup (GK/DEF/MID/FWD + `category`). Finer positions later = rows sharing a category. |
| `competitions` | Global lookup with `type` (league/cup/friendly/tournament). "League-only" stats filter on the type, so a second league competition needs no code. |
| `teams` | Opposition. We are not a row; fixtures are always us-vs-them. Enables head-to-head later. |
| `fixtures` | Keyed by `team_season_id`. `our_score`/`their_score` are **stored** as well as derivable — at pitchside you know the score before the scorers. `stats.score_warnings()` reports mismatches instead of blocking. A derby (Blues v Blacks) is two rows, one per team; `teams.club_team_id` links the opposition row to our own team. |
| `appearances` | One row per player per fixture (`started`, `position_id`, `shirt_number`, `captain`). Unique (fixture, player). This is what the app writes today. |
| `player_stints` | Rolling-sub detail: `(appearance_id, on_minute, off_minute NULL=to the end, position_id)`. Hangs off the appearance so a stint can't exist for someone who didn't play. `stats.minutes_for_appearance()` already computes minutes; nothing writes stints yet. |
| `match_events` | `goal` / `assist` / `own_goal` / `opp_own_goal` with `player_id` (NULL only for `opp_own_goal`), `minute`, `sequence`. **An assist is its own row pointing at its goal via `related_event_id`.** Goals and assists are `COUNT(*)`s. A goal is therefore an addressable thing a YouTube clip can attach to. |
| `award_types` / `awards` | Two club-wide rows today (`coaches_potm`, `parents_potm`, `club_team_id NULL`). A team's own award ("Blues most improved") is a row with `club_team_id` set - only that team sees it. `scope` (match/month/season) + nullable `fixture_id` + `period_label` cover "goal of the month". Awards are keyed by `team_season_id`. Joint winners allowed. |
| `media` / `media_links` | Designed, unused. `media(kind: youtube/photo/file, url | storage_key, …)`. `media_links` has **three nullable FKs** (`fixture_id`, `player_id`, `match_event_id`) with a CHECK that exactly one is set — real FKs and cascades, unlike `target_type/target_id`. A player photo is a link with `role='profile_photo'`. |

Conventions: integer PKs, `created_at`/`updated_at` on mutable tables, enums as
`String` + `CHECK` (values in `models/enums.py`, mirrored by Pydantic), FK
enforcement via `PRAGMA foreign_keys=ON` on every connection (`db/session.py`),
deterministic constraint names (`db/base.py`).

### Access rules (services/access.py)

- Team-scoped data (team-season, squad, fixtures, stats): role on that team ≥ viewer to read,
  ≥ coach to write. Role on a team = max(club role, cohort role, direct team role).
- Players: anyone in the cohort can see names (so squads can pull from the cohort pool);
  editing needs coach+ on the cohort or on a team whose squad the player is in.
- Cohort overview and player moves between teams: cohort-level coach+.
- Users: an admin sees/creates users only within scopes they administer; the last club
  admin can't demote themselves.
- The frontend hides what you can't do (`canEdit`, `isAdminSomewhere`), but the API is
  the enforcement point - every test in `tests/test_access.py` hits the API directly.

### How the four future features land

1. **Player cards** — `squad_members` per team-season + `media_links(role=profile_photo)` +
   `GET /players/{id}/stats?team_season_id=` + `GET /players/{id}/memberships` (history).
2. **Media** — write `media` + `media_links`; add `/media` routes and an authenticated
   file endpoint reading from `settings.media_dir`. The goal-clip case is
   `media_links.match_event_id`.
3. **Positions per appearance** — `appearances.position_id` exists; expose it in the
   entry flow (currently sent as `null`).
4. **Time on pitch** — write `player_stints`; `PlayerStatsRow.minutes` already flips from
   `None` to a number once every appearance has stints.

## Stats

`backend/app/services/stats.py` is pure functions over loaded rows (`team_record`,
`form`, `player_rows`, `highlights`, `minutes_for_appearance`, `score_warnings`) plus
`StatsService` that loads via repositories. `tests/test_stats.py` asserts hand-checked
totals for the demo season in `services/bootstrap.py` — the docstring there is the
answer key. If you change aggregation, change both.

Rules worth knowing: only `status='played'` fixtures with both scores count; form is
the last five played, chronological; leaderboard sorts goals → assists → apps → name;
highlight tiles list every tied name and show `—` at zero; league-only filters
`competition.type == 'league'`; minutes are `None` until every appearance has stints.

## API

`/api/v1`, all routes need the session cookie except `POST /auth/login`. Docs at
`/api/docs`. `GET /auth/me` returns the user plus every team/cohort they can reach
(with their role and the team's current team-season) - the client routes off it.
Team-scoped resources live under `/team-seasons/{id}/...` (squad, stats); fixtures take
`?team_season_id=`; the age-group view is `GET /cohorts/{id}/overview?season_id=`.
The one that matters: **`PUT /fixtures/{id}/result`** takes the whole
result (score, appearances, goals+assists, awards) in one transactional write and marks
the fixture played — that's the under-a-minute flow, and it's idempotent so it can be
queued offline later. Errors are `{"detail": "..."}` with 404/409/422/401.

Frontend types are generated: `make api-client` (exports `openapi.json` without a
running server, then `openapi-typescript`). CI should run `make check-api`.
`lib/api/client.ts` wraps `openapi-fetch` + `openapi-react-query`; query keys are
`["get", "/api/v1/…"]` so `invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] })`
covers every fixture query.

## Reports

`backend/app/services/reports.py` renders the **matchday sheet**: one A4 page for the
next (or a given) fixture - fixture details and previous meetings, season record,
last match with scorers and both POTMs, the squad with appearances-out-of-played
(fewest shaded, the fairness nudge), an "available" tick box per player and a ruled plan box.
`GET /team-seasons/{id}/reports/matchday.pdf?fixture_id=`; coaches only, since it
names children. Pure Python (fpdf2, core Helvetica, so stick to Latin-1 text); the
crest is `app/assets/crest.png`. Tests extract the text with pypdf and assert on it -
no golden files. The UI links to it from the Fixtures "Next up" card and a fixture's
page; same-origin, so it's a plain `<a download>`.

## Deploying (DigitalOcean droplet)

Production is one $6 droplet in London (`abgfc`, 1GB, Ubuntu 24.04), running
`docker-compose.prod.yml`: Caddy (automatic Let's Encrypt) → Next → API. **The API has
no public port**; Next proxies `/api/*` to it over the compose network. SQLite and
media live on the droplet at `/data`. Images are built by `.github/workflows/images.yml`
on every push to `main` and pushed to GHCR (`ghcr.io/garethmd/abgfc-tracker-{api,web}`,
tagged `latest` + commit SHA) - the 1GB box runs the app but can't build it.

- **First time**: `doctl auth init`; register a key with `doctl compute ssh-key create`;
  `SSH_KEY_ID=… make droplet` (uses `deploy/cloud-init.yaml`: key-only SSH for the
  `deploy` user, ufw 22/80/443, unattended upgrades, fail2ban, Docker, 2GB swap, repo at
  `/opt/abgfc`). Then write `/opt/abgfc/.env` (mode 600) from `.env.production.example`
  and run `make deploy`.
- **Secrets** live only in `/opt/abgfc/.env` on the box. `ABGFC_ENV=production` makes the
  API refuse the dev secret key / coach password, hides `/api/docs`, and sets `Secure`
  cookies. Locally, the gitignored `.env.production` holds `DEPLOY_HOST=deploy@<ip>` and
  the initial admin password.
- **Deploy**: `make deploy` = ssh, `git pull`, pull images, `up -d`. Also `make prod-logs`,
  `make prod-shell`. Roll back with `IMAGE_TAG=<sha>` in the box's `.env` + `make deploy`.
- Hostname for now is `<ip>.sslip.io`; the custom domain is issue #4, backups #2, CI deploy #3.

## Frontend notes

- Mobile-first: bottom nav, 44px+ targets, sticky save button above the nav,
  bottom sheets for pick-lists. Desktop gets a sidebar at `md`.
- Dark mode via `next-themes` (class strategy); one accent (`--primary`, club blue)
  used for CTAs and active states only.
- Auth: `proxy.ts` only checks the cookie exists; the API validates it, and
  `client.ts` hard-redirects to `/login` on any 401. Sign-in and sign-out are full
  reloads so no query cache survives a user switch on a shared phone.
- URLs carry the team (`/blues/fixtures`). `(app)/page.tsx` sends a single-team coach
  straight to their team; the team switcher only appears when there is somewhere else
  to go. Selected season per team lives in localStorage (`team-context.tsx`).
- The team's `colour` becomes `--primary` inside `TeamProvider` (`.team-accent` in
  globals.css lifts it in dark mode).
- Next 16: `params` are Promises (`use(params)`), `LayoutProps`/`PageProps` are generated
  by `next typegen`, read `frontend/node_modules/next/dist/docs` before assuming APIs.
- Offline/optimistic writes are not built yet; TanStack Query is the seam
  (persist the mutation cache + `onMutate` on the result submit).

## Out of scope (deliberately)

CSV import from the sheet, media upload/routes, league tables.
