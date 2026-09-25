#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

: "${JENKINS_URL:?Set JENKINS_URL in .env}"
: "${JENKINS_JOB:?Set JENKINS_JOB in .env}"
: "${JENKINS_USER:?Set JENKINS_USER in .env}"
: "${JENKINS_API_TOKEN:?Set JENKINS_API_TOKEN in .env}"

BUILD_URL="${JENKINS_URL%/}/job/${JENKINS_JOB}/build"

echo "Triggering Jenkins build: ${BUILD_URL}"
HTTP_CODE=$(curl -sS -o /tmp/jenkins-build-response.txt -w '%{http_code}' -X POST "$BUILD_URL" \
  --user "${JENKINS_USER}:${JENKINS_API_TOKEN}")

case "$HTTP_CODE" in
  200|201|202|302) echo "Jenkins build triggered." ;;
  *) echo "Jenkins rejected the trigger (HTTP $HTTP_CODE)."; cat /tmp/jenkins-build-response.txt; exit 1 ;;
esac

echo "Starting the local Nginx/PostgreSQL deployment..."
docker compose up -d --build

echo "Application: http://localhost:${APP_PORT:-8000}/dashboard"
