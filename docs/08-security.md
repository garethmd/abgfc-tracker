# 8. Security and access control

The app holds children's names, photos and match data for a youth football club. The
threat model is modest (no payments, no public users) but the data is sensitive, so the
design errs towards isolation: a coach sees their own team and nothing else unless
explicitly granted more.

## Login and sessions

1. `POST /auth/login` with username + password over HTTPS.
2. Password verified with **argon2id** (`argon2-cffi` defaults: memory-hard, ~50 ms).
   Unknown user and wrong password return the same 401 message.
3. On success a cookie `abgfc_session` is set: value = `{"uid": id}` signed with
   `ABGFC_SECRET_KEY` and timestamped (`itsdangerous.URLSafeTimedSerializer`, salt
   `"session"`). Flags: `HttpOnly`, `SameSite=Lax`, `Secure` (production), `Path=/`,
   `Max-Age` 30 days.
4. Every request: `deps.get_current_user` verifies signature and age, loads the user,
   requires `is_active`. `deps.get_access` resolves roles.
5. `POST /auth/logout` deletes the cookie. Sign-in/out are full page loads in the
   frontend so nothing cached from another user survives on a shared phone.
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
| `coach` | viewer + enter results, manage squad and fixtures, award types for their team, match notes, photos, reports, start a season |
| `admin` | coach + manage users/roles within scope; club admins also manage cohorts, teams, club-wide award types and seasons |

| Scope | Covers |
|---|---|
| `team` | one club team |
| `cohort` | every team in the age group, plus the cohort overview and player moves |
| `club` | everything |

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
Admin password reset is the "forgot password" path — there is no email flow.

## Children's data handling

- **Photos**: uploaded files are decoded and **re-encoded** (Pillow) — all EXIF, including
  GPS and device info, is dropped; orientation is applied first. Stored under
  `/data/media/players/<id>/<random>-{full,thumb}.jpg` with mode 600 on a private
  volume. Served only by `GET /players/{id}/photo` after `require_player`, with
  `Cache-Control: private`. The URL's `v=<random token>` changes on every upload.
- **PDF and spreadsheet** name children, so they're **coach-only** (403 for viewers).
- **Match notes** are verbatim WhatsApp text; readable by anyone with access to the
  fixture's team, writable by coaches. Don't add parsing that writes to results without
  a human confirming (see roadmap).
- Names only: no addresses, no medical info, `date_of_birth` optional and shown only on
  the edit form.
- Backups (`/data/backups`, `data/backups/` locally) contain everything the database
  does; treat them accordingly. Password hashes are argon2id.
- The public GitHub repository contains the seed with first names and the fixture list;
  the owner accepted that. No other personal data is in the repo.

## Production hardening (`ABGFC_ENV=production`)

- Refuses to start with the development `secret_key` or `coach_password`.
- `/api/docs`, `/redoc` and `/api/openapi.json` return 404.
- Cookies are `Secure` unless `ABGFC_COOKIE_SECURE=false` is set explicitly.
- Secrets live only in `/opt/abgfc/.env` (mode 600) on the droplet; CI holds an SSH deploy
  key, the host key, the host and the site address as repository secrets.
- Droplet: key-only SSH as `deploy`, `ufw` allowing 22/80/443, unattended security
  upgrades with a 04:30 reboot window, fail2ban on SSH.

## Known gaps (recommended next steps)

1. **No login rate limiting.** Argon2 makes each guess ~50 ms but nothing throttles a
   client. Add per-IP + per-username limits (e.g. 5 failures → 15-minute wait) in the
   API or at Caddy.
2. **Sessions can't be revoked.** The cookie is self-contained; a password change doesn't
   invalidate other devices. Deactivating the user *does* cut them off immediately
   (checked per request). Fix: a per-user session version in the token, bumped on
   password change/reset.
3. **No 2FA** — judged unnecessary for the audience; revisit if parents get accounts.
4. **Timing side-channel on username existence** (argon2 is skipped for unknown users).
   Negligible here; a dummy verify would close it.
