# Week 13 Configuration Specification

## Target
Linux Docker host / Docker Desktop Linux engine used by the Employee Leave Approval System.

## Prerequisites
- Python 3 for the Ansible runtime
- OpenSSL for runtime secret generation
- Docker Engine / Docker Desktop Linux engine
- Docker CLI
- Docker Compose v2

## Users
The Ansible execution account must have permission to access the Docker engine.

## Managed directories
- `<app_dir>/`
- `<app_dir>/uploads/`
- `<app_dir>/secrets/`

## Managed files
- `<app_dir>/Dockerfile`
- `<app_dir>/docker-compose.yml`
- `<app_dir>/requirements.txt`
- `<app_dir>/README.md`
- `<app_dir>/IMPLEMENTATION_STEPS.md`
- `<app_dir>/.env.example`
- `<app_dir>/RELEASE`
- `<app_dir>/secrets/leaveflow_secret_key.txt` (0600)

## Services and ports
- Docker Engine / Docker Desktop Linux engine
- Application/Nginx: host port 8000
- PostgreSQL: container port 5432

## Automation
`ansible/inventory.ini` targets `localhost` with local connection. `ansible/site.yml` manages the application directory, uploads directory, Compose secret, deployment files, application source, release marker, fixed-name containers, Docker Compose deployment, and PostgreSQL-backed FastAPI health.

## Jenkins integration
The Jenkins controller remains LocalSystem. The Week 13 runner uses the official `docker:29.8.0-cli` image, mounts the Jenkins workspace and `/var/run/docker.sock`, installs Ansible Core 2.21.4 plus the Docker SDK and `community.docker`, performs syntax/check-mode validation, and then performs a live Ansible execution against the Docker Desktop Linux engine.
