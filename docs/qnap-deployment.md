# FamQuest QNAP deployment

Verified LAN setup (October 2026): QNAP TS-473A, source at `/share/Container/famquest`, local image `famquest:latest`, PostgreSQL 16, host port `11900` to app port `8080`.

## Build via QNAP SSH

```sh
cd /share/Container/famquest
export HOME=/share/Container/famquest
export DOCKER_CONFIG=/share/Container/famquest/.docker-config
export BUILDX_CONFIG=/share/Container/famquest/.docker-config/buildx
docker build --target runtime --progress=plain -t famquest:latest .
```

Always use `--target runtime` (the Dockerfile's final stage is `test`). Compose uses `image: famquest:latest` and `pull_policy: never`, not a Compose build. Environment file: `/share/Container/famquest/.env`; app sets `POSTGRES_HOST: db`.

Preserve `/share/Container/famquest/postgres-data`, `/share/Container/famquest/uploads`, and `.env` across source ZIP extraction, rebuilds, and container recreation. Make backups before migrations. GitHub commits do not deploy automatically to the NAS. Source was transferred via ZIP/File Station because git was unavailable on QNAP.

**Open security issue:** App temporarily uses `user: "0:0"` because QNAP could not read image files as UID 999 despite permission changes. Fix non-root access before exposing externally. Avoid recursive chmod of `.venv` (previous `Bad address` failure).

After a tested PR merge, copy release source to NAS without overwriting persistent data, build runtime image, recreate app container with same mounts/env, and verify login, tasks, database and migrations at `http://192.168.1.2:11900`.
