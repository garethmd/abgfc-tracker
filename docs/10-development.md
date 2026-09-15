# 10. Development guide

## Prerequisites

- Python 3.13 and [`uv`](https://docs.astral.sh/uv/) (backend)
- Node 24 and npm (frontend)
- Docker Desktop (optional: full-stack compose, image builds)
- LibreOffice (optional: enables the spreadsheet recalculation test —
  `brew install --cask libreoffice`)

## First run

```bash
make install        # uv sync + npm install
make seed           # migrate + reference data + club admin + the real 2026/27 season
make dev            # API :8000 (--reload) and Next :3000 together
```

Login `coach` / `changeme`. Prefer `make seed-demo` when you want the fictional
six-match season the tests use (resets the local database first).

`.env` at the repo root (see `.env.example`) overrides `ABGFC_*` settings locally.
The database is `data/abgfc.db`; media under `data/media/`; both gitignored.

If port 3000 is taken, `cd frontend && npm run dev -- -p 3001` — the API is reached via
Next's rewrite so the frontend port doesn't matter. `.claude/launch.json` has
`autoPort: true` for the same reason.

## Make targets

| Target | Does |
|---|---|
| `install` | dependencies for both halves |
| `dev` / `backend` / `frontend` | run with hot reload |
| `migrate` | `alembic upgrade head` |
| `migration m="…"` | autogenerate a migration — always read it before applying |
| `seed` / `seed-demo` | real season (idempotent) / fictional oracle (reset) |
| `test` | pytest |
| `lint` | ruff check + format check, eslint, tsc |
| `format` | ruff fix + format |
| `api-client` | export OpenAPI → regenerate `frontend/lib/api/*` |
| `check-api` | fail if the committed client differs from the backend (CI runs this) |
| `up` | `docker compose up --build` — the full stack locally in containers |
| `droplet`, `deploy`, `backup`, `restore`, `prod-logs`, `prod-shell` | production, see [Deployment](09-deployment.md) |

## Everyday loop

1. Branch (or push to `main` if you're the admin — CI still runs, and deploys).
2. Backend change → `uv run pytest -q tests/test_x.py` while iterating → `make test`.
3. Schema change → `make migration m="…"` → inspect → `make migrate` →
   `cd backend && uv run alembic check` → `uv run alembic downgrade -1 && uv run alembic upgrade head`.
4. Any API change → `make api-client` and commit `frontend/lib/api/openapi.json` +
   `schema.d.ts`. Forgetting this fails CI on purpose.
5. Frontend → `npx next typegen` (route types), `npm run typecheck`, `npm run lint`.
6. `make lint` before pushing.

## Testing notes

- Each test gets a fresh in-memory SQLite (`create_all`, FK pragma on, `StaticPool`).
- `auth_client` is logged in as the seeded club admin; `make_user`/`login_as` build other
  roles. Scoping tests hit the HTTP API, not the service, deliberately.
- `test_exports.py::test_formulas_recalculate_to_the_apps_numbers` skips unless
  LibreOffice is installed; CI doesn't have it, so run it locally after touching
  `services/exports.py`.
- Photo tests monkeypatch `settings.media_dir` to a temp dir.
- Ruff line length is 100; `tests/*` and `services/exports.py` (spreadsheet formulas) are
  exempt from E501.

## Conventions

- **Backend**: services commit, repositories flush, routers neither. Raise `AppError`
  subclasses, never `HTTPException`. Every service that touches team data takes
  `access` and calls a `require_*` before reading or writing.
- **Schemas**: inputs inherit `InputModel` (unknown fields rejected), outputs `ORMModel`.
  Updates are all-optional and applied with `exclude_unset`.
- **Frontend**: pages are client components using `$api` hooks; keep server components
  for static shells only. Feature code goes in `components/features/<area>/`; generic UI
  in `components/`; shadcn primitives in `components/ui/` (edit them, they're vendored).
- **Copy**: British English, no exclamation marks, "match" not "game" in the UI,
  "Coaches' POTM" / "Parents' POTM" for the awards.
- **Commits**: imperative subject, body says why; CI must be green before merging a PR.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Target database is not up to date` from Alembic | migrations out of sync — `make migrate`; if `alembic check` shows drift after editing a model, generate a migration |
| `FOREIGN KEY constraint failed` during a migration | a batch rebuild with FKs on — `alembic/env.py` must use a plain engine (it does); don't add the FK pragma there |
| `'str' object has no attribute 'level'` | a `UserRole` came from the DB as a plain string; coerce with `UserRole(value)` (see `Access.for_user`) |
| Frontend type error on a request body field that has a default | regenerate with `make api-client` — the generator runs with `--default-non-nullable false` |
| Login form doesn't submit on Enter in an emulated browser | the button works; a quirk of the emulator, not the app |
| Photo/PDF/XLSX works locally but 403 in production | those endpoints are coach-only; check the user's role |
| 401 loop between `/` and `/login` | dead cookie — `client.ts` now calls `/auth/logout` before redirecting; if you see it again, check that middleware |
| Next dev server on a random port | `.claude/launch.json` `autoPort`; port 3000 is often held by another project on this machine |
| LibreOffice test fails with `soffice` not found | install it, or accept the skip |

## Repository hygiene

- `data/`, `.env`, `.env.production`, `data/backups/` are gitignored — never commit them.
- `frontend/lib/api/openapi.json` and `schema.d.ts` **are** committed (generated but
  reviewed, so drift is visible in PRs).
- `CLAUDE.md` is the condensed architecture note for AI assistants; update it alongside
  these docs when behaviour changes.
