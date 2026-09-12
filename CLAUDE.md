# ABGFC Blues — team stats

Stats app for Aldershot Boys & Girls FC Blues (Under-10s, 7-a-side, rolling subs).
Replaces a Google Sheet. Coaches enter results on a phone at the side of the pitch;
the app derives everything else (record, form, leaderboards, awards).

**Children's data.** Everything sits behind a login; media (when added) is served
through the API from a private volume, never a public bucket. No league tables —
the FA doesn't allow them at U10, so the app only ever reports our own record.

## Running it

```bash
make install        # uv sync + npm install
make seed           # migrate, coach login, and the real 2026/27 season from the sheet
make seed-demo      # or: reset and load the fictional demo season the tests use
make dev            # API on :8000, Next on :3000 (both hot reload)
```

Login is `coach` / `changeme` (override with `ABGFC_COACH_PASSWORD`, see `.env.example`).
Other targets: `make test`, `make lint`, `make api-client`, `make check-api`, `make up` (docker compose).

If port 3000 is busy, `npm run dev -- -p 3001` works; the API is reached through Next
rewrites (`/api/*` → `BACKEND_URL`), so the frontend port doesn't matter.

## Layout

```
backend/   FastAPI + SQLAlchemy 2 + Alembic, managed by uv (Python 3.13)
  app/models/         ORM. One module per aggregate; enums in enums.py
  app/schemas/        Pydantic v2 request/response models
  app/repositories/   All queries. Nothing else touches the session
  app/services/       Business rules + stats.py (pure functions) + bootstrap.py (seed data)
  app/api/routers/    Thin routes: parse → service → schema
  alembic/versions/   Migrations (batch mode on, SQLite can't ALTER)
  scripts/            seed.py, export_openapi.py
  tests/              pytest; conftest builds an in-memory DB per test
frontend/  Next.js 16 App Router + TypeScript + Tailwind 4 + shadcn (radix)
  app/(app)/          Authenticated pages behind the AppShell
  app/login/
  components/features/<area>/   Feature components; components/ui/ is shadcn
  lib/api/            openapi.json → schema.d.ts (generated) → client.ts ($api hooks)
  lib/season-context.tsx        Selected season (persisted in localStorage)
  proxy.ts            Cookie-presence redirect to /login (Next 16's middleware)
data/      SQLite file + media (gitignored; docker volume in compose)
```

## Data model — the important part

Derived numbers are the point of the app, so the schema is built around **events**,
not spreadsheet columns. Full DDL is in `backend/alembic/versions/`; rationale here.

| Table | Purpose / decision |
|---|---|
| `seasons` | First-class. Everything hangs off a season; `match_minutes` is the default match length. One `is_current` (enforced in `SeasonService`). |
| `players` | A person, not a squad slot. Never hard-deleted — set `left_date`. Stats survive a player leaving because appearances/events reference the player, not the squad row. |
| `squad_members` | Player ↔ season, with `squad_number` and `primary_position_id`. Unique per (season, player); partial-unique on (season, number). Lets 2027/28 sit next to 2026/27 without forking. |
| `positions` | Lookup (GK/DEF/MID/FWD + `category`). Finer positions later = rows sharing a category. |
| `competitions` | Global lookup with `type` (league/cup/friendly/tournament). "League-only" stats filter on the type, so a second league competition needs no code. |
| `teams` | Opposition. We are not a row; fixtures are always us-vs-them. Enables head-to-head later. |
| `fixtures` | `season_id` is explicit (not derived via competition) so stats queries are one filter. `our_score`/`their_score` are **stored** as well as derivable — at pitchside you know the score before the scorers. `stats.score_warnings()` reports mismatches instead of blocking. |
| `appearances` | One row per player per fixture (`started`, `position_id`, `shirt_number`, `captain`). Unique (fixture, player). This is what the app writes today. |
| `player_stints` | Rolling-sub detail: `(appearance_id, on_minute, off_minute NULL=to the end, position_id)`. Hangs off the appearance so a stint can't exist for someone who didn't play. `stats.minutes_for_appearance()` already computes minutes; nothing writes stints yet. |
| `match_events` | `goal` / `assist` / `own_goal` / `opp_own_goal` with `player_id` (NULL only for `opp_own_goal`), `minute`, `sequence`. **An assist is its own row pointing at its goal via `related_event_id`.** Goals and assists are `COUNT(*)`s. A goal is therefore an addressable thing a YouTube clip can attach to. |
| `award_types` / `awards` | Two rows today (`coaches_potm`, `parents_potm`). A third award is a row. `scope` (match/month/season) + nullable `fixture_id` + `period_label` cover "goal of the month". Joint winners allowed: uniqueness is (type, fixture, player). |
| `media` / `media_links` | Designed, unused. `media(kind: youtube/photo/file, url | storage_key, …)`. `media_links` has **three nullable FKs** (`fixture_id`, `player_id`, `match_event_id`) with a CHECK that exactly one is set — real FKs and cascades, unlike `target_type/target_id`. A player photo is a link with `role='profile_photo'`. |
| `users` | argon2 hash, `role`. Seeded with one `coach`; more coaches are rows. Session = signed HttpOnly cookie (`itsdangerous`). |

Conventions: integer PKs, `created_at`/`updated_at` on mutable tables, enums as
`String` + `CHECK` (values in `models/enums.py`, mirrored by Pydantic), FK
enforcement via `PRAGMA foreign_keys=ON` on every connection (`db/session.py`),
deterministic constraint names (`db/base.py`).

### How the four future features land

1. **Player cards** — `squad_members` per season + `media_links(role=profile_photo)` +
   `GET /players/{id}/stats?season_id=`. Add a `GET /players/{id}/seasons` aggregate.
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
`/api/docs`. The one that matters: **`PUT /fixtures/{id}/result`** takes the whole
result (score, appearances, goals+assists, awards) in one transactional write and marks
the fixture played — that's the under-a-minute flow, and it's idempotent so it can be
queued offline later. Errors are `{"detail": "..."}` with 404/409/422/401.

Frontend types are generated: `make api-client` (exports `openapi.json` without a
running server, then `openapi-typescript`). CI should run `make check-api`.
`lib/api/client.ts` wraps `openapi-fetch` + `openapi-react-query`; query keys are
`["get", "/api/v1/…"]` so `invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] })`
covers every fixture query.

## Frontend notes

- Mobile-first: bottom nav, 44px+ targets, sticky save button above the nav,
  bottom sheets for pick-lists. Desktop gets a sidebar at `md`.
- Dark mode via `next-themes` (class strategy); one accent (`--primary`, club blue)
  used for CTAs and active states only.
- Auth: `proxy.ts` only checks the cookie exists; the API validates it, and
  `client.ts` hard-redirects to `/login` on any 401.
- Season selection lives in `SeasonProvider` and localStorage.
- Next 16: `params` are Promises (`use(params)`), `LayoutProps`/`PageProps` are generated
  by `next typegen`, read `frontend/node_modules/next/dist/docs` before assuming APIs.
- Offline/optimistic writes are not built yet; TanStack Query is the seam
  (persist the mutation cache + `onMutate` on the result submit).

## Out of scope (deliberately)

CSV import from the sheet, media upload/routes, league tables.
