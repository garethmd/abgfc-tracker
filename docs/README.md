# ABGFC Tracker — developer documentation

Team stats for Aldershot Boys & Girls FC. Coaches enter match results from a phone at the
side of the pitch; the app derives the records, leaderboards and reports. This folder is
the complete handover for a developer who needs to support or extend it.

Read in order the first time; afterwards each document stands alone.

| # | Document | What it covers |
|---|---|---|
| 1 | [Overview](01-overview.md) | What the app is for, who uses it, the domain vocabulary |
| 2 | [Architecture](02-architecture.md) | Components, request flow, layering, the tech stack and why |
| 3 | [Data model](03-data-model.md) | Every table, every relationship, the reasoning, migrations |
| 4 | [Backend](04-backend.md) | Code walkthrough of `backend/` — config, models, repositories, services, routers |
| 5 | [API reference](05-api.md) | Every endpoint, auth, error format, key payloads |
| 6 | [Frontend](06-frontend.md) | Next.js structure, routing, providers, generated API client, UI conventions |
| 7 | [Stats engine](07-stats.md) | Exactly how every derived number is calculated, and the test oracle |
| 8 | [Security & access](08-security.md) | Login, sessions, roles/scopes, children's data, production hardening, known gaps |
| 9 | [Deployment & operations](09-deployment.md) | The droplet, CI/CD, secrets, backups, restore, rollback, runbooks |
| 10 | [Development guide](10-development.md) | Local setup, Make targets, tests, migrations, adding features, troubleshooting |
| 11 | [Reports, exports & media](11-features.md) | Matchday PDF, spreadsheet export, match notes, profile photos |
| 12 | [Roadmap & design seams](12-roadmap.md) | Features designed but not built, and how they land |

`CLAUDE.md` in the repository root is the condensed version of the same material,
optimised for AI coding assistants; keep the two in step when you change behaviour.

## Where things are

```
abgfc-tracker/
├── backend/            FastAPI + SQLAlchemy + Alembic (Python 3.13, uv)
├── frontend/           Next.js 16 App Router + TypeScript + Tailwind 4 + shadcn/ui
├── deploy/             cloud-init, Caddyfile, backup/restore scripts for the droplet
├── docs/               this documentation
├── .github/workflows/  ci.yml — checks on PRs, build + deploy on main
├── docker-compose.yml       local full stack
├── docker-compose.prod.yml  production stack (Caddy + web + api from GHCR images)
├── Makefile            every routine task has a target
└── CLAUDE.md           condensed architecture notes for AI assistants
```

## Live system

- Production: <https://abgfc.neuralaspect.com> — one DigitalOcean droplet in London (`abgfc`, 1GB)
- Source: <https://github.com/garethmd/abgfc-tracker> — pushing to `main` deploys automatically
- Images: `ghcr.io/garethmd/abgfc-tracker-api`, `ghcr.io/garethmd/abgfc-tracker-web`
