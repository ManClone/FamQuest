#!/bin/sh
set -eu
# Only the private staging gateway may supply the external HTTPS origin.
TRUSTED_GATEWAY="$(python -c 'import socket; print(socket.gethostbyname("central-stage-gateway"))')"
python -m app.deployment_check
exec uvicorn app.multitenant_app:create_app --factory \
  --host 0.0.0.0 --port 8080 --proxy-headers \
  --forwarded-allow-ips "$TRUSTED_GATEWAY" --log-level "${LOG_LEVEL:-info}"
