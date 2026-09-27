#!/bin/sh

set -eu

SECRET_FILE="/run/secrets/leaveflow_secret_key"

if [ ! -f "$SECRET_FILE" ]; then
    echo "ERROR: Docker secret not found: $SECRET_FILE"
    exit 1
fi

export SECRET_KEY="$(cat "$SECRET_FILE")"

if [ -z "$SECRET_KEY" ]; then
    echo "ERROR: SECRET_KEY is empty."
    exit 1
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers