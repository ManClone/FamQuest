#!/bin/sh
# Read-only Docker inventory. Never outputs container environment, commands or logs.
# Run on the QNAP Docker host and keep the report private (it contains storage paths).
set -eu
: "${DOCKER_BIN:=docker}"
command -v "$DOCKER_BIN" >/dev/null 2>&1 || {
  printf '%s\n' 'Docker command unavailable; set DOCKER_BIN to its executable path.' >&2
  exit 1
}
"$DOCKER_BIN" info --format '{"kind":"daemon","name":{{json .Name}},"version":{{json .ServerVersion}}}'
# Include stopped and non-FamQuest containers to identify shared mounts/networks.
# Successful enumeration is required; do not hide Docker access failures.
container_ids=$("$DOCKER_BIN" ps -aq --no-trunc)
for container_id in $container_ids; do
  "$DOCKER_BIN" inspect --type container --format '{"kind":"container","id":{{json .Id}},"name":{{json .Name}},"status":{{json .State.Status}},"image_reference":{{json .Config.Image}},"image_id":{{json .Image}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"compose_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"restart":{{json .HostConfig.RestartPolicy}},"mounts":{{json .Mounts}},"network_mode":{{json .HostConfig.NetworkMode}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}}}' "$container_id"
done
"$DOCKER_BIN" volume ls --format '{"kind":"volume","name":{{json .Name}},"driver":{{json .Driver}}}'
"$DOCKER_BIN" network ls --format '{"kind":"network","name":{{json .Name}},"id":{{json .ID}},"driver":{{json .Driver}}}'
