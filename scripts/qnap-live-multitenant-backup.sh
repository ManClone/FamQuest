#!/bin/sh
# Embedded in Compose by prepare-live-backup.py; coordinated scheduler only.
set -eu
if test "${FAMQUEST_BACKUP_COORDINATED:-0}" != 1; then
    echo 'SKIP: use the coordinated scheduler to pause app and MCP first.'
    exit 0
fi
umask 077
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGHOST=live-db PGUSER="$POSTGRES_USER" PGCONNECT_TIMEOUT=10
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "/backups/live-$STAMP"
cd "/backups/live-$STAMP"
mkdir databases
pg_dumpall --globals-only --file=globals.sql
# Include every non-template database, including all future prepared family slots.
psql -X -At -v ON_ERROR_STOP=1 --dbname=postgres \
    -c 'SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname' > DATABASES
while IFS= read -r database; do
    case "$database" in ''|*[!a-z0-9_]*) echo 'FAIL: unsupported database name'; exit 1 ;; esac
    pg_dump --format=custom --create --dbname="$database" --file="databases/$database.dump"
    pg_restore --list "databases/$database.dump" > /dev/null
done < DATABASES
# Keep original paths for existing restore instructions.
cp databases/famquest_auth.dump auth.dump
cp databases/famquest_grasser_runtime.dump family.dump
test -z "$(find /source-uploads -type l -print -quit)"
tar -czf uploads.tar.gz -C /source-uploads .
tar -tzf uploads.tar.gz > /dev/null
cp /source-config/runtime.json runtime.json
cp /source-config/gateway.conf gateway.conf
cp /source-config/nginx.conf nginx.conf
sha256sum globals.sql auth.dump family.dump uploads.tar.gz runtime.json \
    gateway.conf nginx.conf DATABASES databases/*.dump > SHA256SUMS
sha256sum -c SHA256SUMS > /dev/null
touch BACKUP-COMPLETE
echo 'PASS: live central registry, all databases, role definitions, uploads and runtime configuration saved privately. Actual restore not performed.'
