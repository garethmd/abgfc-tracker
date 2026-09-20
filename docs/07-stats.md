# 7. Stats engine

Everything derived lives in `backend/app/services/stats.py`. The functions at the top are
pure — they take already-loaded ORM rows and return Pydantic models — and `StatsService`
at the bottom loads the rows via repositories. Change a rule here and in the oracle
(`services/bootstrap.py::seed_demo_season` docstring + `tests/test_stats.py`) together.

## Which fixtures count

`_is_played(f)`: `status == 'played'` **and** both scores present. Scheduled, live,
postponed, cancelled, abandoned, and "played but score not yet entered" are all excluded
from records, form and per-player totals — a match being recorded live has a score and
goals on it but doesn't count until *Full time* makes it `played`. Appearances/events on a non-played fixture don't
count either (they're keyed by played fixture ids).

## Team record — `team_record(fixtures) → TeamRecord`

- `outcome(ours, theirs)` → W / D / L.
- `played, won, drawn, lost, goals_for, goals_against, goal_difference`.
- `win_pct = round(100 * won / played, 1)`, `0.0` when nothing played.
- League-only = the same over fixtures whose `competition.type == 'league'`. Any number
  of league competitions qualify (Conference League, Zidane League).

## Form — `form(fixtures, n=5) → [FormEntry]`

Played fixtures sorted by `(kickoff_at, id)`, last `n`, **chronological (most recent
last)**. The spreadsheet export reverses it because the original sheet listed most
recent first.

## Per-player rows — `player_rows(players, appearances, events, awards, award_types, squad_numbers, durations)`

The base set is the team season's **squad** (so a fresh season lists everyone with
zeros); anyone else who has an appearance, event or award in the fixture set is added
(e.g. a player who has since left the squad keeps their row and totals).

| Column | Rule |
|---|---|
| `appearances` | count of appearance rows |
| `starts` | appearances with `started` |
| `goals` | `match_events` of type `goal` for the player |
| `assists` | type `assist` |
| `own_goals` | type `own_goal` (counts against us; shown on the player) |
| `goals_per_game` | `round(goals / appearances, 2)`, `0.0` with no appearances |
| `awards` | one `AwardCount` per active award type visible to the team (club-wide + team's own), count of awards of that type on played fixtures |
| `minutes` | sum of `minutes_for_appearance` — **`None` unless every appearance has stints** (partial data would mislead a fairness check) |

`opp_own_goal` events have no player and count for nobody.

Sort: goals ↓, assists ↓, appearances ↓, name ↑.

## Minutes — `minutes_for_appearance(appearance, match_duration)`

`None` with no stints. Otherwise Σ `(off or duration) − on`, each stint clipped to the
match length (`fixture.duration_minutes` or the team season's `match_minutes`).

## Highlights — `highlights(rows, award_types) → [HighlightTile]`

Tiles: "Top scorer" (goals), "Most assists" (assists), then one per award type (count).
Value = max; `players` = **every** row with that max, alphabetical; empty list when the
max is 0 (the UI shows "—").

## Score warnings — `score_warnings(fixture) → [str]`

For played fixtures only: `goals_from_events` = (our goals = `goal` + `opp_own_goal`,
their = `own_goal`). Warns when our recorded goals are fewer than `our_score` ("3 of our
4 goals have a scorer recorded"), more ("4 goals recorded but our score is 3"), when own
goals exceed `their_score`, and when an event's player has no appearance. Surfaced on the
fixture page; never blocks saving.

## Cohort overview — `StatsService.cohort_overview(cohort_id, season_id)`

For each team season in the cohort/season: overall + league records, form, squad size.
Then every player's rows across those team seasons are merged: `teams` lists each team
they appeared for, appearances/starts/goals/assists summed, minutes summed only where
known. Sorted by appearances ↓ then name — the "is game time fair across the group" view.

## The oracle

`seed_demo_season` builds six played fixtures (plus one scheduled, one postponed) for a
Blues team season and documents the expected totals in its docstring:

```
Overall  P6 W2 D1 L3  GF12 GA12 GD0  win% 33.3   form D L W L L
League   P4 W2 D1 L1  GF11 GA6  GD5  win% 50.0
Archie 6 apps 5 goals 3 assists, 2 coaches' POTM; Max & Noah 2 parents' POTM each; ...
```

`tests/test_stats.py` asserts every one of those numbers through `StatsService`, plus
the pure functions in isolation (ties, empty seasons, clipped stints, a player removed
from the squad keeping their stats, warnings). `tests/test_exports.py` recalculates the
spreadsheet's formulas in LibreOffice and asserts they agree with the same numbers. If
you change a rule, update the docstring, the tests, and (if it affects a column) the
spreadsheet formulas in `services/exports.py`.
