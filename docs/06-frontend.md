# 6. Frontend

`frontend/` — Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind 4,
shadcn/ui (radix-nova style). Built as a `standalone` output for Docker.

> Next 16 has breaking changes from earlier versions: `params` are Promises
> (`use(params)`), middleware is `proxy.ts`, `LayoutProps`/`PageProps` are generated
> globals (`next typegen`), and config is read at build time. When in doubt read
> `frontend/node_modules/next/dist/docs/` rather than relying on memory.

## Structure

```
frontend/
├── app/
│   ├── layout.tsx                 fonts (Geist), metadata, <Providers>
│   ├── globals.css                Tailwind + shadcn tokens; club blue accent; .team-accent
│   ├── manifest.ts                web app manifest (home-screen install)
│   ├── icon.png, apple-icon.png   crest icons
│   ├── login/                     page.tsx (server) + login-form.tsx (client)
│   └── (app)/                     authenticated area
│       ├── layout.tsx             fetches /auth/me → <MeProvider>
│       ├── page.tsx               landing: homeFor(me) redirect
│       ├── teams/                 picker for multi-team users
│       ├── no-access/
│       ├── admin/                 coaches + structure (admins)
│       ├── cohorts/[id]/          age-group overview (cohort coaches)
│       └── [team]/                everything a coach uses
│           ├── layout.tsx         slug → TeamAccess → <TeamProvider> + <AppShell nav>
│           ├── page.tsx           dashboard
│           ├── fixtures/          list, new, [id] (detail), [id]/entry, [id]/edit, [id]/live
│           ├── players/           squad list, [id] (profile)
│           └── settings/          seasons, awards, leagues, opposition, appearance, account
├── components/
│   ├── ui/                        shadcn primitives (button, sheet, dialog, select, …)
│   ├── features/<area>/           dashboard, fixtures, players, settings, admin, cohort
│   ├── app-shell.tsx              sidebar (md+) / top bar + bottom nav (mobile); Crest
│   ├── team-switcher.tsx          brand block; dropdown only if there's somewhere else to go
│   ├── season-switcher.tsx        team seasons for the current team
│   ├── plain-shell.tsx            shell without team nav (admin, cohort, picker)
│   ├── player-avatar.tsx          photo or initials
│   ├── providers.tsx              QueryClient, next-themes, Toaster
│   └── page-header, stat-card, empty-state, error-state, account-card, theme-toggle
├── lib/
│   ├── api/openapi.json           exported from the backend (generated)
│   ├── api/schema.d.ts            openapi-typescript output (generated)
│   ├── api/client.ts              fetchClient, $api hooks, errorMessage(), 401 handling
│   ├── me-context.tsx             MeProvider/useMe, homeFor(), rememberTeam()
│   ├── team-context.tsx           TeamProvider/useTeam, selected team season, accent
│   ├── reports.ts                 URLs for PDF / spreadsheet downloads
│   ├── format.ts                  dates, labels
│   └── utils.ts                   cn()
├── proxy.ts                       cookie-presence redirect
├── next.config.ts                 output: standalone; rewrites /api/* → BACKEND_URL
└── Dockerfile                     BACKEND_URL is a build ARG (rewrites are compiled in)
```

## Routing and the two providers

1. `(app)/layout.tsx` calls `GET /auth/me`. While loading it shows a skeleton; a 401 has
   already triggered the redirect in `client.ts`. It wraps children in `MeProvider`.
2. `(app)/page.tsx` sends the user to `homeFor(me)`: their only team, else the team they
   last used (localStorage), else `/teams` (picker) or `/admin`/`/no-access`.
3. `(app)/[team]/layout.tsx` looks the slug up in `me.teams`; unknown → "Team not found".
   It wraps the page in `TeamProvider` and the `AppShell` with the four-item nav.

`useMe()` gives `me`, `isClubAdmin`, `isAdminSomewhere`, `cohortRoles`, `teamBySlug`.
`useTeam()` gives `team`, `teamSeason` (the one being viewed), `teamSeasons`,
`setTeamSeasonId`, `canEdit` (coach or admin on this team), `base` (`/blues`).

The team switcher only renders a dropdown when `me.teams + cohortRoles + admin > 1`;
a single-team coach never sees the concept of other teams.

## Data access

```ts
import { $api, fetchClient, errorMessage } from "@/lib/api/client";

const q = $api.useQuery("get", "/api/v1/team-seasons/{team_season_id}/stats/summary",
  { params: { path: { team_season_id: tsId } } }, { enabled: !!teamSeason });

const m = $api.useMutation("put", "/api/v1/fixtures/{fixture_id}/result");
await m.mutateAsync({ params: { path: { fixture_id } }, body });
qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures"] });   // prefix match
```

- Paths, params and bodies are typed from `schema.d.ts`; a typo is a compile error.
- Query keys are `[method, path, init]`, so invalidating by path prefix refreshes every
  variant of that query.
- `fetchClient` is for one-offs (login, logout, multipart photo upload).
- `errorMessage(error)` turns `{detail}` (string or Pydantic list) into a toast string.
- **401 handling**: the middleware in `client.ts` calls `/auth/logout` (to clear the
  HttpOnly cookie — otherwise `proxy.ts` would bounce `/login` straight back) and then
  hard-navigates to `/login?next=…`. Sign-in and sign-out are full page loads on
  purpose, so no query cache survives a user switch on a shared phone.

## Pages and their key components

| Page | Component(s) | Notes |
|---|---|---|
| Dashboard | `RecordCard`, `HighlightTiles`, `Leaderboard`, `FormPips` | All/League toggle; spreadsheet button in header |
| Fixtures | `FixtureRow` | "Next up" card with *Enter result* + *Sheet* (PDF) |
| Fixture detail | `MatchNotes`, `GoalLine` | ⋯ menu: edit, edit result, PDF, delete; warnings banner |
| Result entry | `ResultEntry`, `GoalSheet`, `Chip`, `ScoreStepper` | squad preselected; bottom sheet scorer→assist; sticky save |
| Live match | `LineUp`, `LiveMatch` (+ `GoalSheet`/`Chip` from result entry) | line-up + captain → sticky score card, Goal/Against/Undo bar, Full time → entry screen for awards |
| Fixture new/edit | `FixtureForm` | inline "+ New team…" creates opposition |
| Squad | `PlayerAvatar`, `PlayerForm` (sheet) | "Already at the club" mode picks from the cohort pool |
| Player | `PhotoPicker`, `PlayerAvatar`, `Stat` | season stats, history across teams |
| Settings | `SeasonsManager` (roll-over dialog), `AwardTypesManager`, `CompetitionsManager`, `TeamsManager`, `ThemeToggle`, `AccountCard` | |
| Admin | `UsersManager` (roles with scope picker, reset password), `StructureManager` | admins only |
| Cohort overview | cards per team, players table, `MovePlayerDialog` | cohort coaches |

## Styling conventions

- Mobile-first: bottom nav (`h-16`), touch targets ≥44px (`h-11`/`h-12` buttons), sticky
  primary action above the nav on entry screens, bottom `Sheet`s for pick-lists.
- One accent: `--primary`. `globals.css` sets club blue; inside `TeamProvider` the wrapper
  sets `--team-accent` from `club_teams.colour` and `.team-accent` maps it to `--primary`
  (dark mode lifts the lightness with `oklch(from …)`).
- Dark mode via `next-themes` (`class` strategy); `ThemeToggle` in Settings.
- Numbers use the `tnum` utility (tabular figures). Cards: `rounded-xl bg-card shadow-sm
  ring-1 ring-border/60`.
- Empty states are designed (`EmptyState`), not blank — a fresh season should look
  intentional.

## Lint, types, build

- `npm run lint` (ESLint 9 flat config, `eslint-config-next`), `npm run typecheck`
  (`tsc --noEmit`; run `npx next typegen` first so `PageProps<"/[team]/…">` exist).
- React Compiler rules are on: don't `setState` synchronously inside effects — use
  `useSyncExternalStore` for browser-only values (see `theme-toggle.tsx`,
  `team-context.tsx`).
- `npm run build` produces `.next/standalone`; the Dockerfile copies it plus static and
  public.
- `BACKEND_URL` is baked at build time (rewrites are compiled). The Dockerfile default is
  `http://backend:8000`, matching the compose service name.
