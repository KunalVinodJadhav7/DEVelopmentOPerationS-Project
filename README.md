# Jenkins-Based Employee Leave Approval System

A FastAPI employee leave approval application packaged as a DevOps/CI/CD project using **Gradle, Jenkins, Selenium, Docker, Nginx and Ansible**.

## Architecture

```text
Browser
   |
 Nginx :8000
   |
 FastAPI/Uvicorn :8000
   |
 PostgreSQL
```

CI/CD:

```text
GitHub -> Jenkins -> Gradle build -> Pytest -> Selenium quality gate
       -> Docker image -> Nginx/PostgreSQL deployment -> health check
```

### Why Nginx instead of Tomcat?

The application is FastAPI/Uvicorn, not a Java servlet/WAR application. Nginx is therefore used as the deployment gateway/reverse proxy in front of the Python ASGI service.

## Jenkins build

The repository contains `Jenkinsfile` and `build.gradle`. Configure a Jenkins Gradle tool named `Gradle-8`, connect the repository using SCM, and run the Pipeline job.

The pipeline:

- checks out the source;
- runs `gradle clean build`;
- archives `build/dist/*.zip`;
- starts an isolated CI copy of the FastAPI service;
- runs Selenium tests and publishes JUnit XML;
- builds a versioned Docker image using the Jenkins build number;
- optionally pushes the image to Docker Hub;
- deploys PostgreSQL + FastAPI + Nginx with Docker Compose;
- verifies `/health` before declaring success.

A failing test returns a non-zero exit code and prevents the Docker deployment stage from running.

## Local build

```bash
gradle clean build
gradle seleniumTest
```

The packaged artifact is created under `build/dist/`.

## Local Docker deployment

```bash
copy .env.example .env   # Windows
# or: cp .env.example .env

docker compose up -d --build
```

Open:

- `http://localhost:8000/dashboard`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`

## Jenkins start trigger

For a demonstration where starting the application also requests a Jenkins build:

```bash
./scripts/start_with_jenkins.sh
```

Windows:

```powershell
.\scripts\start_with_jenkins.ps1
```

Set `JENKINS_URL`, `JENKINS_JOB`, `JENKINS_USER` and `JENKINS_API_TOKEN` in `.env` first.

## Tests

```bash
pytest -v
python -m pytest selenium_tests -v
```

Failure screenshots are stored in `test-results/screenshots/`.

## Main implementation areas

- `app/main.py` — FastAPI routes and leave workflow
- `app/orm_models.py` — SQLAlchemy persistence models
- `app/schemas.py` — validation
- `app/security.py` — password hashing, JWT and role checks
- `build.gradle` — Gradle build/test/package orchestration
- `Jenkinsfile` — CI/CD pipeline
- `docker-compose.yml` — PostgreSQL, FastAPI and Nginx
- `nginx/default.conf` — reverse proxy configuration
- `selenium_tests/` — browser quality tests
- `ansible/site.yml` — provisioning

## Week 15 enhancements: configurable leave types and Manager-first approval

The application seeds two editable initial policies: **CL (Casual Leave, 12 workdays/year)** and **EL (Earned Leave, 15 workdays/year)**. These are example defaults, not fixed company policy. Admin or Super Admin can change yearly allowances, enable/disable existing types, and add new types from the **Leave policies** navigation item.

Employees select a leave type when submitting a request. Balances are calculated per calendar year using weekdays (Monday-Friday); public holidays are not excluded. A request awaiting a decision reserves its days; rejected requests release the reservation. If a requested leave exceeds the available allowance, the API rejects the submission.

The approval path is now:

```text
Employee submits leave
  -> Manager approves or rejects first
  -> HR performs a mandatory final review of the Manager decision
  -> Admin final decision, only after both approvals
  -> Super Admin notification
```

Every new request starts at `PENDING_MANAGER`. The Manager can approve or reject without waiting for HR; either decision is stored separately and moves the request to `PENDING_HR_FINAL`. HR must then record a final review. If the Manager approved, HR can pass it to Admin or veto it by rejecting. If the Manager rejected, HR confirms the rejection and the request remains `REJECTED`. Admin can finalize only requests that both Manager and HR have approved.

See `WEEK15_ENHANCEMENTS.md` for API details, migration behavior, rules and verification steps.
