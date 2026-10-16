<p align="center"><img src="docs/logo.png" alt="FamQuest" width="300"></p>

# FamQuest — quests, household and rewards for the family

**English** · [Deutsch](README.de.md)

FamQuest is a self-hosted family app for children and parents. Children complete tasks,
collect stars, earn praise hearts and unlock levels. Parents manage tasks, approve
completions and keep track of the household. Everyone can browse the family's rewards;
each person can only redeem their own.

This is **ManClone's family-focused continuation of [craebby/FamQuest](https://github.com/craebby/FamQuest)**.
It focuses on everyday tasks, household participation and understandable rewards on phones,
tablets and shared displays. The original calendar, weather, meal-planning and shopping
dashboard is not the focus of this fork's current interface.

## Current release: Stable 1 Final

[Stable source](https://github.com/ManClone/FamQuest/tree/stable-1-final) ·
[Release scope and checks](docs/STABLE-1.md) ·
[Open issues](https://github.com/ManClone/FamQuest/issues)

Stable 1 Final includes issues #16–#23 and the compact reward layout:

- **Accounts and roles:** separate child and parent access, with optional logins assigned
  to family profiles. Children see their own tasks and private progress.
- **Tasks and routines:** recurring tasks, optional extras and parent approval where required.
- **Household:** cleaning plan with rooms, intervals, one-off tasks and participation by
  eligible children; parents approve children's completions.
- **Stars and rewards:** an auditable points ledger, rewards for children and adults,
  owner-only redemption and reasoned reversals without double refunds.
- **Praise and progress:** praise hearts, task XP and permanently unlocked levels.
  Spendable stars and task XP are separate values.
- **Compact mobile layout:** two reward cards per row on phones; stars and children's
  praise hearts appear below names inside the profile buttons.
- **Corrections with history:** confirmation before undoing completions; associated praise
  remains independent. A read-only consistency report supports reviewing existing records.
- **Optional MCP service:** authenticated tools for supported family workflows, with
  explicit parent decisions for child approvals. See [MCP setup and limits](mcp/README.md).

The interface supports German and English. Data is stored in your own PostgreSQL database
and upload storage. One installation belongs to one family.

**Deferred:** banking and the money module (#25), plus later adventure features (#24),
are outside this stable release. Stars are not euros. There is no automatic bank transfer.

## Install on a Docker host

Requires Git, Docker and the Compose plugin. The image builds the frontend and backend;
Node.js and Python do not need to be installed on the host.

```sh
git clone https://github.com/ManClone/FamQuest.git
cd FamQuest
git checkout stable-1-final
cp .env.example .env
```

Set a strong, unique `POSTGRES_PASSWORD` in `.env`, then start:

```sh
docker compose up -d --build
docker compose ps
```

Open `http://<host>:8080` (`APP_PORT` can change the port). Complete the first-run setup,
then manage family profiles and their optional logins under **Settings → Family**.
Access is account-based; the original shared-parent-PIN instructions do not describe this fork.
Database migrations run automatically at startup. Configuration variables are documented
in [`.env.example`](.env.example).

For an existing NAS installation, preserve its configuration, database and upload mounts.
See [QNAP deployment notes](docs/qnap-deployment.md); GitHub changes do not automatically
deploy to the NAS. Always build the Dockerfile's `runtime` target.

## Updates and backups

`main` contains released changes; `develop` is for further development. The
`stable-1-final` tag identifies the tested stable application source.

Before updating, back up the database, uploads, environment/Compose configuration,
previous image and, if used, the MCP state. Keep private backups outside Git.
Use [the backup script](scripts/backup.sh) as appropriate for your installation.
Verify container health and `/api/health` after updating. A rollback after a migration
requires a matching database backup and image.

The consistency report only reads data; it does not automatically repair records:

```sh
docker compose exec -T app python -m app.cli consistency-report
```

Keep the report private: it can contain family information and booking details.

## Development and documentation

React, TypeScript and Tailwind CSS frontend; FastAPI, SQLAlchemy and PostgreSQL backend;
Alembic migrations; Docker deployment. GitHub Actions checks the frontend, backend,
MCP service and container builds.

- [Product direction and rules for this fork](docs/FORK_ROADMAP.md)
- [Stable release behavior, levels and acceptance checks](docs/STABLE-1.md)
- [Family deployment and account behavior](docs/LIVE-TEST.md)
- [Original specification](docs/SPEC.md)
- [Historical upstream manual](docs/legacy/README.md), including the original dashboard's
  optional integrations and technical reference; it is not the current product description.

## Origin and license

Based on FamQuest by **Craebby**, copyright © 2026 Craebby, continued here by **ManClone**.
Licensed under [GNU AGPL-3.0-or-later](LICENSE). The original attribution and license remain
in place. Bundled [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) icons are
© Microsoft, MIT licensed.
