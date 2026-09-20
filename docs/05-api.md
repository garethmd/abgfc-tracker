# 5. API reference

Base path `/api/v1`. JSON in and out except the two report downloads and the photo
endpoints. Interactive docs at `/api/docs` in development only.

## Authentication

- `POST /auth/login` `{username, password}` → sets the `abgfc_session` cookie (HttpOnly,
  SameSite=Lax, Secure in production, 30 days) and returns `MeRead`.
- Every other route requires the cookie; missing/invalid → `401 {"detail": "..."}`.
- `POST /auth/logout` clears the cookie. `GET /auth/me` returns the caller and what they
  can reach. `POST /auth/change-password` `{current_password, new_password}`.

`MeRead` drives the frontend's routing:

```json
{
  "id": 1, "username": "coach", "display_name": "Club admin",
  "roles": [{"role": "admin", "scope_type": "club", "scope_id": null}],
  "club_role": "admin",
  "cohorts": [{"cohort": {"id": 1, "name": "Born 2016/17", ...}, "role": "admin"}],
  "teams": [{"team": {"id": 1, "name": "Blues", "slug": "blues", "colour": "oklch(...)", ...},
             "role": "admin", "current_team_season_id": 1}, ...]
}
```

## Errors

Always `{"detail": <string or validation list>}`.

| Status | Raised by | Meaning |
|---|---|---|
| 401 | `AuthError` | not signed in / session expired / bad credentials |
| 403 | `ForbiddenError` | signed in but outside your scope or below the required role |
| 404 | `NotFoundError` | no such row (or not on that parent, e.g. note not on that fixture) |
| 409 | `ConflictError` | uniqueness: season name, squad number, match number, username… |
| 422 | `ValidationError` / Pydantic | bad input; Pydantic errors are a list of `{loc, msg, type}` |

## Access summary

Role on a team = max(club role, cohort role for the team's cohort, direct team role).
Reads need `viewer`, writes `coach`, admin operations `admin` — within the relevant scope.
Full rules in [Security](08-security.md).

## Endpoints

### Club structure

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/cohorts` | any | cohorts you can see |
| POST | `/cohorts` | club admin | `{name, birth_year_start?}` |
| PATCH | `/cohorts/{id}` | club admin | |
| GET | `/cohorts/{id}/overview?season_id=` | cohort viewer | `CohortOverview`: per-team records + per-player totals across teams |
| GET | `/club-teams?cohort_id=` | any | teams you can see |
| POST | `/club-teams` | cohort admin | `{cohort_id, name, slug?, colour?, sort_order?}`; slug auto-suffixed on clash |
| GET | `/club-teams/by-slug/{slug}` | team viewer | |
| GET/PATCH | `/club-teams/{id}` | viewer / team admin | |
| GET | `/club-teams/{id}/seasons` | team viewer | newest first |
| POST | `/club-teams/{id}/seasons` | team coach | `TeamSeasonStart`: `{season_id | season_name, age_group?, format?, match_minutes, copy_squad_from_team_season_id?, make_current}` |
| GET/PATCH | `/team-seasons/{id}` | viewer / coach | PATCH: `age_group, format, match_minutes, arrival_lead_minutes` (0–180) |
| POST | `/team-seasons/{id}/make-current` | coach | |
| GET | `/seasons`, `/seasons/{id}` | any | club-wide |
| POST | `/seasons` | any signed-in | `{name, start_date?, end_date?}` |
| PATCH/DELETE | `/seasons/{id}` | club admin | delete refused while in use |

### Squad and players

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/team-seasons/{id}/squad` | team viewer | `SquadMemberRead[]` incl. `left_at` |
| PUT | `/team-seasons/{id}/squad/{player_id}` | team coach | upsert `{squad_number?, primary_position_id?, joined_at?, left_at?}`; player must be in the team's cohort; 409 on number clash |
| DELETE | `/team-seasons/{id}/squad/{player_id}` | team coach | |
| GET | `/players?cohort_id=&include_left=` | any | players in cohorts you can see |
| POST | `/players` | cohort or team coach | `{first_name, …, cohort_id? \| team_season_id?, squad_number?}`; `team_season_id` also adds to the squad |
| GET/PATCH | `/players/{id}` | cohort viewer / coach of a squad they're in | PATCH incl. `left_date` |
| GET | `/players/{id}/memberships` | viewer | `MembershipRead[]` — team/season history you can see |
| GET | `/players/{id}/stats?team_season_id=` | team viewer | `PlayerStatsRow` |
| POST | `/players/{id}/move` | cohort coach | `{from_team_season_id, to_team_season_id, left_at?, squad_number?}` |
| PUT | `/players/{id}/photo` | coach | multipart `file`; returns `PlayerRead` with new `photo_key` |
| GET | `/players/{id}/photo?size=full\|thumb` | viewer | `image/jpeg`, `Cache-Control: private` |
| DELETE | `/players/{id}/photo` | coach | |

### Lookups

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/positions` | any | |
| GET | `/award-types?club_team_id=&active_only=` | any | club-wide + that team's |
| POST | `/award-types` | club admin (club-wide) / team coach (`club_team_id` set) | `{name, club_team_id?, scope}` |
| PATCH | `/award-types/{id}` | same | `{name?, is_active?}` |
| GET/POST/PATCH/DELETE | `/competitions[/{id}]` | any signed-in | delete refused while fixtures use it |
| GET/POST/PATCH/DELETE | `/teams[/{id}]` | any signed-in | opposition; delete refused while fixtures use it |
| GET | `/teams/{id}/head-to-head?club_team_id=` | any (scoped) | `HeadToHead`: record, form, `played` (newest first), `upcoming`, `other` — only fixtures of our teams the caller can see; `club_team_id` narrows to one team (403 if not yours) |

### Fixtures and results

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/fixtures?team_season_id=&competition_id=&status=` | viewer | only fixtures of teams you can see |
| POST | `/fixtures` | team coach | `FixtureCreate`; `match_number` auto if omitted |
| GET | `/fixtures/{id}` | viewer | `FixtureDetail`: appearances, `goals` (assist folded in), awards, `warnings` |
| PATCH | `/fixtures/{id}` | coach | 422 if set to `played` without both scores |
| DELETE | `/fixtures/{id}` | coach | cascades appearances, events, awards, notes |
| **PUT** | **`/fixtures/{id}/result`** | coach | **the post-match write** — see below |
| GET/POST | `/fixtures/{id}/notes` | viewer / coach | `MatchNoteRead[]`; `{body, author?, sent_at?}` |
| PATCH/DELETE | `/fixtures/{id}/notes/{note_id}` | coach | 404 if the note isn't on that fixture |
| POST | `/fixtures/{id}/live/start` | coach | `LiveSquad {player_ids}` → `status=live`, 0-0; 409 unless `scheduled` |
| PUT | `/fixtures/{id}/live/squad` | coach | `LiveSquad`; 422 if it drops someone with a goal/assist |
| POST | `/fixtures/{id}/live/goals` | coach | `LiveGoal` = `GoalInput` + `sequence`; bumps the score; same `sequence` again = same goal (retry-safe), other goal at a used `sequence` = 409 |
| DELETE | `/fixtures/{id}/live/goals/{event_id}` | coach | undo: removes goal + assist, decrements the score |
| POST/DELETE | `/fixtures/{id}/live/against` | coach | opposition goal (`their_score` ± 1; no event) |
| POST | `/fixtures/{id}/live/finish` | coach | `status=played`; the fixture is now exactly what `PUT /result` produces |
| DELETE | `/fixtures/{id}/live` | coach | started by mistake: clears everything, back to `scheduled` |
| GET | `/fixtures/{id}/selection` | viewer | `SelectionRead` or `null` — pre-match availability (below) |
| PUT | `/fixtures/{id}/selection` | coach | `SelectionSubmit` = who's out (+ coaching, notes); replaces the whole thing; 409 unless `scheduled`/`postponed`; 422 for a player outside the team's cohort |
| DELETE | `/fixtures/{id}/selection` | coach | 404 if there isn't one |
| GET | `/fixtures/{id}/selection/message?date_line=` | coach | `{text}` — the parents' message in the house style listing the available players; 404 until availability is recorded |

`ResultSubmit`:

```json
{
  "our_score": 2, "their_score": 1,
  "appearances": [{"player_id": 3, "started": true, "position_id": null, "shirt_number": null, "captain": false}, ...],
  "goals": [
    {"event_type": "goal", "scorer_id": 3, "assisted_by_id": 7, "minute": 12, "notes": null},
    {"event_type": "opp_own_goal", "scorer_id": null, "assisted_by_id": null}
  ],
  "awards": [{"award_type_id": 1, "player_id": 3}, {"award_type_id": 2, "player_id": 3}, {"award_type_id": 2, "player_id": 5}]
}
```

Validation: scorers, assisters and award winners must appear in `appearances`; a player
can't assist their own goal; own goals can't be assisted; `opp_own_goal` has no player;
award types must be match-scoped and visible to the team. Replaces the fixture's whole
result and sets `status=played`. Score/scorer disagreements come back as `warnings` on
the detail, not errors.

**Live entry** (`/fixtures/{id}/live/*`, `services/live.py`) writes the same result one
tap at a time. Every call returns the full `FixtureDetail`. While a fixture is `live`,
`PUT /result` answers 409 ("finish it first") and `PATCH` can't set the status to `live`;
`finish` moves it to `played`, after which the post-match screen is used as normal for
the awards and any corrections. Viewers see the running score through `GET /fixtures/{id}`.

**Pre-match availability** (`services/selections.py`): everyone in the squad can play
unless the coach marks them out — separate from `appearances`, which only the result
flows write.

```json
PUT {"unavailable_player_ids": [9], "coaching": "Adam & Dan", "notes": "Bring both kits"}

GET → {"fixture_id": 12,
       "available": [{"player": {...}, "squad_number": 1}, ...],   // the squad minus those out
       "unavailable": [{"player": {...}, "squad_number": 9}],
       "arrival_at": "2026-09-26T10:30:00", "arrival_lead_minutes": 30,
       "coaching": "Adam & Dan", "notes": "Bring both kits", "updated_at": "..."}
```

Each list is in squad-number then name order. `arrival_at` is kick-off minus the
team-season's `arrival_lead_minutes`, computed in Europe/London and returned as naive
wall-clock like `kickoff_at`. The message endpoint renders `services/messages.py` — the
frontend never holds a copy of the template.

### Stats

| Method | Path | Returns |
|---|---|---|
| GET | `/team-seasons/{id}/stats/summary` | `SeasonSummary`: `overall` + `league` `TeamRecord`, `form` (last 5, chronological), `highlights` (tiles with every tied name) |
| GET | `/team-seasons/{id}/stats/leaderboard?competition_type=league` | `Leaderboard`: `award_types` (column headers) + `rows` (`PlayerStatsRow`) |

### Reports

| Method | Path | Access | Returns |
|---|---|---|---|
| GET | `/team-seasons/{id}/reports/matchday.pdf?fixture_id=` | coach | one-page A4 PDF, `Content-Disposition: attachment` |
| GET | `/team-seasons/{id}/reports/season.xlsx` | coach | the season in the original sheet's layout |

### Users (admin)

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/users` | any admin | users whose every role is within scopes you administer |
| POST | `/users` | any admin | `{username, display_name?, password, roles: [{role, scope_type, scope_id}]}`; each role must be grantable by you |
| GET/PATCH | `/users/{id}` | same | PATCH `{display_name?, is_active?}`; can't deactivate yourself |
| PUT | `/users/{id}/roles` | same | replaces all roles; last club admin can't demote themselves |
| POST | `/users/{id}/password` | same | admin reset `{new_password}` |

### Meta

`GET /api/health` → `{"status": "ok"}` (no auth; used by Docker and the deploy).

## Generated client

`make api-client` exports the schema (`backend/scripts/export_openapi.py`, no server
needed) to `frontend/lib/api/openapi.json` and runs `openapi-typescript` with
`--default-non-nullable false` (so fields with defaults are optional on input). CI runs
`make check-api` and fails on drift. Never hand-edit `schema.d.ts`.
