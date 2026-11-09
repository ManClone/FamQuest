#!/bin/sh
# Install only together with docker-compose.qnap-live-final.yml on the NAS.
set -eu
umask 077
fail() { echo "FAIL: $*" >&2; exit 1; }
case "${1:---check}" in --check|--run) ;; *) fail 'Use --check or --run.' ;; esac
command -v docker >/dev/null || fail 'Docker not found in PATH.'
compose_file=${FAMQUEST_COMPOSE_FILE:-/share/Container/famquest-live/compose.yml}
project=famquest-live
compose() { docker compose -p "$project" -f "$compose_file" "$@"; }
# Do not silently continue on a failed Docker enumeration.
container() {
    ids=$(docker ps -aq --no-trunc --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.service=$1") || return 1
    printf '%s\n' "$ids" | awk 'NF { count++; id=$0 } END { if (count == 1) print id; else exit 1 }'
}
state() { docker inspect --format '{{.State.Status}}' "$1"; }
docker compose version >/dev/null || fail 'Docker Compose plugin unavailable.'
test -r "$compose_file" || fail 'Final Compose file is missing or unreadable.'
compose config --quiet || fail 'Compose validation failed.'
app=$(container live-app) || fail 'Expected exactly one live-app.'
mcp=$(container live-mcp) || fail 'Expected exactly one live-mcp.'
db=$(container live-db) || fail 'Expected exactly one live-db.'
for service_id in "$app" "$mcp" "$db"; do
    test "$(state "$service_id")" = running || fail 'A required service is not running.'
done
# Preserve the old lock name during transition; never schedule both jobs.
lock_root=${FAMQUEST_BACKUP_LOCK_ROOT:-${HOME:-}}
case "$lock_root" in /*) test "$lock_root" != / || fail 'Invalid lock directory.' ;; *) fail 'An absolute lock directory is required.' ;; esac
test -d "$lock_root" && test -w "$lock_root" || fail 'Lock directory is not writable.'
lock="$lock_root/.famquest-live-auto-backup-lock"
mkdir "$lock" || fail 'Cannot acquire backup lock.'
resume_app=no
resume_mcp=no
backup_name=famquest-live-scheduled-backup
backup_started=no
cleanup() {
    result=$?
    trap - EXIT
    trap '' HUP INT TERM
    # On interruption, finish/stop our one-shot helper before resuming writers.
    if test "$backup_started" = yes && docker container inspect "$backup_name" >/dev/null 2>&1; then
        if ! docker stop "$backup_name" >/dev/null; then
            echo 'FAIL: backup helper could not be stopped; resume app/MCP manually after checking it.' >&2
            rm -f "$lock/backup.log"
            rmdir "$lock" || :
            exit 1
        fi
    fi
    if test "$resume_app" = yes; then
        docker start "$app" >/dev/null || { echo 'FAIL: start live-app manually.' >&2; result=1; }
    fi
    if test "$resume_mcp" = yes; then
        docker start "$mcp" >/dev/null || { echo 'FAIL: start live-mcp manually.' >&2; result=1; }
    fi
    rm -f "$lock/backup.log" || result=1
    rmdir "$lock" || result=1
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
# Refuse an existing one-shot container; never remove a container we did not start.
if docker container inspect "$backup_name" >/dev/null 2>&1; then
    fail 'A scheduled backup container already exists. Review it before retrying.'
fi
if test "${1:---check}" = --check; then
    echo 'PASS: live services, final Compose file and lock verified; no backup performed.'
    exit 0
fi
resume_mcp=yes
docker stop "$mcp" >/dev/null
resume_app=yes
docker stop "$app" >/dev/null
backup_started=yes
echo "Backup started at $(date -u)."
if ! compose --profile backup run --rm --no-deps -T --name "$backup_name" -e FAMQUEST_BACKUP_COORDINATED=1 backup > "$lock/backup.log" 2>&1; then
    fail 'Backup failed. Review the private backup directory; incomplete runs have no BACKUP-COMPLETE marker.'
fi
if ! grep -q '^PASS: live central registry,' "$lock/backup.log"; then
    fail 'Backup did not report completion.'
fi
backup_started=no
echo 'PASS: scheduled live backup completed.'
