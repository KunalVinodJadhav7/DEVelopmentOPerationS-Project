# Ansible deployment

The playbook manages the Employee Leave Approval System on a Linux Docker host / Docker Desktop Linux engine. It copies the required application sources and build inputs, prepares the runtime secret, deploys the Docker Compose project, and checks container and HTTP health.

## Standalone execution

```bash
ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook -i ansible/inventory.ini ansible/site.yml
```

Override the target directory when needed:

```bash
ansible-playbook -i ansible/inventory.ini ansible/site.yml \
  -e app_dir=/opt/leave-approval-system \
  -e health_host=127.0.0.1 \
  -e release_version=local
```

## Week 14 Jenkins execution

Set `RUN_ANSIBLE=true` with `DEPLOY_MODE=docker`. Jenkins runs the playbook inside the `docker:29.8.0-cli` container on the Docker Desktop agent, after Docker connectivity is verified. It performs syntax validation, check-mode validation, a real deployment, container health checks, a PostgreSQL-backed `/health` assertion, a release image tag check, and a second playbook run that must report `changed=0`. When this option is enabled, Ansible is the deployment path for that build and the later standalone Compose cleanup/deploy stages are skipped. With `RUN_ANSIBLE=false`, the standard Week 12 Docker Compose pipeline remains in use.

Jenkins uses the versioned image `leave-approval-system:1.0.<BUILD_NUMBER>` and updates `leave-approval-system:latest` only after health validation. The Compose project name remains stable so downstream Jenkins verification inspects the same containers and named volumes.
