#!/bin/sh
set -eu

# Explicit alternate entrypoint. Migration/provisioning must be completed separately.
python -m app.deployment_check
exec uvicorn app.multitenant_app:create_app --factory \
  --host 0.0.0.0 --port 8080 --proxy-headers --log-level "${LOG_LEVEL:-info}"
