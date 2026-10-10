# 8. Security and access control

The app holds children's names, photos and match data for a youth football club. The
threat model is modest (no payments, no public users) but the data is sensitive, so the
design errs towards isolation: a coach sees their own team and nothing else unless
explicitly granted more.

## Login and sessions

There are two ways in, and they never cross: **coaches and admins** have a username and
a password; **parents** have neither and sign in with a single-use link emailed to them
(see [Parents](13-parents.md)). A parent account has `password_hash = NULL`, so
`POST /auth/login` can never authenticate one; a coach has no `email`, so no sign-in link
is ever issued for them.

1. `POST /auth/login` with username + password over HTTPS.
2. Password verified with **argon2id** (`argon2-cffi` defaults: memory-hard, ~50 ms).
   Unknown user and wrong password return the same 401 message.
3. On success a cookie `abgfc_session` is set: value = `{"uid": id, "sv": session_version}` signed with
   `ABGFC_SECRET_KEY` and timestamped (`itsdangerous.URLSafeTimedSerializer`, salt
   `"session"`). Flags: `HttpOnly`, `SameSite=Lax`, `Secure` (production), `Path=/`,
   `Max-Age` 30 days.
4. Every request: `deps.get_current_user` verifies signature and age, loads the user,
   requires `is_active`. `deps.get_access` resolves roles.
5. `POST /auth/logout` deletes the cookie. Sign-in/out are full page loads in the
   frontend so nothing cached from another user survives on a shared phone.
   `users.session_version` is included in the cookie and checked per request: bumping it
   signs every device out at once. A cookie issued before versions existed carries no
   `sv` and is still accepted, so adding this signed nobody out.
6. Passwords: min 8 chars (12 recommended); self-service change needs the current
   password; admins can reset within their scope; the development default is refused
   in production.

Transport: Caddy terminates TLS with a Let's Encrypt certificate, redirects HTTP → HTTPS,
sets HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`. The API
has no public port; only Next.js reaches it over the Docker network.

## Roles and scopes

`user_roles` rows: `(role, scope_type, scope_id)`.

| Role | May |
|---|---|
| `viewer` | read everything in scope |
| `coach` | viewer + enter results (post-match or live), manage squad and fixtures, award types for their team, match notes, photos, reports, start a season |
| `admin` | coach + manage users/roles within scope; club admins also manage cohorts, teams, club-wide award types and seasons |

| Scope | Covers |
|---|---|
| `team` | one club team |
| `cohort` | every team in the age group, plus the cohort overview and player moves |
| `club` | everything |

A **parent** holds exactly one row: `(viewer, cohort, <their child's cohort>)`. That is
the same row the age-group coach has at a lower role, so parents needed no new access
logic - they read the whole age group and write nothing. What makes them a parent rather
than any other viewer is a `player_guardians` link, which grants nothing today and is
there to answer "whose access is this?" and to gate per-child contributions later.

Roles **widen upwards**: role on a team = max(club role, cohort role, direct team role).
`Access.for_user` computes, once per request:

- `club_role`, `cohort_roles{cohort_id → role}`, `team_roles{team_id → role}`
- `visible_team_ids()` — `None` (all) for any club role, else the union of directly
  assigned teams and every team in assigned cohorts
- `visible_cohort_ids()` — cohorts of those teams plus assigned cohorts

Guards (each raises `ForbiddenError` → 403):

| Guard | Rule |
|---|---|
| `require_team(team, min)` / `require_team_season(ts, min)` | role on that team ≥ min |
| `require_cohort(cohort_id, min)` | cohort-level role ≥ min; for `viewer` it's enough that the cohort is visible |
| `require_club(min)` | club role ≥ min |
| `require_player(db, player, min)` | **view**: player's cohort is visible (so squads can pick from the age-group pool and a Reds coach can see a Blues child's name and photo); **edit**: coach+ on the cohort, or coach+ on a team whose squad contains the player |

List endpoints don't just guard — they **filter** with the visible ids, so results are
scoped even when no single row would 403.

### User administration

An admin manages only users whose *every* role lies inside scopes the admin administers:
a Blacks team admin can create Blacks coaches but not Reds', nor grant cohort or club
roles. A club admin can't demote their own club-admin role or deactivate themselves.
For a **coach**, admin password reset is still the "forgot password" path.

Parents are managed separately, by **coaches**, in Settings → Parents: inviting, closing
and signing out are authorised by "could you have invited them?" — coach+ on at least one
of that parent's children — not by the admin-scope rules above. A coach granting `viewer`
is granting strictly less than they hold themselves, so it is not an escalation.

## Children's data handling

- **Photos**: uploaded files are decoded and **re-encoded** (Pillow) — all EXIF, including
  GPS and device info, is dropped; orientation is applied first. Stored under
  `/data/media/players/<id>/<random>-{full,thumb}.jpg` with mode 600 on a private
  volume. Served only by `GET /players/{id}/photo` after `require_player`, with
  `Cache-Control: private`. The URL's `v=<random token>` changes on every upload.
- **PDF and spreadsheet** name children, so they're **coach-only** (403 for viewers) -
  this is the one thing a parent cannot reach. Everything else in the age group is
  readable by them, which the head coach decided explicitly in Oct 2026: there is nothing
  in match notes, player notes or photos the club wants withheld from parents.
- **Parents' email addresses** are personal data and the only contact details the app
  holds. They are in the database and therefore in the backups; closing an account leaves
  the address on the row.
- **Match notes** are verbatim WhatsApp text; readable by anyone with access to the
  fixture's team, writable by coaches. Don't add parsing that writes to results without
  a human confirming (see roadmap).
- **No dates of birth.** The app used to collect one per player and never read it -
  nothing displayed it, no report carried it, and age-group eligibility is decided by the
  cohort's birth-year window rather than per child. Children's PII with no purpose, so the
  column was dropped (migration `a1d0b17hdrop`, Oct 2026) and the 22 stored dates erased
  with it. **Don't add it back** without a use that actually needs it; if an age check is
  ever wanted, the cohort window answers it and the club's registration records live with
  the FA.
- Names only: no addresses, no medical info. `players.notes` is free text with no
  guidance on it - worth a look if coaches start putting anything sensitive there.
- Backups (`/data/backups`, `data/backups/` locally) contain everything the database
  does; treat them accordingly. Password hashes are argon2id.
- The public GitHub repository contains the seed with first names and the fixture list;
  the owner accepted that. No other personal data is in the repo.

### Club-wide lookups

Opposition teams, competitions and award types belong to no single team, so the per-team
checks never applied to them - and for a while nothing else did either: **any signed-in
user, including a viewer, could create, rename or delete an opposition or a competition**,
which reaches into every team's fixtures. Fixed Oct 2026 by `Access.require_any_coach()`
on every write (`api/routers/lookups.py`); award types were already guarded (club-wide ones
need a club admin, a team's own needs a coach on that team). `tests/test_access.py` pins a
viewer out of all of them.

The lesson for anything added later: a resource that isn't team-scoped gets **no** access
check by default. Say explicitly who may write it.

## Production hardening (`ABGFC_ENV=production`)

- Refuses to start with the development `secret_key` or `coach_password`.
- `/api/docs`, `/redoc` and `/api/openapi.json` return 404.
- Cookies are `Secure` unless `ABGFC_COOKIE_SECURE=false` is set explicitly.
- Secrets live only in `/opt/abgfc/.env` (mode 600) on the droplet; CI holds an SSH deploy
  key, the host key, the host and the site address as repository secrets.
- Droplet: key-only SSH as `deploy`, `ufw` allowing 22/80/443, unattended security
  upgrades with a 04:30 reboot window, fail2ban on SSH.

## Known gaps (recommended next steps)

1. **No rate limiting on `POST /auth/login`.** Argon2 makes each guess ~50 ms but nothing
   throttles a client. Deliberately left alone when parent access was added: locking out a
   coach who fumbles their password at the pitch is its own failure. The emailed-link
   endpoints *are* limited (`core/ratelimit.py`: 5 link requests and 20 token attempts per
   15 minutes, per email and per IP), in process - it forgets on restart, which is fine
   for one container.
2. **Session revocation is now possible but not wired to passwords.**
   `users.session_version` is in the cookie and checked per request;
   `POST /parents/{id}/sign-out` bumps it, and closing an account bumps it too. A coach
   changing their password still doesn't invalidate their other devices - bump it there
   as well.
3. **No 2FA.** Parents now have accounts, but they are read-only and sign in from an
   email inbox, which is itself the second factor in practice. Revisit if parents ever get
   write access beyond their own child.
4. **Timing side-channel on username existence** (argon2 is skipped for unknown users).
   Negligible here; a dummy verify would close it.
