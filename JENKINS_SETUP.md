# Jenkins setup for the Employee Leave Approval System

This project intentionally keeps the application as **FastAPI/Python** and uses **Gradle as the build/orchestration tool**. Jenkins runs Gradle, Pytest and Selenium, then builds/deploys the Docker stack.

## Jenkins prerequisites

Use a Jenkins controller/agent with the following tools available. The supplied Jenkinsfile supports both Windows and Unix-like agents:

- Git
- Python 3.11+
- Java 17+
- Docker Engine + Docker Compose plugin
- Chromium/Google Chrome for local Selenium, or Docker for the optional remote Selenium setup
- `curl` on Unix-like agents; PowerShell is used for the health check on Windows agents

## Jenkins plugins

Install or verify:

- Pipeline
- Git
- JUnit
- Credentials Binding

## Configure Gradle

Go to **Manage Jenkins → Tools → Gradle installations** and add a Gradle 8.x installation with the name:

```text
Gradle-8
```

The `Jenkinsfile` references this exact name.

## Create the Pipeline job

1. Create a new **Pipeline** job named `Employee-Leave-Approval`.
2. Under Pipeline definition, choose **Pipeline script from SCM**.
3. Select Git and enter your GitHub repository URL.
4. Select the correct credentials if the repository is private.
5. Set the script path to:

```text
Jenkinsfile
```

6. Save and use **Build Now** for the first run.

## Automatic triggering

The Jenkinsfile contains:

```groovy
triggers {
    pollSCM('H/5 * * * *')
}
```

Jenkins checks SCM for changes on the configured interval and starts a build when new source changes are detected.

For immediate GitHub-driven builds, configure a GitHub webhook to the Jenkins webhook endpoint and enable the corresponding GitHub/SCM trigger in the Jenkins job.

## Docker Hub credentials

The Docker publish stage is optional. When the `PUSH_IMAGE` parameter is enabled, configure a Jenkins username/password credential with ID:

```text
dockerhub-creds
```

Use the Docker Hub username as the credential username and an access token as the password.

## Docker permissions

The Jenkins service account must be able to execute:

```bash
docker version
docker compose version
```

On Linux this normally means granting the Jenkins service account access to the Docker socket/group according to the security policy of the machine.

## Build flow

```text
GitHub commit
    |
    v
Jenkins checkout
    |
    v
Gradle clean build
    |
    +--> Pytest + JUnit XML
    |
    +--> ZIP artifact
    |
    v
Temporary CI FastAPI server
    |
    v
Selenium quality gate
    |
    v
Docker image :BUILD_NUMBER
    |
    +--> optional Docker Hub push
    |
    v
Docker Compose deployment
    |
    +--> PostgreSQL
    +--> FastAPI/Uvicorn
    +--> Nginx reverse proxy
    |
    v
http://localhost:8000/health
```

A non-zero exit code from the Gradle, Pytest or Selenium stage prevents the later deployment stage from executing.

## Start-trigger demonstration

After setting Jenkins connection values in `.env`, these scripts send a remote build request when the application is started:

Linux/macOS:

```bash
./scripts/start_with_jenkins.sh
```

Windows PowerShell:

```powershell
.\scripts\start_with_jenkins.ps1
```

These scripts are intended for a classroom/demo workflow. For production, SCM/webhook-triggered Jenkins builds are the normal CI/CD pattern.
