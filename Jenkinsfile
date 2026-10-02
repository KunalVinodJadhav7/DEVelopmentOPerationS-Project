pipeline {
    agent any

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
        // WEEK 12 - DOCKER RELEASE METADATA
        // ============================================================

        stage('Prepare Docker Release Metadata') {
            when {
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                script {
                    def releaseVersion = "1.0.${env.BUILD_NUMBER}"
                    env.LEAVEFLOW_APP_VERSION = releaseVersion
                    env.LEAVEFLOW_APP_IMAGE = "leave-approval-system:${releaseVersion}"
                    env.LEAVEFLOW_APP_LATEST = 'leave-approval-system:latest'

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
Docker Version: ${env.LEAVEFLOW_APP_IMAGE}
Docker Latest Tag: ${env.LEAVEFLOW_APP_LATEST}
Docker Registry Publishing: ${params.PUBLISH_DOCKER_IMAGE}
""".trim() + "\r\n"

                    writeFile(
                        file: 'build/docker-release-manifest.txt',
                        text: manifest
                    )

                    echo "Week 12 release: ${env.LEAVEFLOW_APP_IMAGE}"
                    echo "Source commit: ${commit}"

                    archiveArtifacts(
                        artifacts: 'build/docker-release-manifest.txt',
                        fingerprint: true
                    )
                }
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

        stage('Docker Environment Verification') {
            when {
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
            when {
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
                        $env:LEAVEFLOW_APP_LATEST,
                        $env:LEAVEFLOW_APP_IMAGE,
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
            when {
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
                    $secretDir = Join-Path $env:WORKSPACE 'secrets'
                    $secretFile = Join-Path $secretDir 'leaveflow_secret_key.txt'

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

                    & $dockerExe compose -f $composeFile config | Out-Null
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
                    & $dockerExe compose -f $composeFile build --no-cache
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
                    & $dockerExe compose -f $composeFile up -d --remove-orphans --force-recreate
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
            when {
                expression {
                    params.DEPLOY_MODE == 'docker'
                }
            }

            steps {
                echo 'Verifying the Week 11 Docker deployment...'

                powershell '''
                    $ErrorActionPreference = "Stop"

                    $dockerExe = $env:DOCKER_EXE
                    $dockerBinDir = $env:DOCKER_BIN_DIR
                    $composeFile = Join-Path $env:WORKSPACE 'docker-compose.yml'

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
                    Invoke-DockerChecked @('image','inspect','leave-approval-system:latest') 'Application image was not found.'

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
                    if ($deployedImage -ne $env:LEAVEFLOW_APP_IMAGE) {
                        throw "Docker deployment is not running the expected release image. Expected=$env:LEAVEFLOW_APP_IMAGE Actual=$deployedImage"
                    }
                    Write-Host "Deployed release image: $deployedImage"

                    $imageVersion = (& $dockerExe image inspect $env:LEAVEFLOW_APP_IMAGE --format '{{index .Config.Labels "org.opencontainers.image.version"}}').Trim()
                    if ($imageVersion -ne $env:LEAVEFLOW_APP_VERSION) {
                        throw "Docker image version label mismatch. Expected=$env:LEAVEFLOW_APP_VERSION Actual=$imageVersion"
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
            when {
                allOf {
                    expression { params.DEPLOY_MODE == 'docker' }
                    expression { params.PUBLISH_DOCKER_IMAGE }
                }
            }

            steps {
                script {
                    if (!params.DOCKERHUB_REPOSITORY?.trim()) {
                        error(
                            'DOCKERHUB_REPOSITORY is required when PUBLISH_DOCKER_IMAGE is enabled. ' +
                            'Example: username/employee-leave-approval-system'
                        )
                    }

                    withCredentials([
                        usernamePassword(
                            credentialsId: 'dockerhub-credentials',
                            usernameVariable: 'DOCKER_USERNAME',
                            passwordVariable: 'DOCKER_PASSWORD'
                        )
                    ]) {
                        powershell '''
                            $ErrorActionPreference = "Stop"

                            $dockerExe = $env:DOCKER_EXE
                            $dockerBinDir = $env:DOCKER_BIN_DIR
                            $registry = $env:DOCKER_REGISTRY.Trim()
                            $repository = $env:DOCKERHUB_REPOSITORY.Trim()

                            if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $dockerBinDir })) {
                                $env:PATH = "$dockerBinDir;$env:PATH"
                            }

                            $remoteVersion = "$registry/$repository`:$env:LEAVEFLOW_APP_VERSION"
                            $remoteLatest = "$registry/$repository`:latest"

                            Write-Host "Publishing release image: $remoteVersion"
                            Write-Host "Publishing latest image: $remoteLatest"

                            $env:DOCKER_PASSWORD | & $dockerExe login $registry --username $env:DOCKER_USERNAME --password-stdin
                            if ($LASTEXITCODE -ne 0) {
                                throw "Docker registry login failed."
                            }

                            try {
                                & $dockerExe tag $env:LEAVEFLOW_APP_IMAGE $remoteVersion
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to tag Docker release image for publishing."
                                }

                                & $dockerExe tag $env:LEAVEFLOW_APP_IMAGE $remoteLatest
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to tag Docker latest image for publishing."
                                }

                                & $dockerExe push $remoteVersion
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to push versioned Docker image: $remoteVersion"
                                }

                                & $dockerExe push $remoteLatest
                                if ($LASTEXITCODE -ne 0) {
                                    throw "Failed to push Docker latest image: $remoteLatest"
                                }

                                Write-Host "Docker image publication successful."
                            }
                            finally {
                                & $dockerExe logout $registry | Out-Null
                            }
                        '''
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