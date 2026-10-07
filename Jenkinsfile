pipeline {
    agent any

    // The top-level pipeline stays on any available Jenkins executor.
    // Docker-specific stages below explicitly allocate the docker-desktop
    // agent, keeping the controller-side orchestration intact.

    parameters {
        choice(
            name: 'DEPLOY_ENV',
            choices: ['staging', 'production'],
            description: 'Deployment environment'
        )

        choice(
            name: 'DEPLOY_MODE',
            choices: ['legacy', 'docker'],
            description: 'Deployment target. Legacy uses Windows Task Scheduler/Nginx. Docker verifies and tests the Docker Compose deployment.'
        )

        booleanParam(
            name: 'PUBLISH_DOCKER_IMAGE',
            defaultValue: false,
            description: 'Week 12: publish the versioned Docker image and latest tag to a container registry.'
        )

        string(
            name: 'DOCKER_REGISTRY',
            defaultValue: 'docker.io',
            description: 'Container registry hostname used only when publishing is enabled.'
        )

        string(
            name: 'DOCKERHUB_REPOSITORY',
            defaultValue: '',
            trim: true,
            description: 'Repository path for publishing, for example username/employee-leave-approval-system. Required only when publishing is enabled.'
        )

        booleanParam(
            name: 'RUN_ANSIBLE',
            defaultValue: false,
            description: 'Week 13: run Ansible syntax/check-mode validation and LIVE configuration management/deployment inside the Docker-based Ansible environment. Disabled by default so Week 12 Docker CI/CD behavior is unchanged.'
        )

        string(
            name: 'ANSIBLE_APP_DIR',
            defaultValue: '',
            trim: true,
            description: 'Optional Week 13 Ansible application directory override for standalone Linux execution. For Jenkins live execution, leave blank; the pipeline uses /workspace/ansible-live/leaveflow.'
        )
    }

    environment {
        PYTHON_EXE        = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
        DEPLOY_ROOT       = 'C:\\ProgramData\\Jenkins\\deploy\\leaveflow'
        NGINX_HOME        = 'C:\\nginx-1.30.5'
        SELENIUM_BASE_URL = 'http://localhost/dashboard'
        BASE_URL          = 'http://localhost'
        SECRET_KEY        = credentials('leaveflow-secret-key')
        DOCKER_BASE_URL   = 'http://localhost:8000'
        DOCKER_EXE        = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe'
        DOCKER_CONFIG     = 'C:\\Users\\kphvj\\.docker'

        // Docker Desktop installs its credential helper beside docker.exe.
        // Jenkins may not inherit that directory in PATH. Each Docker
        // PowerShell step prepends this directory before invoking Docker.
        DOCKER_BIN_DIR    = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin'

        // ------------------------------------------------------------
        // Jenkins controller -> Docker Desktop inbound agent bootstrap
        // ------------------------------------------------------------
        // The agent is an inbound WebSocket agent. Its secret MUST be kept
        // in Jenkins Credentials as Secret Text with ID
        // `docker-desktop-agent-secret`; never commit the value to Git.
        JENKINS_AGENT_URL   = 'http://localhost:8081/'
        DOCKER_AGENT_NAME   = 'docker-desktop-agent'
        DOCKER_AGENT_LABEL  = 'docker-desktop'
        DOCKER_AGENT_HOME   = 'C:\\Jenkins\\docker-agent'
        DOCKER_AGENT_JAR    = 'C:\\Jenkins\\docker-agent\\agent.jar'
        JAVA_EXE            = 'C:\\Program Files\\Eclipse Adoptium\\jdk-25.0.4+7\\bin\\java.exe'

        // Week 12 release metadata. Runtime values are overwritten from the Jenkins build number.
        LEAVEFLOW_APP_IMAGE   = 'leave-approval-system:latest'
        LEAVEFLOW_APP_VERSION = 'dev'
        LEAVEFLOW_APP_LATEST  = 'leave-approval-system:latest'
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout()

        timeout(
            time: 30,
            unit: 'MINUTES'
        )
    }

    stages {

        // ============================================================
        // CONTROLLER-SIDE AGENT BOOTSTRAP
        // ============================================================
        // The built-in Jenkins executor starts the inbound Docker agent only
        // when a Docker deployment is requested. The later Docker stages use
        // node(label: 'docker-desktop') and therefore execute on the
        // docker-desktop-agent machine/workspace.

        stage('Bootstrap Docker Desktop Agent') {
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                script {
                    withCredentials([
                        string(
                            credentialsId: 'docker-desktop-agent-secret',
                            variable: 'DOCKER_AGENT_SECRET'
                        )
                    ]) {
                        powershell '''
                            $ErrorActionPreference = "Stop"

                            $agentName = $env:DOCKER_AGENT_NAME
                            $agentHome = $env:DOCKER_AGENT_HOME
                            $agentJar = $env:DOCKER_AGENT_JAR
                            $javaExe = $env:JAVA_EXE
                            $jenkinsUrl = $env:JENKINS_AGENT_URL

                            Write-Host "=========================================="
                            Write-Host "Jenkins Controller -> Docker Agent Bootstrap"
                            Write-Host "=========================================="
                            Write-Host "Agent name: $agentName"
                            Write-Host "Agent home: $agentHome"
                            Write-Host "Jenkins URL: $jenkinsUrl"

                            $controllerIdentity = (whoami).Trim()
                            Write-Host "Controller executor Windows identity: $controllerIdentity"
                            Write-Host "The Docker agent will inherit this Windows identity when started by this stage."

                            if (-not (Test-Path $javaExe)) {
                                throw "Java executable not found: $javaExe"
                            }

                            New-Item -ItemType Directory -Path $agentHome -Force | Out-Null

                            if (-not (Test-Path $agentJar)) {
                                Write-Host "agent.jar not found. Downloading from Jenkins controller..."

                                $agentJarUrl = $jenkinsUrl.TrimEnd('/') + '/jnlpJars/agent.jar'
                                & curl.exe -fL --retry 3 --retry-delay 2 -o $agentJar $agentJarUrl

                                if ($LASTEXITCODE -ne 0 -or -not (Test-Path $agentJar)) {
                                    throw "Unable to download Jenkins agent.jar from $agentJarUrl"
                                }

                                Write-Host "agent.jar downloaded successfully."
                            }
                            else {
                                Write-Host "agent.jar already exists. Reusing the local copy."
                            }

                            # Do not start a second inbound agent process with the
                            # same Jenkins node name if one is already running.
                            $needle = "-name $agentName"
                            $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                                Where-Object {
                                    $_.Name -match '^java(?:w)?(?:[.]exe)?$' -and
                                    $_.CommandLine -and
                                    $_.CommandLine.Contains($needle)
                                }

                            if ($running) {
                                Write-Host "Inbound agent process is already running. No duplicate process will be started."
                                $running | ForEach-Object {
                                    Write-Host "Existing agent PID: $($_.ProcessId)"
                                }
                                exit 0
                            }

                            Write-Host "Starting inbound WebSocket agent..."

                            $agentArguments = @(
                                '-jar',
                                $agentJar,
                                '-url',
                                $jenkinsUrl,
                                '-secret',
                                $env:DOCKER_AGENT_SECRET,
                                '-name',
                                $agentName,
                                '-webSocket',
                                '-workDir',
                                $agentHome
                            )

                            Start-Process `
                                -FilePath $javaExe `
                                -ArgumentList $agentArguments `
                                -WorkingDirectory $agentHome `
                                -WindowStyle Hidden

                            Start-Sleep -Seconds 5

                            $started = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                                Where-Object {
                                    $_.Name -match '^java(?:w)?(?:[.]exe)?$' -and
                                    $_.CommandLine -and
                                    $_.CommandLine.Contains($needle)
                                }

                            if (-not $started) {
                                throw "Docker Desktop inbound agent process did not remain running after startup."
                            }

                            Write-Host "Docker Desktop inbound agent process started successfully."
                            Write-Host "The next verification stage will wait for Jenkins to allocate the docker-desktop agent."
                        '''
                    }
                }
            }
        }

        stage('Verify Docker Agent Allocation') {
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            options {
                timeout(
                    time: 2,
                    unit: 'MINUTES'
                )
            }

            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }

            steps {
                echo "Docker agent allocated successfully: ${env.NODE_NAME}"
                echo "Docker agent workspace: ${env.WORKSPACE}"
            }
        }

        // ============================================================
        // VALIDATION & CHECKOUT
        // ============================================================

        stage('Validate Parameters') {
            steps {
                script {
                    if (!params.DEPLOY_ENV?.trim()) {
                        error(
                            'DEPLOY_ENV was not provided. ' +
                            'Use Build with Parameters and select staging or production.'
                        )
                    }

                    echo "Deployment environment: ${params.DEPLOY_ENV}"
                    echo "Deployment mode: ${params.DEPLOY_MODE}"
                }
            }
        }

        stage('Checkout') {
            steps {
                powershell '''
                    $ErrorActionPreference = "SilentlyContinue"

                    Write-Host "=========================================="
                    Write-Host "Cleaning previous Jenkins-owned FastAPI processes"
                    Write-Host "=========================================="

                    # ------------------------------------------------
                    # Stop legacy Windows Scheduled Tasks first.
                    # The legacy deployment uses the Jenkins workspace
                    # .ci-venv. If Uvicorn is still running from that
                    # environment, Windows locks native .pyd files and
                    # deleteDir() cannot clean the workspace.
                    # ------------------------------------------------

                    $taskNames = @(
                        "LeaveFlow-FastAPI-staging",
                        "LeaveFlow-FastAPI-production"
                    )

                    foreach ($taskName in $taskNames) {

                        $task = Get-ScheduledTask `
                            -TaskName $taskName `
                            -ErrorAction SilentlyContinue

                        if ($task) {
                            Write-Host "Stopping scheduled task: $taskName"

                            Stop-ScheduledTask `
                                -TaskName $taskName `
                                -ErrorAction SilentlyContinue

                            Start-Sleep -Seconds 2

                            Unregister-ScheduledTask `
                                -TaskName $taskName `
                                -Confirm:$false `
                                -ErrorAction SilentlyContinue
                        }
                    }

                    # ------------------------------------------------
                    # Kill any leftover process whose command line
                    # still references this Jenkins workspace/.ci-venv.
                    # This targets only processes owned by this pipeline's
                    # workspace rather than unrelated Python processes.
                    # ------------------------------------------------

                    $workspace = [System.IO.Path]::GetFullPath($env:WORKSPACE).TrimEnd([char]92)
                    $workspaceNeedle = (Join-Path $workspace '.ci-venv').ToLowerInvariant()

                    $workspaceProcesses = Get-CimInstance Win32_Process `
                        -ErrorAction SilentlyContinue |
                        Where-Object {
                            $_.CommandLine -and `
                            $_.CommandLine.ToLowerInvariant().Contains($workspaceNeedle)
                        }

                    foreach ($processInfo in $workspaceProcesses) {

                        Write-Host `
                            "Stopping workspace-bound process PID $($processInfo.ProcessId): $($processInfo.Name)"

                        & taskkill.exe /PID $processInfo.ProcessId /T /F | Out-Null
                    }

                    Start-Sleep -Seconds 2

                    Write-Host "Workspace process cleanup completed."
                '''

                deleteDir()

                echo 'Checking out Employee Leave Approval System...'

                git(
                    branch: 'main',
                    credentialsId: 'github-credentials',
                    url: 'https://github.com/KunalVinodJadhav7/DEVelopmentOPerationS-Project.git'
                )

                bat 'git log -1 --oneline'
                bat 'dir'
            }
        }

        // ============================================================
        // PYTHON SETUP & UNIT TESTS
        // ============================================================

        stage('Python Setup') {
            steps {
                echo 'Creating Python CI environment...'

                bat '''
                    if not exist "%PYTHON_EXE%" (
                        echo ERROR: Python executable not found.
                        exit /b 1
                    )

                    "%PYTHON_EXE%" -m venv .ci-venv

                    .ci-venv\\Scripts\\python.exe -m pip install --upgrade pip

                    .ci-venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running unit tests...'

                bat '''
                    if not exist build\\test-results mkdir build\\test-results
                    if not exist build\\uploads mkdir build\\uploads

                    .ci-venv\\Scripts\\python.exe -m pytest tests -q ^
                        --junitxml=build\\test-results\\pytest-jenkins.xml
                '''
            }

            post {
                always {
                    junit(
                        testResults: 'build/test-results/pytest-jenkins.xml',
                        allowEmptyResults: true
                    )
                }
            }
        }

        // ============================================================
        // GRADLE BUILD & ARTIFACT
        // ============================================================

        stage('Gradle Build') {
            steps {
                echo 'Building application with Gradle...'

                bat '''
                    where gradle
                    gradle --version

                    gradle --no-daemon clean build ^
                        "-PappVersion=1.0.%BUILD_NUMBER%"
                '''
            }
        }

        stage('Verify Artifact') {
            steps {
                echo 'Verifying generated ZIP artifact...'

                bat '''
                    if not exist build\\dist (
                        echo ERROR: build\\dist does not exist.
                        exit /b 1
                    )

                    dir build\\dist

                    if not exist build\\dist\\*.zip (
                        echo ERROR: No ZIP artifact found.
                        exit /b 1
                    )

                    echo ZIP artifact successfully created.
                '''
            }
        }

        stage('Archive Artifact') {
            steps {
                echo 'Archiving application artifact...'

                archiveArtifacts(
                    artifacts: 'build/dist/*.zip',
                    fingerprint: true
                )
            }
        }

        // ============================================================
        // WEEK 13 - ANSIBLE VALIDATION
        //
        // Runs inside a Docker-based Ansible validation environment so the
        // Windows Jenkins controller does not have to host native Ansible.
        // This stage is validation only; the normal Week 12 Docker deployment
        // path is untouched.
        // ============================================================

        // ============================================================
        // WEEK 13 - ANSIBLE CONFIGURATION MANAGEMENT + LIVE EXECUTION
        //
        // Jenkins runs as Windows LocalSystem, so native WSL execution is
        // intentionally avoided. Ansible runs in an official Docker CLI
        // environment with access to the Docker Desktop Linux engine.
        //
        // This stage performs:
        //   1. Ansible/collection installation
        //   2. Syntax validation
        //   3. Check-mode validation
        //   4. LIVE Ansible provisioning/deployment
        //   5. Live health verification
        // ============================================================

        stage('Week 13 - Ansible Configuration Management') {
            when {
                expression {
                    params.RUN_ANSIBLE
                }
            }

            steps {
                script {
                    withEnv([
                        "RUN_ANSIBLE_APP_DIR=/workspace/ansible-live/leaveflow",
                        "RUN_ANSIBLE_HEALTH_HOST=host.docker.internal"
                    ]) {
                        powershell '''
                            $ErrorActionPreference = "Stop"

                            $dockerExe = $env:DOCKER_EXE
                            $dockerBinDir = $env:DOCKER_BIN_DIR
                            $workspace = $env:WORKSPACE
                            $ansibleImage = 'docker:29.8.0-cli'
                            $ansibleAppDir = '/workspace/ansible-live/leaveflow'
                            $healthHost = 'host.docker.internal'

                            Write-Host "=========================================="
                            Write-Host "Week 13 Ansible Configuration Management"
                            Write-Host "=========================================="
                            Write-Host "Docker image: $ansibleImage"
                            Write-Host "Jenkins workspace: $workspace"
                            Write-Host "Ansible-managed directory: $ansibleAppDir"
                            Write-Host "Health host: $healthHost"

                            if (-not (Test-Path $dockerExe)) {
                                throw "Docker CLI not found: $dockerExe"
                            }

                            if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                                $env:PATH = "$dockerBinDir;$env:PATH"
                            }

                            & $dockerExe --version
                            if ($LASTEXITCODE -ne 0) {
                                throw 'Docker CLI verification failed.'
                            }

                            # The Ansible runner reaches Docker Desktop's Linux
                            # engine through the standard Unix Docker socket.
                            # The Jenkins workspace is mounted so managed
                            # configuration state remains visible to Jenkins.
                            $command = @'
set -eu
echo "=== Install Ansible prerequisites ==="
apk add --no-cache python3 py3-pip openssl curl
echo "=== Create Ansible virtual environment ==="
python3 -m venv /opt/ansible-venv
echo "=== Install Ansible and Docker SDK ==="
/opt/ansible-venv/bin/pip install --no-cache-dir ansible-core==2.21.4 docker==7.2.0
echo "=== Verify Docker engine socket ==="
docker info --format '{{.ServerVersion}}'
docker compose version
echo "=== Install Ansible collection ==="
/opt/ansible-venv/bin/ansible-galaxy collection install -r /workspace/ansible/requirements.yml
echo "=== Ansible version ==="
/opt/ansible-venv/bin/ansible-playbook --version
echo "=== Collection verification ==="
/opt/ansible-venv/bin/ansible-galaxy collection list | grep -A2 'community.docker' || true
echo "=== Syntax check ==="
/opt/ansible-venv/bin/ansible-playbook -i /workspace/ansible/inventory.ini /workspace/ansible/site.yml -e "app_dir=${RUN_ANSIBLE_APP_DIR}" -e "health_host=${RUN_ANSIBLE_HEALTH_HOST}" -e "release_version=1.0.${LEAVEFLOW_BUILD_NUMBER}" --syntax-check
echo "=== Check mode ==="
/opt/ansible-venv/bin/ansible-playbook -i /workspace/ansible/inventory.ini /workspace/ansible/site.yml -e "app_dir=${RUN_ANSIBLE_APP_DIR}" -e "health_host=${RUN_ANSIBLE_HEALTH_HOST}" -e "release_version=1.0.${LEAVEFLOW_BUILD_NUMBER}" --check
echo "=== LIVE Ansible execution ==="
/opt/ansible-venv/bin/ansible-playbook -i /workspace/ansible/inventory.ini /workspace/ansible/site.yml -e "app_dir=${RUN_ANSIBLE_APP_DIR}" -e "health_host=${RUN_ANSIBLE_HEALTH_HOST}" -e "release_version=1.0.${LEAVEFLOW_BUILD_NUMBER}"
echo "=== Post-deployment health verification ==="
curl -fsS --max-time 20 "http://${RUN_ANSIBLE_HEALTH_HOST}:8000/health"
echo
echo "=== Ansible-managed release marker ==="
cat "${RUN_ANSIBLE_APP_DIR}/RELEASE"
'@

                            $dockerArgs = @(
                                'run',
                                '--rm',
                                '--pull', 'missing',
                                '--env', "RUN_ANSIBLE_APP_DIR=$ansibleAppDir",
                                '--env', "RUN_ANSIBLE_HEALTH_HOST=$healthHost",
                                '--env', "LEAVEFLOW_BUILD_NUMBER=$env:BUILD_NUMBER",
                                '--env', 'DOCKER_HOST=unix:///var/run/docker.sock',
                                '--mount', "type=bind,source=$workspace,target=/workspace",
                                '--mount', 'type=bind,source=/var/run/docker.sock.raw,target=/var/run/docker.sock',
                                '--entrypoint', 'sh',
                                $ansibleImage,
                                '-c', $command
                            )

                            Write-Host "Starting live Ansible configuration-management runner..."
                            & $dockerExe @dockerArgs
                            if ($LASTEXITCODE -ne 0) {
                                throw 'Live Ansible configuration-management execution failed.'
                            }

                            Write-Host "Week 13 Ansible configuration management and live deployment succeeded."
                        '''
                    }
                }
            }
        }

        stage('Prepare Docker Release Metadata') {
            when {
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                script {
                    def releaseVersion = "1.0.${env.BUILD_NUMBER}"
                    def releaseImage = "leave-approval-system:${releaseVersion}"
                    def latestImage = 'leave-approval-system:latest'

                    def commit = bat(
                        script: '@git rev-parse --short HEAD',
                        returnStdout: true
                    ).trim()

                    def manifest = """
Week 12 Docker Release Manifest
================================
Application: Jenkins-Based Employee Leave Approval System
Jenkins Build: ${env.BUILD_NUMBER}
Deployment Environment: ${params.DEPLOY_ENV}
Git Commit: ${commit}
Docker Version: ${releaseImage}
Docker Latest Tag: ${latestImage}
Docker Registry Publishing: ${params.PUBLISH_DOCKER_IMAGE}
""".trim() + "\r\n"

                    writeFile(
                        file: 'build/docker-release-manifest.txt',
                        text: manifest
                    )

                    echo "Week 12 release: ${releaseImage}"
                    echo "Source commit: ${commit}"

                    archiveArtifacts(
                        artifacts: 'build/docker-release-manifest.txt',
                        fingerprint: true
                    )
                }
            }
        }

        // ============================================================
        // WEEK 12 - DOCKER AGENT WORKSPACE
        // ============================================================

        stage('Prepare Docker Agent Workspace') {
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                echo 'Stashing Docker deployment source for the Docker Desktop agent...'

                stash(
                    name: 'docker-deployment-source',
                    includes: """
                        Dockerfile,
                        docker-compose.yml,
                        .dockerignore,
                        .env.example,
                        README.md,
                        IMPLEMENTATION_STEPS.md,
                        requirements.txt,
                        pytest.ini,
                        build.gradle,
                        gradle.properties,
                        settings.gradle,
                        app/**/*,
                        templates/**/*,
                        frontend/**/*,
                        sql/**/*,
                        docker/**/*,
                        nginx/**/*,
                        scripts/**/*
                    """,
                    useDefaultExcludes: false
                )
            }
        }

        // ============================================================
        // FASTAPI DEPLOYMENT
        //
        // Windows Task Scheduler owns the long-running FastAPI process.
        // Jenkins creates the task, starts it, and verifies HTTP health.
        // ============================================================

        // ============================================================
        // LEGACY MODE / DOCKER PORT CONFLICT PREVENTION
        //
        // Docker Nginx publishes host port 8000. Legacy production
        // FastAPI also uses host port 8000, so the two deployment modes
        // must not run at the same time.
        //
        // This stage runs only in legacy mode. It stops the Docker Compose
        // deployment before the legacy FastAPI deployment checks port 8000.
        // Docker volumes are intentionally preserved because `docker compose
        // down` without `-v` does not remove named volumes.
        // ============================================================

        stage('Stop Docker Deployment for Legacy Mode') {
            when {
                expression {
                    params.DEPLOY_MODE == 'legacy'
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerConfig = $env:DOCKER_CONFIG

                    Write-Host "=========================================="
                    Write-Host "Checking Docker deployment before legacy deployment"
                    Write-Host "=========================================="

                    if (-not (Test-Path $dockerExe)) {
                        Write-Host "Docker CLI not found."
                        Write-Host "Continuing with legacy deployment."
                        exit 0
                    }

                    if (-not (Test-Path $dockerConfig)) {
                        Write-Host "Docker config directory not found."
                        Write-Host "Continuing with legacy deployment."
                        exit 0
                    }

                    $env:DOCKER_CONFIG = $dockerConfig

                    # Make Docker Desktop's credential helper available to this PowerShell process.
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    $dockerRunning = & $dockerExe ps `
                        --filter "name=leaveflow-nginx" `
                        --format "{{.Names}}" 2>$null

                    if ($LASTEXITCODE -ne 0) {
                        throw "Unable to query running Docker containers."
                    }

                    if ($dockerRunning -contains "leaveflow-nginx") {
                        Write-Host "Docker Nginx is running."
                        Write-Host "Stopping Docker Compose deployment to free host port 8000..."

                        Push-Location $env:WORKSPACE
                        try {
                            & $dockerExe compose down --remove-orphans

                            if ($LASTEXITCODE -ne 0) {
                                throw "Docker Compose shutdown failed."
                            }
                        }
                        finally {
                            Pop-Location
                        }

                        Write-Host "Docker deployment stopped successfully."
                    }
                    else {
                        Write-Host "Docker Nginx is not running."
                        Write-Host "No Docker shutdown required."
                    }

                    Start-Sleep -Seconds 2

                    $portCheck = Get-NetTCPConnection `
                        -LocalPort 8000 `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($portCheck) {
                        Write-Host "Port 8000 is still occupied:"
                        $portCheck | Format-Table -AutoSize
                        throw "Port 8000 is still occupied after Docker cleanup."
                    }

                    Write-Host "Port 8000 is available for legacy production deployment."
                '''
            }
        }

        stage('Deploy FastAPI') {
            when {
                expression {
                    return params.DEPLOY_MODE == 'legacy'
                }
            }

            options {
                timeout(
                    time: 3,
                    unit: 'MINUTES'
                )
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $envName = $env:DEPLOY_ENV
                    $root = $env:DEPLOY_ROOT

                    switch ($envName) {
                        "production" {
                            $port = 8000
                        }

                        "staging" {
                            $port = 8001
                        }

                        default {
                            throw "Unsupported deployment environment: $envName"
                        }
                    }

                    $taskName = "LeaveFlow-FastAPI-$envName"

                    Write-Host "=========================================="
                    Write-Host "FastAPI Deployment"
                    Write-Host "Environment : $envName"
                    Write-Host "Port        : $port"
                    Write-Host "Task        : $taskName"
                    Write-Host "=========================================="

                    $environmentDir = Join-Path $root $envName
                    $releaseDir = Join-Path $environmentDir $env:BUILD_NUMBER

                    New-Item `
                        -ItemType Directory `
                        -Force `
                        -Path $environmentDir | Out-Null

                    New-Item `
                        -ItemType Directory `
                        -Force `
                        -Path $releaseDir | Out-Null

                    Write-Host "Release directory:"
                    Write-Host $releaseDir

                    # ------------------------------------------------
                    # Locate generated application artifact
                    # ------------------------------------------------

                    $zip = Get-ChildItem "build\\dist\\*.zip" |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1

                    if (-not $zip) {
                        throw "Application ZIP was not found."
                    }

                    Write-Host "Artifact:"
                    Write-Host $zip.FullName

                    Expand-Archive `
                        -LiteralPath $zip.FullName `
                        -DestinationPath $releaseDir `
                        -Force

                    $appFile = Join-Path $releaseDir "app\\main.py"

                    if (-not (Test-Path $appFile)) {
                        throw "FastAPI application not found: $appFile"
                    }

                    Write-Host "FastAPI application found."

                    # ------------------------------------------------
                    # Jenkins Python environment
                    # ------------------------------------------------

                    $ciPython = Join-Path `
                        $env:WORKSPACE `
                        ".ci-venv\\Scripts\\python.exe"

                    if (-not (Test-Path $ciPython)) {
                        throw "Jenkins Python environment not found: $ciPython"
                    }

                    Write-Host "Runtime Python:"
                    Write-Host $ciPython

                    # ------------------------------------------------
                    # Stop and remove previous Scheduled Task
                    # ------------------------------------------------

                    $existingTask = Get-ScheduledTask `
                        -TaskName $taskName `
                        -ErrorAction SilentlyContinue

                    if ($existingTask) {

                        Write-Host "Existing FastAPI task found."

                        try {
                            Stop-ScheduledTask `
                                -TaskName $taskName `
                                -ErrorAction SilentlyContinue
                        }
                        catch {
                            Write-Host "Previous task was not running."
                        }

                        Start-Sleep -Seconds 2

                        Unregister-ScheduledTask `
                            -TaskName $taskName `
                            -Confirm:$false `
                            -ErrorAction SilentlyContinue

                        Start-Sleep -Seconds 1
                    }

                    # ------------------------------------------------
                    # Clean deployment port
                    # ------------------------------------------------

                    Write-Host "Checking port $port..."

                    $existingConnections = Get-NetTCPConnection `
                        -LocalPort $port `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($existingConnections) {

                        $existingPid = $existingConnections |
                            Select-Object -First 1 -ExpandProperty OwningProcess

                        Write-Host "Port $port is currently owned by PID $existingPid"

                        $existingProcess = Get-Process `
                            -Id $existingPid `
                            -ErrorAction SilentlyContinue

                        if ($existingProcess) {

                            Write-Host `
                                "Stopping existing process: $($existingProcess.ProcessName)"

                            Stop-Process `
                                -Id $existingPid `
                                -Force `
                                -ErrorAction Stop
                        }

                        Start-Sleep -Seconds 2
                    }

                    $stillListening = Get-NetTCPConnection `
                        -LocalPort $port `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($stillListening) {
                        throw "Port $port is still occupied after cleanup."
                    }

                    Write-Host "Port $port is available."

                    # ------------------------------------------------
                    # Runtime secret
                    # ------------------------------------------------

                    if ([string]::IsNullOrWhiteSpace($env:SECRET_KEY)) {
                        throw "SECRET_KEY was not supplied by Jenkins credentials."
                    }

                    $secretFile = Join-Path `
                        $releaseDir `
                        "runtime-secret.txt"

                    Set-Content `
                        -Path $secretFile `
                        -Value $env:SECRET_KEY `
                        -Encoding ASCII

                    if (-not (Test-Path $secretFile)) {
                        throw "Failed to create runtime secret file."
                    }

                    Write-Host "Runtime secret file created."

                    # ------------------------------------------------
                    # FastAPI logs
                    # ------------------------------------------------

                    $stdout = Join-Path `
                        $releaseDir `
                        "uvicorn.out.log"

                    $stderr = Join-Path `
                        $releaseDir `
                        "uvicorn.err.log"

                    $taskLog = Join-Path `
                        $releaseDir `
                        "task-launch.log"

                    New-Item `
                        -ItemType File `
                        -Force `
                        -Path $stdout | Out-Null

                    New-Item `
                        -ItemType File `
                        -Force `
                        -Path $stderr | Out-Null

                    New-Item `
                        -ItemType File `
                        -Force `
                        -Path $taskLog | Out-Null

                    # ------------------------------------------------
                    # Create CMD launcher
                    # ------------------------------------------------

                    $launcher = Join-Path `
                        $releaseDir `
                        "launch_fastapi.cmd"

                    $launcherContent = @"
@echo off
setlocal

echo ==========================================>>"$taskLog"
echo LeaveFlow FastAPI launcher started>>"$taskLog"
echo Date: %DATE% %TIME%>>"$taskLog"
echo Release: $releaseDir>>"$taskLog"
echo Python: $ciPython>>"$taskLog"
echo ==========================================>>"$taskLog"

cd /d "$releaseDir"

if not exist "$ciPython" (
    echo ERROR: Python executable not found.>>"$taskLog"
    exit /b 1
)

if not exist "$appFile" (
    echo ERROR: FastAPI application not found.>>"$taskLog"
    exit /b 1
)

if not exist "$secretFile" (
    echo ERROR: Secret file not found.>>"$taskLog"
    exit /b 1
)

set /p SECRET_KEY=<"$secretFile"
set PYTHONUNBUFFERED=1

echo Python executable exists.>>"$taskLog"
echo FastAPI application exists.>>"$taskLog"
echo Runtime secret loaded.>>"$taskLog"
echo Starting Uvicorn...>>"$taskLog"

"$ciPython" -m uvicorn app.main:app --host 127.0.0.1 --port $port --proxy-headers >>"$stdout" 2>>"$stderr"

set EXITCODE=%ERRORLEVEL%

echo Uvicorn exited with code %EXITCODE%.>>"$taskLog"

exit /b %EXITCODE%
"@

                    Set-Content `
                        -Path $launcher `
                        -Value $launcherContent `
                        -Encoding ASCII

                    Write-Host "FastAPI CMD launcher created:"
                    Write-Host $launcher

                    if (-not (Test-Path $launcher)) {
                        throw "FastAPI launcher was not created."
                    }

                    Write-Host "Launcher verification successful."

                    # ------------------------------------------------
                    # Windows Scheduled Task
                    # ------------------------------------------------

                    $cmdExe = Join-Path `
                        $env:WINDIR `
                        "System32\\cmd.exe"

                    if (-not (Test-Path $cmdExe)) {
                        throw "Windows CMD executable not found: $cmdExe"
                    }

                    Write-Host "CMD executable:"
                    Write-Host $cmdExe

                    $action = New-ScheduledTaskAction `
                        -Execute $cmdExe `
                        -Argument "/d /c `"$launcher`""

                    $trigger = New-ScheduledTaskTrigger `
                        -Once `
                        -At ((Get-Date).AddYears(1))

                    $principal = New-ScheduledTaskPrincipal `
                        -UserId "SYSTEM" `
                        -LogonType ServiceAccount `
                        -RunLevel Highest

                    $settings = New-ScheduledTaskSettingsSet `
                        -AllowStartIfOnBatteries `
                        -DontStopIfGoingOnBatteries `
                        -StartWhenAvailable

                    Write-Host "Registering FastAPI Scheduled Task..."

                    Register-ScheduledTask `
                        -TaskName $taskName `
                        -Action $action `
                        -Trigger $trigger `
                        -Principal $principal `
                        -Settings $settings `
                        -Description `
                            "LeaveFlow FastAPI $envName deployment managed by Jenkins" `
                        -Force | Out-Null

                    Write-Host "Scheduled Task registered successfully."

                    # ------------------------------------------------
                    # Start Scheduled Task
                    # ------------------------------------------------

                    Write-Host "Starting FastAPI Scheduled Task..."

                    Start-ScheduledTask `
                        -TaskName $taskName

                    Write-Host "FastAPI task start command returned to Jenkins."

                    Start-Sleep -Seconds 3

                    # ------------------------------------------------
                    # FastAPI health check
                    # ------------------------------------------------

                    $healthUrl = `
                        "http://127.0.0.1:$port/openapi.json"

                    $healthy = $false

                    Write-Host "Checking:"
                    Write-Host $healthUrl

                    for ($i = 1; $i -le 15; $i++) {

                        try {

                            $response = Invoke-WebRequest `
                                -Uri $healthUrl `
                                -UseBasicParsing `
                                -TimeoutSec 5

                            if ($response.StatusCode -eq 200) {

                                $healthy = $true

                                Write-Host "FastAPI is healthy. HTTP 200"

                                break
                            }
                        }
                        catch {

                            Write-Host `
                                "Waiting for FastAPI... attempt $i/15"
                        }

                        Start-Sleep -Seconds 2
                    }

                    # ------------------------------------------------
                    # Diagnostics if FastAPI failed
                    # ------------------------------------------------

                    if (-not $healthy) {

                        Write-Host "=========================================="
                        Write-Host "TASK LAUNCH LOG"
                        Write-Host "=========================================="

                        if (Test-Path $taskLog) {
                            Get-Content -LiteralPath $taskLog
                        }
                        else {
                            Write-Host "Task launch log was not created."
                        }

                        Write-Host "=========================================="
                        Write-Host "FASTAPI STDOUT"
                        Write-Host "=========================================="

                        if (Test-Path $stdout) {
                            Get-Content -LiteralPath $stdout
                        }
                        else {
                            Write-Host "FastAPI stdout log was not created."
                        }

                        Write-Host "=========================================="
                        Write-Host "FASTAPI STDERR"
                        Write-Host "=========================================="

                        if (Test-Path $stderr) {
                            Get-Content -LiteralPath $stderr
                        }
                        else {
                            Write-Host "FastAPI stderr log was not created."
                        }

                        Write-Host "=========================================="
                        Write-Host "SCHEDULED TASK INFO"
                        Write-Host "=========================================="

                        $taskInfo = Get-ScheduledTaskInfo `
                            -TaskName $taskName `
                            -ErrorAction SilentlyContinue

                        if ($taskInfo) {

                            Write-Host "Last Run Time:"
                            Write-Host $taskInfo.LastRunTime

                            Write-Host "Last Task Result:"
                            Write-Host $taskInfo.LastTaskResult

                            Write-Host "Next Run Time:"
                            Write-Host $taskInfo.NextRunTime
                        }
                        else {
                            Write-Host "Scheduled Task information unavailable."
                        }

                        Write-Host "=========================================="
                        Write-Host "PORT CHECK"
                        Write-Host "=========================================="

                        $portCheck = Get-NetTCPConnection `
                            -LocalPort $port `
                            -State Listen `
                            -ErrorAction SilentlyContinue

                        if ($portCheck) {
                            $portCheck | Format-Table -AutoSize
                        }
                        else {
                            Write-Host "Nothing is listening on port $port."
                        }

                        throw "FastAPI health check failed."
                    }

                    # ------------------------------------------------
                    # Remove temporary secret
                    # ------------------------------------------------

                    Remove-Item `
                        -LiteralPath $secretFile `
                        -Force `
                        -ErrorAction SilentlyContinue

                    Write-Host "Temporary runtime secret removed."

                    Write-Host "=========================================="
                    Write-Host "FASTAPI DEPLOYMENT SUCCESSFUL"
                    Write-Host "Environment : $envName"
                    Write-Host "Release     : $releaseDir"
                    Write-Host "Port        : $port"
                    Write-Host "URL         : http://127.0.0.1:$port"
                    Write-Host "Task        : $taskName"
                    Write-Host "=========================================="
                '''
            }
        }

        // ============================================================
        // FASTAPI VERIFICATION
        // ============================================================

        stage('Deployment Verification') {
            when {
                expression {
                    return params.DEPLOY_MODE == 'legacy'
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    if ($env:DEPLOY_ENV -eq "production") {
                        $port = 8000
                    }
                    else {
                        $port = 8001
                    }

                    $url = `
                        "http://127.0.0.1:$port/openapi.json"

                    Write-Host "=========================================="
                    Write-Host "Final FastAPI Verification"
                    Write-Host "Testing: $url"
                    Write-Host "=========================================="

                    $response = Invoke-WebRequest `
                        -Uri $url `
                        -UseBasicParsing `
                        -TimeoutSec 10

                    if ($response.StatusCode -ne 200) {
                        throw "FastAPI verification failed."
                    }

                    Write-Host "Application is responding successfully."
                    Write-Host "HTTP Status: $($response.StatusCode)"
                '''
            }
        }

        // ============================================================
        // NGINX
        // ============================================================

        stage('Nginx Setup') {
            when {
                allOf {
                    expression {
                        params.DEPLOY_MODE == 'legacy'
                    }
                    expression {
                        params.DEPLOY_ENV == 'production'
                    }
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $nginxHome = $env:NGINX_HOME

                    $nginxExe = Join-Path `
                        $nginxHome `
                        "nginx.exe"

                    $sourceConfig = Join-Path `
                        $env:WORKSPACE `
                        "nginx\\nginx.conf"

                    $targetConfig = Join-Path `
                        $nginxHome `
                        "conf\\nginx.conf"

                    Write-Host "=========================================="
                    Write-Host "Nginx Configuration"
                    Write-Host "Nginx Home: $nginxHome"
                    Write-Host "=========================================="

                    if (-not (Test-Path $nginxExe)) {
                        throw "Nginx executable not found: $nginxExe"
                    }

                    if (-not (Test-Path $sourceConfig)) {
                        throw "Repository Nginx configuration not found: $sourceConfig"
                    }

                    Copy-Item `
                        -Path $sourceConfig `
                        -Destination $targetConfig `
                        -Force

                    Write-Host "Nginx configuration copied."

                    Write-Host "Testing Nginx configuration..."

                    & $nginxExe `
                        -p "$nginxHome\\" `
                        -c "conf\\nginx.conf" `
                        -t

                    if ($LASTEXITCODE -ne 0) {
                        throw "Nginx configuration test failed."
                    }

                    Write-Host "Nginx configuration test successful."

                    $nginxProcesses = Get-Process `
                        nginx `
                        -ErrorAction SilentlyContinue

                    if ($nginxProcesses) {

                        Write-Host "Nginx is already running. Reloading..."

                        & $nginxExe `
                            -p "$nginxHome\\" `
                            -c "conf\\nginx.conf" `
                            -s reload

                        if ($LASTEXITCODE -ne 0) {
                            throw "Nginx reload failed."
                        }

                        Write-Host "Nginx reload successful."
                    }
                    else {

                        Write-Host "Nginx is not running. Starting Nginx..."

                        Start-Process `
                            -FilePath $nginxExe `
                            -WorkingDirectory $nginxHome `
                            -WindowStyle Hidden

                        Start-Sleep -Seconds 3

                        $nginxProcesses = Get-Process `
                            nginx `
                            -ErrorAction SilentlyContinue

                        if (-not $nginxProcesses) {
                            throw "Nginx failed to start."
                        }

                        Write-Host "Nginx started successfully."
                    }
                '''
            }
        }

        // ============================================================
        // NGINX VERIFICATION
        // ============================================================

        stage('Nginx Verification') {
            when {
                allOf {
                    expression {
                        params.DEPLOY_MODE == 'legacy'
                    }
                    expression {
                        params.DEPLOY_ENV == 'production'
                    }
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $url = "http://localhost/openapi.json"
                    $healthy = $false

                    Write-Host "=========================================="
                    Write-Host "Nginx End-to-End Verification"
                    Write-Host "Testing: $url"
                    Write-Host "=========================================="

                    for ($i = 1; $i -le 10; $i++) {

                        try {

                            $response = Invoke-WebRequest `
                                -Uri $url `
                                -UseBasicParsing `
                                -TimeoutSec 5

                            if ($response.StatusCode -eq 200) {

                                $healthy = $true

                                Write-Host `
                                    "Nginx reverse proxy verification successful."

                                Write-Host `
                                    "HTTP Status: $($response.StatusCode)"

                                break
                            }
                        }
                        catch {

                            Write-Host `
                                "Waiting for Nginx... attempt $i/10"
                        }

                        Start-Sleep -Seconds 2
                    }

                    if (-not $healthy) {
                        throw "Nginx end-to-end verification failed."
                    }

                    Write-Host "=========================================="
                    Write-Host "NGINX + FASTAPI VERIFICATION SUCCESSFUL"
                    Write-Host "URL: http://localhost/openapi.json"
                    Write-Host "=========================================="
                '''
            }
        }

        // ============================================================
        // DOCKER INTEGRATION
        // ============================================================

        // Every stage in this Docker section is intentionally bound to the
        // Docker Desktop agent. The current node is named
        // `docker-desktop-agent` and carries the `docker-desktop` label.
        stage('Ensure Docker Desktop Running') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                deleteDir()
                unstash 'docker-deployment-source'

                echo 'Ensuring Docker Desktop and the Linux Docker Engine are available...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerBinDir = $env:DOCKER_BIN_DIR

                    Write-Host "=========================================="
                    Write-Host "Ensure Docker Desktop Running"
                    Write-Host "=========================================="

                    if (-not (Test-Path $dockerExe)) {
                        throw "Docker CLI not found: $dockerExe"
                    }

                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    # Always use the Docker Desktop Linux engine expected by
                    # the Week 11/12 Compose deployment.
                    $currentContext = (& $dockerExe context show 2>$null).Trim()
                    Write-Host "Current Docker context: $currentContext"

                    if ($currentContext -ne 'desktop-linux') {
                        Write-Host "Switching Docker context to desktop-linux..."
                        & $dockerExe context use desktop-linux
                        if ($LASTEXITCODE -ne 0) {
                            throw "Unable to select Docker context desktop-linux."
                        }
                    }

                    # First check whether the engine is already reachable.
                    & $dockerExe info *> $null

                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "Docker Engine is already running and reachable."
                        exit 0
                    }

                    Write-Host "Docker Engine is not currently reachable."
                    Write-Host "Attempting to start Docker Desktop..."

                    # Docker Desktop's CLI plugin is preferred because it starts
                    # Docker Desktop through its supported command interface.
                    & $dockerExe desktop start
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Desktop could not be started from the Docker agent. Ensure the docker-desktop agent runs under the Windows user that owns the Docker Desktop installation."
                    }

                    $dockerReady = $false

                    for ($i = 1; $i -le 60; $i++) {
                        Start-Sleep -Seconds 5

                        & $dockerExe info *> $null

                        if ($LASTEXITCODE -eq 0) {
                            $dockerReady = $true
                            Write-Host "Docker Engine became available on attempt $i/60."
                            break
                        }

                        Write-Host "Waiting for Docker Engine... attempt $i/60"
                    }

                    if (-not $dockerReady) {
                        throw "Docker Desktop was started, but the Docker Linux Engine did not become available within 5 minutes."
                    }

                    Write-Host "Docker Desktop and Docker Engine are ready for Jenkins."
                '''
            }
        }

        stage('Docker Environment Verification') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                echo 'Verifying Docker Engine and Docker Compose access...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerConfig = $env:DOCKER_CONFIG

                    Write-Host "=========================================="
                    Write-Host "Docker Environment Verification"
                    Write-Host "=========================================="

                    if (-not (Test-Path $dockerExe)) {
                        throw "Docker CLI not found: $dockerExe"
                    }

                    if (-not (Test-Path $dockerConfig)) {
                        throw "Docker config directory not found: $dockerConfig"
                    }

                    $env:DOCKER_CONFIG = $dockerConfig

                    # Docker Desktop keeps docker-credential-desktop.exe
                    # beside docker.exe. The Jenkins service environment may
                    # not contain that directory in PATH even though the
                    # Docker CLI itself is reachable by absolute path.
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    $credentialHelper = Get-Command `
                        docker-credential-desktop.exe `
                        -ErrorAction SilentlyContinue

                    if (-not $credentialHelper) {
                        throw "Docker credential helper not found on PATH: docker-credential-desktop.exe"
                    }

                    Write-Host "Docker CLI: $dockerExe"
                    Write-Host "Docker Config: $env:DOCKER_CONFIG"
                    Write-Host "Docker credential helper: $($credentialHelper.Source)"

                    & $dockerExe --version
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker CLI version check failed."
                    }

                    & $dockerExe info
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Engine is not accessible from Jenkins."
                    }

                    $pluginPath = Join-Path (Join-Path $dockerConfig "cli-plugins") "docker-compose.exe"

                    if (-not (Test-Path $pluginPath)) {
                        throw "Docker Compose CLI plugin was not found: $pluginPath"
                    }

                    Write-Host "Compose plugin: $pluginPath"
                    & $pluginPath version
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Compose plugin executable check failed."
                    }

                    & $dockerExe compose version
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Compose command failed from Jenkins."
                    }

                    Write-Host "Docker Engine and Docker Compose verification successful."
                '''
            }
        }

        // ============================================================
        // DOCKER COMPOSE DEPLOYMENT
        // ============================================================

        stage('Clean Docker Deployment State') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                echo 'Resetting the previous Docker Compose deployment...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    $composeFile = Join-Path $env:WORKSPACE 'docker-compose.yml'
                    $secretFile = Join-Path (Join-Path $env:WORKSPACE 'secrets') 'leaveflow_secret_key.txt'
                    $releaseVersion = "1.0.$($env:BUILD_NUMBER)"
                    $releaseImage = "leave-approval-system:$releaseVersion"
                    $latestImage = 'leave-approval-system:latest'

                    Write-Host "=========================================="
                    Write-Host "Fresh Docker Run Cleanup"
                    Write-Host "=========================================="

                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    if (-not (Test-Path $composeFile)) {
                        throw "docker-compose.yml not found: $composeFile"
                    }

                    if ([string]::IsNullOrWhiteSpace($env:SECRET_KEY)) {
                        throw "Jenkins credential leaveflow-secret-key is empty."
                    }

                    # Compose validates file-backed secrets while reading the
                    # project, so create the runtime secret before running
                    # the cleanup command on a completely fresh workspace.
                    $secretDir = Split-Path -Parent $secretFile
                    New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
                    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                    [System.IO.File]::WriteAllText(
                        $secretFile,
                        $env:SECRET_KEY,
                        $utf8NoBom
                    )

                    # Stop and remove the entire previous Compose stack.
                    # --volumes guarantees a new PostgreSQL data directory
                    # and a new application upload volume on every run.
                    & $dockerExe compose -f $composeFile down --volumes --remove-orphans
                    if ($LASTEXITCODE -ne 0) {
                        throw "Previous Docker Compose deployment cleanup failed."
                    }

                    # Remove the project-created images so this run builds
                    # fresh application and PostgreSQL images instead of
                    # reusing an older tagged image. Build cache remains
                    # available unless the deployment step disables it.
                    $images = @(
                        $latestImage,
                        $releaseImage,
                        'leaveflow-postgres:16-alpine-locales'
                    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

                    foreach ($image in $images) {
                        # docker image inspect returns exit code 1 when an image
                        # does not exist. Do not invoke inspect here because a
                        # native non-zero exit can be promoted to a Jenkins
                        # PowerShell failure even when its output is redirected.
                        $imageId = (& $dockerExe images -q $image 2>$null | Select-Object -First 1)

                        if (-not [string]::IsNullOrWhiteSpace($imageId)) {
                            Write-Host "Removing previous image: $image"
                            & $dockerExe image rm -f $image
                            if ($LASTEXITCODE -ne 0) {
                                throw "Failed to remove previous Docker image: $image"
                            }
                        }
                        else {
                            Write-Host "Previous image not present: $image"
                        }
                    }

                    Write-Host "Runtime secret file prepared for the fresh Compose deployment."
                    Write-Host "Previous Docker deployment state removed. Fresh run is ready."
                '''
            }
        }

        stage('Deploy Docker Compose') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            options {
                timeout(
                    time: 10,
                    unit: 'MINUTES'
                )
            }

            steps {
                echo 'Building and starting the Docker Compose deployment...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    $composeFile = Join-Path $env:WORKSPACE 'docker-compose.yml'
                    $composeCiFile = Join-Path $env:WORKSPACE 'docker-compose.week12.yml'
                    $secretDir = Join-Path $env:WORKSPACE 'secrets'
                    $secretFile = Join-Path $secretDir 'leaveflow_secret_key.txt'

                    # Derive Week 12 release metadata directly from Jenkins BUILD_NUMBER.
                    # Do not rely on a previous Groovy env assignment surviving stage boundaries.
                    $releaseVersion = "1.0.$($env:BUILD_NUMBER)"
                    $releaseImage = "leave-approval-system:$releaseVersion"
                    $latestImage = 'leave-approval-system:latest'
                    $env:LEAVEFLOW_APP_VERSION = $releaseVersion
                    $env:LEAVEFLOW_APP_IMAGE = $releaseImage
                    $env:LEAVEFLOW_APP_LATEST = $latestImage

                    Write-Host "=========================================="
                    Write-Host "Docker Compose Deployment"
                    Write-Host "=========================================="

                    # Docker Desktop's credential helper must be on PATH for image pulls/builds.
                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    if (-not (Test-Path $composeFile)) {
                        throw "docker-compose.yml not found: $composeFile"
                    }

                    if ([string]::IsNullOrWhiteSpace($env:SECRET_KEY)) {
                        throw "Jenkins credential leaveflow-secret-key is empty."
                    }

                    # docker-compose.yml uses a file-backed Compose secret.
                    # Create it from the Jenkins credential without printing
                    # the secret value to the console.
                    New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

                    # Write the secret as UTF-8 without a BOM so the Linux
                    # container receives exactly the credential value.
                    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                    [System.IO.File]::WriteAllText(
                        $secretFile,
                        $env:SECRET_KEY,
                        $utf8NoBom
                    )

                    if (-not (Test-Path $secretFile)) {
                        throw "Docker secret file was not created."
                    }

                    Write-Host "Compose file: $composeFile"
                    Write-Host "Runtime secret file created for Compose."

                    # Keep the Week 11 repository Compose file unchanged.
                    # Week 12 creates a temporary Compose copy so the app service
                    # builds and deploys the immutable Jenkins build tag.
                    Copy-Item -LiteralPath $composeFile -Destination $composeCiFile -Force
                    $composeContent = Get-Content -LiteralPath $composeCiFile -Raw
                    $composeContent = $composeContent.Replace('image: leave-approval-system:latest', "image: $releaseImage")
                    Set-Content -LiteralPath $composeCiFile -Value $composeContent -Encoding UTF8

                    Write-Host "Week 12 Compose file: $composeCiFile"
                    Write-Host "Week 12 Compose application image: $releaseImage"

                    & $dockerExe compose -f $composeCiFile config | Out-Null
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Compose configuration validation failed."
                    }

                    # Week 12: deploy the immutable build-specific image rather
                    # than the mutable :latest tag. Compose consumes these values
                    # from the PowerShell process environment.
                    if ([string]::IsNullOrWhiteSpace($env:LEAVEFLOW_APP_IMAGE)) {
                        throw "Week 12 Docker image tag was not prepared."
                    }

                    if ([string]::IsNullOrWhiteSpace($env:LEAVEFLOW_APP_VERSION)) {
                        throw "Week 12 Docker image version was not prepared."
                    }

                    Write-Host "Release image: $env:LEAVEFLOW_APP_IMAGE"
                    Write-Host "Release version: $env:LEAVEFLOW_APP_VERSION"

                    # Build the application and PostgreSQL images from scratch.
                    & $dockerExe compose -f $composeCiFile build --no-cache
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Compose image build failed."
                    }

                    $builtImageId = (& $dockerExe images -q $env:LEAVEFLOW_APP_IMAGE 2>$null | Select-Object -First 1)
                    if ([string]::IsNullOrWhiteSpace($builtImageId)) {
                        throw "Versioned Docker image was not created: $env:LEAVEFLOW_APP_IMAGE"
                    }

                    Write-Host "Versioned Docker image created: $env:LEAVEFLOW_APP_IMAGE"
                    Write-Host "Image ID: $builtImageId"

                    # Create a completely new container set from the fresh images.
                    & $dockerExe compose -f $composeCiFile up -d --remove-orphans --force-recreate
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker Compose deployment failed."
                    }

                    Write-Host "Fresh Docker Compose services started with $env:LEAVEFLOW_APP_IMAGE."

                    $healthy = $false
                    for ($i = 1; $i -le 30; $i++) {
                        $appState = (& $dockerExe inspect leaveflow-app --format '{{.State.Status}}' 2>$null).Trim()
                        $appHealth = (& $dockerExe inspect leaveflow-app --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>$null).Trim()
                        $dbState = (& $dockerExe inspect leaveflow-db --format '{{.State.Status}}' 2>$null).Trim()
                        $dbHealth = (& $dockerExe inspect leaveflow-db --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>$null).Trim()
                        $nginxState = (& $dockerExe inspect leaveflow-nginx --format '{{.State.Status}}' 2>$null).Trim()

                        Write-Host "Attempt $i/30 - app=$appState/$appHealth db=$dbState/$dbHealth nginx=$nginxState"

                        if ($appState -eq 'running' -and $appHealth -eq 'healthy' -and
                            $dbState -eq 'running' -and $dbHealth -eq 'healthy' -and
                            $nginxState -eq 'running') {
                            $healthy = $true
                            break
                        }

                        Start-Sleep -Seconds 5
                    }

                    if (-not $healthy) {
                        Write-Host "Docker Compose services did not reach the expected state."
                        & $dockerExe compose -f $composeFile ps
                        throw "Docker Compose deployment health verification failed."
                    }

                    Write-Host "Docker Compose deployment is running and healthy."

                    # Update :latest only after the immutable release has
                    # successfully passed the deployment health gate.
                    & $dockerExe tag $env:LEAVEFLOW_APP_IMAGE $env:LEAVEFLOW_APP_LATEST
                    if ($LASTEXITCODE -ne 0) {
                        throw "Failed to update Docker latest tag."
                    }

                    Write-Host "Latest tag updated: $env:LEAVEFLOW_APP_LATEST -> $env:LEAVEFLOW_APP_IMAGE"
                '''
            }
        }

        stage('Docker Container Verification') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                echo 'Verifying the Week 11/12 Docker deployment on the Docker Desktop agent...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    $composeFile = Join-Path $env:WORKSPACE 'docker-compose.week12.yml'
                    $expectedVersion = "1.0.$($env:BUILD_NUMBER)"
                    $expectedImage = "leave-approval-system:$expectedVersion"
                    $latestImage = 'leave-approval-system:latest'

                    # Keep the credential helper available for all Docker commands in this step.
                    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                        $env:PATH = "$dockerBinDir;$env:PATH"
                    }

                    function Invoke-DockerChecked {
                        param(
                            [Parameter(Mandatory=$true)]
                            [string[]]$Arguments,
                            [string]$FailureMessage = 'Docker command failed.'
                        )

                        & $dockerExe @Arguments
                        if ($LASTEXITCODE -ne 0) {
                            throw $FailureMessage
                        }
                    }

                    Write-Host "=========================================="
                    Write-Host "Docker container status"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('compose','-f',$composeFile,'ps') 'docker compose ps failed.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Docker image verification"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('image','inspect',$latestImage) 'Application latest image was not found.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Application container health"
                    Write-Host "=========================================="
                    $appState = (& $dockerExe inspect leaveflow-app --format '{{.State.Status}}').Trim()
                    $appHealth = (& $dockerExe inspect leaveflow-app --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}').Trim()
                    if ($appState -ne 'running' -or $appHealth -ne 'healthy') {
                        throw "leaveflow-app is not healthy: state=$appState health=$appHealth"
                    }
                    Write-Host "leaveflow-app state=$appState health=$appHealth"

                    $deployedImage = (& $dockerExe inspect leaveflow-app --format '{{.Config.Image}}').Trim()
                    if ($deployedImage -ne $expectedImage) {
                        throw "Docker deployment is not running the expected release image. Expected=$expectedImage Actual=$deployedImage"
                    }
                    Write-Host "Expected release image: $expectedImage"
                    Write-Host "Deployed release image: $deployedImage"

                    # Read the complete label map as JSON. This avoids quoting a
                    # dotted OCI label key inside Docker's Go-template syntax,
                    # which can be misparsed by the Windows/PowerShell invocation.
                    $labelsJson = (& $dockerExe image inspect $expectedImage --format '{{json .Config.Labels}}' 2>&1)
                    if ($LASTEXITCODE -ne 0) {
                        throw "Docker image label inspection failed for $expectedImage."
                    }

                    try {
                        $labels = $labelsJson | ConvertFrom-Json
                    }
                    catch {
                        throw "Docker image labels could not be parsed as JSON: $labelsJson"
                    }

                    $imageVersionProperty = $labels.PSObject.Properties['org.opencontainers.image.version']
                    $imageVersion = if ($imageVersionProperty) {
                        [string]$imageVersionProperty.Value
                    }
                    else {
                        ''
                    }

                    if ($imageVersion -ne $expectedVersion) {
                        throw "Docker image version label mismatch. Expected=$expectedVersion Actual=$imageVersion"
                    }
                    Write-Host "Docker image version label: $imageVersion"

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Database container health"
                    Write-Host "=========================================="
                    $dbState = (& $dockerExe inspect leaveflow-db --format '{{.State.Status}}').Trim()
                    $dbHealth = (& $dockerExe inspect leaveflow-db --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}').Trim()
                    if ($dbState -ne 'running' -or $dbHealth -ne 'healthy') {
                        throw "leaveflow-db is not healthy: state=$dbState health=$dbHealth"
                    }
                    Write-Host "leaveflow-db state=$dbState health=$dbHealth"

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Nginx container status"
                    Write-Host "=========================================="
                    $nginxState = (& $dockerExe inspect leaveflow-nginx --format '{{.State.Status}}').Trim()
                    if ($nginxState -ne 'running') {
                        throw "leaveflow-nginx is not running: state=$nginxState"
                    }
                    Write-Host "leaveflow-nginx state=$nginxState"

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "PostgreSQL readiness"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('exec','leaveflow-db','pg_isready','-U','postgres','-d','leave_approval_db') 'PostgreSQL readiness check failed.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Docker logs"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('logs','--tail','50','leaveflow-app') 'Application container logs could not be read.'
                    Invoke-DockerChecked @('logs','--tail','50','leaveflow-db') 'Database container logs could not be read.'
                    Invoke-DockerChecked @('logs','--tail','50','leaveflow-nginx') 'Nginx container logs could not be read.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Volume verification"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('inspect','leaveflow-app','--format','{{json .Mounts}}') 'Application volume verification failed.'
                    Invoke-DockerChecked @('inspect','leaveflow-db','--format','{{json .Mounts}}') 'Database volume verification failed.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Public Docker health"
                    Write-Host "=========================================="
                    & curl.exe -f --max-time 20 "$env:DOCKER_BASE_URL/health"
                    if ($LASTEXITCODE -ne 0) {
                        throw "Public Docker health endpoint failed."
                    }

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Public Docker OpenAPI verification"
                    Write-Host "=========================================="
                    & curl.exe -f --max-time 20 "$env:DOCKER_BASE_URL/openapi.json" | Out-Null
                    if ($LASTEXITCODE -ne 0) {
                        throw "Public Docker OpenAPI endpoint failed."
                    }

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Nginx to FastAPI verification"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('exec','leaveflow-nginx','wget','-qO-','http://app:8000/openapi.json') 'Nginx to FastAPI verification failed.' | Out-Null

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Docker upload persistence verification"
                    Write-Host "=========================================="
                    Invoke-DockerChecked @('exec','leaveflow-app','sh','-c',"echo 'week11-upload-test' > /app/uploads/docker-test.txt") 'Unable to create Docker upload persistence marker.'
                    Invoke-DockerChecked @('compose','-f',$composeFile,'up','-d','--force-recreate','app') 'Application container recreation failed.'

                    $recreatedHealthy = $false
                    for ($i = 1; $i -le 20; $i++) {
                        $currentState = (& $dockerExe inspect leaveflow-app --format '{{.State.Status}}').Trim()
                        $currentHealth = (& $dockerExe inspect leaveflow-app --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}').Trim()
                        Write-Host "Recreate health attempt $i/20 - state=$currentState health=$currentHealth"

                        if ($currentState -eq 'running' -and $currentHealth -eq 'healthy') {
                            $recreatedHealthy = $true
                            break
                        }
                        Start-Sleep -Seconds 3
                    }

                    if (-not $recreatedHealthy) {
                        throw "Application did not become healthy after container recreation."
                    }

                    Invoke-DockerChecked @('exec','leaveflow-app','sh','-c',"grep -Fx 'week11-upload-test' /app/uploads/docker-test.txt") 'Docker upload-volume persistence verification failed.'

                    Write-Host ""
                    Write-Host "=========================================="
                    Write-Host "Docker verification successful"
                    Write-Host "=========================================="
                '''
            }
        }

        // ============================================================
        // SELENIUM CONFIGURATION
        // ============================================================
        // Selenium remains on the normal Jenkins executor. Docker containers
        // are running on the docker-desktop agent on this same Windows host,
        // so the existing localhost Docker URL remains valid.

        stage('Configure Selenium Target') {
            steps {
                script {

                    if (params.DEPLOY_MODE == 'docker') {

                        env.SELENIUM_BASE_URL =
                            "${env.DOCKER_BASE_URL}/dashboard"

                        env.BASE_URL =
                            env.DOCKER_BASE_URL

                        echo 'Selenium target: Docker Nginx -> FastAPI deployment.'
                    }
                    else if (params.DEPLOY_ENV == 'production') {

                        env.SELENIUM_BASE_URL =
                            'http://localhost/dashboard'

                        env.BASE_URL =
                            'http://localhost'

                        echo 'Selenium target: production through Windows Nginx.'
                    }
                    else {

                        env.SELENIUM_BASE_URL =
                            'http://127.0.0.1:8001/dashboard'

                        env.BASE_URL =
                            'http://127.0.0.1:8001'

                        echo 'Selenium target: staging through FastAPI.'
                    }
                }
            }
        }

        // ============================================================
        // SELENIUM TARGET VERIFICATION
        // ============================================================

        stage('Verify Selenium Target') {
            steps {
                echo 'Verifying Selenium target...'

                bat '''
                    echo ==========================================
                    echo Selenium Target Verification
                    echo ==========================================

                    if "%DEPLOY_MODE%"=="docker" (
                        set "TARGET_URL=http://localhost:8000/dashboard"
                    ) else if "%DEPLOY_ENV%"=="production" (
                        set "TARGET_URL=http://localhost/dashboard"
                    ) else (
                        set "TARGET_URL=http://127.0.0.1:8001/dashboard"
                    )

                    echo Target URL: %TARGET_URL%

                    curl.exe -f --max-time 20 "%TARGET_URL%"
                '''
            }
        }

        // ============================================================
        // SELENIUM WEEK 10 TESTS
        // ============================================================

        stage('Selenium Integration Tests') {
            steps {
                echo 'Running Week 10 Selenium integration tests...'

                bat '''
                    if not exist test-results mkdir test-results
                    if not exist selenium_tests\\artifacts mkdir selenium_tests\\artifacts

                    rem ------------------------------------------------
                    rem Pass both Selenium URL variables.
                    rem test_workflow.py reads BASE_URL, while the smoke
                    rem tests use the base_url fixture from conftest.py,
                    rem which reads SELENIUM_BASE_URL.
                    rem ------------------------------------------------
                    if "%DEPLOY_MODE%"=="docker" (
                        set "BASE_URL=%DOCKER_BASE_URL%"
                        set "SELENIUM_BASE_URL=%DOCKER_BASE_URL%/dashboard"
                    ) else if "%DEPLOY_ENV%"=="production" (
                        set "BASE_URL=http://localhost"
                        set "SELENIUM_BASE_URL=http://localhost/dashboard"
                    ) else (
                        set "BASE_URL=http://127.0.0.1:8001"
                        set "SELENIUM_BASE_URL=http://127.0.0.1:8001/dashboard"
                    )

                    echo Selenium BASE_URL: %BASE_URL%
                    echo Selenium SELENIUM_BASE_URL: %SELENIUM_BASE_URL%

                    set "PYTHONUNBUFFERED=1"

                    .ci-venv\\Scripts\\python.exe -m pytest selenium_tests ^
                        -v ^
                        --junitxml=test-results\\selenium-results.xml
                '''
            }

            post {
                always {

                    junit(
                        testResults: 'test-results/selenium-results.xml',
                        allowEmptyResults: true
                    )

                    archiveArtifacts(
                        artifacts: 'selenium_tests/artifacts/**/*',
                        allowEmptyArchive: true
                    )
                }
            }
        }

        // ============================================================
        // WEEK 12 - OPTIONAL CONTAINER REGISTRY PUBLISH
        // ============================================================

        stage('Publish Docker Image') {
            agent {
                node {
                    label 'docker-desktop-agent'
                    customWorkspace 'C:\\Jenkins\\docker-agent-workspace\\Leave-Approval-CI_CD'
                }
            }
            when {
                beforeAgent true
                allOf {
                    expression { params.DEPLOY_MODE == 'docker' }
                    expression { params.PUBLISH_DOCKER_IMAGE }
                }
            }

            steps {
                script {
                    def publishRegistry = params.DOCKER_REGISTRY?.trim()
                    if (!publishRegistry) {
                        publishRegistry = 'docker.io'
                    }

                    def publishRepository = params.DOCKERHUB_REPOSITORY?.trim()
                    if (!publishRepository) {
                        error(
                            'DOCKERHUB_REPOSITORY is required when PUBLISH_DOCKER_IMAGE is enabled. ' +
                            'Example: username/employee-leave-approval-system'
                        )
                    }

                    // Docker Hub username is intentionally explicit. The Jenkins
                    // credential stores only the PAT, avoiding ambiguity in the
                    // username/password credential binding.
                    def dockerHubUsername = 'kphvj'

                    withEnv([
                        "PUBLISH_REGISTRY=${publishRegistry}",
                        "PUBLISH_REPOSITORY=${publishRepository}",
                        "DOCKERHUB_USERNAME=${dockerHubUsername}"
                    ]) {
                        withCredentials([
                            string(
                                credentialsId: 'dockerhub-credentials',
                                variable: 'DOCKER_PASSWORD'
                            )
                        ]) {
                            powershell '''
                            $ErrorActionPreference = "Stop"

                            $dockerExe = $env:DOCKER_EXE
                            $dockerBinDir = $env:DOCKER_BIN_DIR
                            $registry = $env:PUBLISH_REGISTRY.Trim()
                            $repository = $env:PUBLISH_REPOSITORY.Trim()
                            $dockerUsername = $env:DOCKERHUB_USERNAME.Trim()
                            $dockerPassword = $env:DOCKER_PASSWORD.Trim()
                            $releaseVersion = "1.0.$($env:BUILD_NUMBER)"
                            $releaseImage = "leave-approval-system:$releaseVersion"

                            if (-not (Test-Path $dockerExe)) {
                                throw "Docker CLI not found: $dockerExe"
                            }

                            if ([string]::IsNullOrWhiteSpace($dockerUsername)) {
                                throw "Docker Hub username was not configured."
                            }

                            if ([string]::IsNullOrWhiteSpace($dockerPassword)) {
                                throw "Docker Hub PAT was not supplied by Jenkins credential dockerhub-credentials."
                            }

                            if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                                $env:PATH = "$dockerBinDir;$env:PATH"
                            }

                            $remoteVersion = "$registry/$repository`:$releaseVersion"
                            $remoteLatest = "$registry/$repository`:latest"

                            Write-Host "Docker Hub username: $dockerUsername"
                            Write-Host "Docker secret successfully bound."
                            Write-Host "Docker secret length: $($dockerPassword.Length)"

                            # Jenkins is running Windows PowerShell/.NET Framework on
                            # the Docker Desktop agent. Use ComputeHash() rather than
                            # SHA256.HashData(), which is unavailable on older .NET.
                            # The PAT itself is never written to the build log.
                            $sha256 = [System.Security.Cryptography.SHA256]::Create()
                            try {
                                $secretBytes = [System.Text.Encoding]::UTF8.GetBytes($dockerPassword)
                                $secretHash = $sha256.ComputeHash($secretBytes)
                                $secretFingerprint = [System.BitConverter]::ToString($secretHash).Replace('-', '').ToLowerInvariant()
                            }
                            finally {
                                $sha256.Dispose()
                            }

                            Write-Host "Docker credential SHA-256: $secretFingerprint"
                            Write-Host "Docker registry: $registry"
                            Write-Host "Docker repository: $repository"
                            Write-Host "Publishing release image: $remoteVersion"
                            Write-Host "Publishing latest image: $remoteLatest"

                            # Use an isolated Docker client configuration for Jenkins.
                            # This prevents Jenkins from using any interactive user's
                            # Docker credential helper or stale credentials.
                            $tempDockerConfig = Join-Path `
                                $env:TEMP `
                                "jenkins-docker-config-$env:BUILD_NUMBER"

                            New-Item `
                                -ItemType Directory `
                                -Force `
                                -Path $tempDockerConfig | Out-Null

                            $previousDockerConfig = $env:DOCKER_CONFIG
                            $env:DOCKER_CONFIG = $tempDockerConfig

                            try {
                                Write-Host "Preparing isolated Docker authentication config..."

                                # Do not invoke `docker login` here. The Jenkins agent
                                # previously returned HTTP 401 even though the same PAT
                                # was valid manually. Create the standard Docker auths
                                # entry directly in the temporary client configuration.
                                $authBytes = [System.Text.Encoding]::UTF8.GetBytes(
                                    "$dockerUsername`:$dockerPassword"
                                )
                                $authValue = [System.Convert]::ToBase64String($authBytes)

                                $dockerConfigPath = Join-Path $tempDockerConfig 'config.json'
                                $dockerConfigObject = @{
                                    auths = @{
                                        "https://index.docker.io/v1/" = @{
                                            auth = $authValue
                                        }
                                    }
                                }

                                $dockerConfigJson = $dockerConfigObject | ConvertTo-Json -Depth 5
                                $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                                [System.IO.File]::WriteAllText(
                                    $dockerConfigPath,
                                    $dockerConfigJson,
                                    $utf8NoBom
                                )

                                Write-Host "Docker authentication config prepared successfully."
                                Write-Host "Docker login command bypassed; push will authenticate using the temporary config."

                                & $dockerExe tag $releaseImage $remoteVersion
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to tag Docker release image for publishing."
                                }

                                & $dockerExe tag $releaseImage $remoteLatest
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to tag Docker latest image for publishing."
                                }

                                Write-Host "Pushing versioned image..."
                                & $dockerExe push $remoteVersion
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to push versioned Docker image: $remoteVersion"
                                }

                                Write-Host "Pushing latest image..."
                                & $dockerExe push $remoteLatest
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to push Docker latest image: $remoteLatest"
                                }

                                Write-Host "Docker image publication successful."
                            }
                            finally {
                                if ($previousDockerConfig) {
                                    $env:DOCKER_CONFIG = $previousDockerConfig
                                }
                                else {
                                    Remove-Item Env:DOCKER_CONFIG -ErrorAction SilentlyContinue
                                }

                                Remove-Item `
                                    -Recurse `
                                    -Force `
                                    -Path $tempDockerConfig `
                                    -ErrorAction SilentlyContinue
                            }
                            '''
                        }
                    }
                }
            }
        }


    }

    // ================================================================
    // POST BUILD
    // ================================================================

    post {

        success {
            echo 'Jenkins CI/CD pipeline completed successfully.'

            echo(
                'Build, unit tests, Gradle packaging, artifact archiving, ' +
                'legacy deployment or Docker continuous deployment, versioned image ' +
                'verification/publishing, and Selenium integration tests succeeded where applicable.'
            )
        }

        failure {
            echo(
                'Jenkins pipeline failed. ' +
                'Check the failed stage and console output.'
            )
        }

        always {
            archiveArtifacts(
                artifacts: 'build/dist/*.zip',
                allowEmptyArchive: true
            )
        }
    }
}
