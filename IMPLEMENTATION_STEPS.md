# Implementation Steps

This package is the consolidated single-project implementation for the Employee Leave Approval System DevOps assignment.

## 1. Local environment

Create and activate a Python virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```

Install Java and Gradle on the development/Jenkins machine. The project uses Gradle as the build tool for the Python application; Gradle orchestrates dependency setup, unit testing and application packaging.

## 2. Configure the application

Copy `.env.example` to `.env` and set a strong `SECRET_KEY`.

For Docker, PostgreSQL is the default database. For a simple local run, SQLite can still be used:

```text
DATABASE_URL=sqlite:///./leave_approval.db
```

## 3. Run the application locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/dashboard` and `http://localhost:8000/docs`.

## 4. Gradle build and tests

```bash
gradle clean build
```

The `build` task creates a versioned artifact at `build/dist/` and runs the API unit tests.

Run the Selenium suite with:

```bash
gradle seleniumTest
```

Selenium uses a local Chrome/Chromium driver through Selenium Manager, or a remote Selenium Grid when `SELENIUM_REMOTE_URL` is provided.

## 5. Docker and Nginx deployment

Nginx is used instead of Tomcat because the application is FastAPI/Uvicorn rather than a Java servlet/WAR application.

```bash
docker compose up -d --build
```

The public entry point is Nginx at `http://localhost:8000/dashboard`; Nginx reverse-proxies requests to FastAPI on the internal Docker network.

## 6. Jenkins CI/CD

Create a Jenkins Pipeline job connected to the repository and select `Jenkinsfile` from SCM.

Configure these Jenkins tools/credentials:

- Gradle installation named `Gradle-8`.
- Docker available to the Jenkins agent.
- JUnit plugin installed.
- Optional Docker Hub username/password credential named `dockerhub-creds`.
- Jenkins SCM credentials/webhook as appropriate for the GitHub repository.

The pipeline performs:

1. Checkout.
2. Gradle build and unit tests.
3. Artifact archival.
4. Start a temporary CI application.
5. Selenium quality gate with JUnit report.
6. Docker image build and tagging with the Jenkins build number.
7. Optional Docker Hub publication.
8. Nginx/PostgreSQL deployment with Docker Compose.
9. Health check.

A failed unit or Selenium test stops later deployment stages automatically.

## 7. Jenkins trigger

The Jenkinsfile also polls SCM every five minutes (`pollSCM('H/5 * * * *')`). A GitHub webhook can be configured for immediate builds.

For a local "start application -> trigger Jenkins -> start deployment" demonstration, configure `.env` with Jenkins credentials and run:

```bash
./scripts/start_with_jenkins.sh
```

Windows PowerShell:

```powershell
.\scripts\start_with_jenkins.ps1
```

## 8. Ansible provisioning

Use `ansible/site.yml` with `ansible/inventory.ini` to provision a clean Linux target with Docker and Docker Compose and prepare the deployment directory.

## 9. Assignment mapping

- Weeks 1-6: requirements, backlog, architecture, Git/GitHub workflow and MVP.
- Week 7: Jenkins + Gradle CI job and archived Gradle artifact.
- Week 8: Jenkins Pipeline as Code + Nginx deployment.
- Week 9: Selenium user journeys and failure screenshots.
- Week 10: Selenium quality gate and published JUnit results.
- Week 11: Docker image and container lifecycle.
- Week 12: Jenkins Docker continuous deployment.
- Weeks 13-14: Ansible provisioning, idempotency and reliability checks.
- Week 15: end-to-end release, documentation and viva evidence.
