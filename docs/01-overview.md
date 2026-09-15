# 1. Overview

## Purpose

Aldershot Boys & Girls FC runs several teams per age group (at Under-10: Blues, Blacks,
Reds, Whites). Each has a coach or two who, until this app, kept a Google Sheet of
fixtures, results, scorers, appearances and player-of-the-match awards. The app replaces
the sheet with something a coach can update one-handed on a phone in the rain, and that
derives every number rather than having it typed.

Design priorities, in order:

1. **A clean, extensible data model.** Contributions are events, not columns; seasons and
   teams are first-class; nothing is hard-deleted. See [Data model](03-data-model.md).
2. **Correct derived numbers.** The stats engine is pure functions with a hand-checked
   oracle. See [Stats engine](07-stats.md).
3. **Mobile-first entry.** Post-match entry in under a minute, large touch targets, works
   as a home-screen app.
4. **Children's data handled properly.** Everything behind a login, every query scoped to
   what the caller may see, photos never on a public URL. See [Security](08-security.md).

Deliberately **not** built: league tables (the FA doesn't permit them at U10), CSV import
from the old sheet, and any integration that would need an unofficial WhatsApp client.

## Who uses it

| Role in the club | Role in the app | What they see |
|---|---|---|
| Team coach (e.g. Blues coach) | `coach` at **team** scope | Only their team: fixtures, squad, results entry, reports, team settings. No switcher, no other teams' children. |
| Age-group coach (Stuart) | `coach` at **cohort** scope | Every team in the age group, plus the cohort overview (records side by side, game time per player across teams) and player moves between teams. |
| Club admin (Gareth) | `admin` at **club** scope | Everything, plus `/admin`: coaches, roles, password resets, age groups and teams. |
| Parent (future) | `viewer` at team scope | Read-only view of one team. Accounts exist as a role; there is no self-signup. |

Roles widen upwards: a cohort coach is implicitly a coach on every team in the cohort.
See [Security & access](08-security.md#roles-and-scopes).

## Domain vocabulary

Use these words in code, commits and conversation — they map one-to-one to tables.

| Term | Meaning |
|---|---|
| **Cohort** | An age group as a group of children, independent of season: "Born 2016/17". U10 this season, U11 next. `Cohort.age_group_for(season)` derives the label. |
| **Club team** | One of *our* teams: Blues, Blacks, Reds, Whites. Belongs to a cohort. Has a URL slug (`/blues`) and an accent colour. |
| **Season** | Club-wide: "2026/27" with start/end dates. |
| **Team season** | A club team's participation in a season. **Everything a coach looks at hangs off this**: squad, fixtures, awards, stats. Carries age group, format (7v7), default match length. |
| **Player** | A child. Belongs to a cohort, never hard-deleted (`left_date`). |
| **Squad member** | A player in a team season, with squad number, primary position, `left_at`. Moving a child between teams mid-season = `left_at` on one row, a new row on the other. |
| **Fixture** | A match for one team season against an **opposition team** (`teams` table). Scores are stored *and* derivable from events. |
| **Appearance** | A player played in a fixture. One row per player per fixture. |
| **Stint** | A continuous spell on the pitch within an appearance (rolling subs). Designed, not yet written by the UI. |
| **Match event** | A goal, assist, own goal or opposition own goal. An assist is its own row pointing at its goal. |
| **Award** | A player winning an **award type** (Coaches' POTM, Parents' POTM, or a team's own) for a fixture. Joint winners allowed. |
| **Match note** | A free-text report (typically a WhatsApp message) attached to a fixture. |
| **Media** | A photo/file/YouTube link, attached to exactly one of: fixture, player, match event. Used today for player profile photos. |
| **Opposition team** | A row in `teams`. *Not* one of ours — except a derby, where the opposition row links back to our own club team via `club_team_id`. |

## A day in the life

1. **Friday** — coach opens the app on their phone, taps the "Sheet" button on the next
   fixture and gets the one-page matchday PDF: fixture details, squad with appearances
   so far (fewest shaded), tick boxes for availability.
2. **Saturday, full time** — coach opens the fixture, taps *Enter result*: score steppers,
   the whole squad preselected (tap to deselect absentees), *Add goal* → scorer → assist,
   POTM chips, *Save*. One request; the dashboard updates.
3. **Saturday evening** — someone posts a match report on the WhatsApp group; the coach
   pastes it into *Match report* on the fixture.
4. **Any time** — the dashboard shows record, form, leaderboard; the spreadsheet export
   gives the old Google Sheet layout for anyone who wants it.
5. **Next season** — Settings → *Start next season* creates 2027/28 for the team, copies the
   squad forward and derives "U11".
