# Week 14 Ansible Deployment and Verification Specification

## Target
Docker Desktop Linux engine accessed by the Jenkins Docker agent. Ansible runs in the official `docker:29.8.0-cli` image and uses the mounted Docker socket.

## Inputs managed by Ansible
- Application `Dockerfile`, `docker-compose.yml`, `requirements.txt`, README and implementation notes
- Python application source: `app/`, `frontend/`, `templates/`, `sql/`
- Nginx configuration source: `nginx/`
- PostgreSQL image build inputs and entrypoint: `docker/`
- `.env.example` (example only; no real `.env` is copied)
- `RELEASE` marker and runtime secret file with restrictive permissions

## Deployment behavior
1. Validate Linux target and prerequisites (Docker CLI, Compose v2, OpenSSL).
2. Run Ansible syntax validation and check-mode validation.
3. Deploy the versioned app image through Docker Compose.
4. Verify `leaveflow-app` and `leaveflow-db` are running and healthy; verify `leaveflow-nginx` is running.
5. Verify `/health` returns HTTP 200 with `status=ok` and `database=postgresql`.
6. Update the `latest` image tag only when it does not already reference the verified release image.
7. Re-run the playbook from Jenkins and require an idempotent recap (`changed=0`).

## Jenkins parameters
```text
DEPLOY_ENV=production
DEPLOY_MODE=docker
PUBLISH_DOCKER_IMAGE=false
DOCKER_REGISTRY=blank or default
DOCKERHUB_REPOSITORY=blank
RUN_ANSIBLE=true
ANSIBLE_APP_DIR=blank
```

Registry publishing is outside Week 14 scope. The live deployment is local to Docker Desktop; check mode alone is not considered completion.

## Acceptance evidence
- Ansible syntax and check-mode commands pass
- Live play recap has `failed=0` and `unreachable=0`
- Second run reports `changed=0`
- `leaveflow-app` and `leaveflow-db` are healthy; `leaveflow-nginx` is running
- `/health` reports PostgreSQL-backed health
- Jenkins downstream Docker verification and Selenium tests pass
