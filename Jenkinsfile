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
        // FASTAPI DEPLOYMENT
        //
        // Windows Task Scheduler owns the long-running FastAPI process.
        // Jenkins creates the task, starts it, and verifies HTTP health.
        // ============================================================

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

                bat '''
                    if not exist "%DOCKER_EXE%" (
                        echo ERROR: Docker CLI not found at:
                        echo %DOCKER_EXE%
                        exit /b 1
                    )

                    echo Docker CLI:
                    echo %DOCKER_EXE%

                    "%DOCKER_EXE%" --version
                    "%DOCKER_EXE%" compose version
                    "%DOCKER_EXE%" info
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

                bat '''
                    echo ==========================================
                    echo Docker container status
                    echo ==========================================
                    "%DOCKER_EXE%" ps --filter "name=leaveflow-app" --filter "name=leaveflow-db" --filter "name=leaveflow-nginx"

                    echo.
                    echo ==========================================
                    echo Docker image verification
                    echo ==========================================
                    "%DOCKER_EXE%" image inspect leave-approval-system:latest

                    echo.
                    echo ==========================================
                    echo Application container health
                    echo ==========================================
                    "%DOCKER_EXE%" inspect leaveflow-app --format "{{.State.Status}}"
                    "%DOCKER_EXE%" inspect leaveflow-app --format "{{.State.Health.Status}}"

                    echo.
                    echo ==========================================
                    echo Database container health
                    echo ==========================================
                    "%DOCKER_EXE%" inspect leaveflow-db --format "{{.State.Status}}"
                    "%DOCKER_EXE%" inspect leaveflow-db --format "{{.State.Health.Status}}"

                    echo.
                    echo ==========================================
                    echo Nginx container status
                    echo ==========================================
                    "%DOCKER_EXE%" inspect leaveflow-nginx --format "{{.State.Status}}"

                    echo.
                    echo ==========================================
                    echo PostgreSQL readiness
                    echo ==========================================
                    "%DOCKER_EXE%" exec leaveflow-db pg_isready -U postgres -d leave_approval_db

                    echo.
                    echo ==========================================
                    echo Upload volume verification
                    echo ==========================================
                    "%DOCKER_EXE%" inspect leaveflow-app --format "{{json .Mounts}}"

                    echo.
                    echo ==========================================
                    echo Database volume verification
                    echo ==========================================
                    "%DOCKER_EXE%" inspect leaveflow-db --format "{{json .Mounts}}"

                    echo.
                    echo ==========================================
                    echo Public Docker health
                    echo ==========================================
                    curl.exe -f --max-time 20 "%DOCKER_BASE_URL%/health"

                    echo.
                    echo ==========================================
                    echo Public Docker OpenAPI verification
                    echo ==========================================
                    curl.exe -f --max-time 20 "%DOCKER_BASE_URL%/openapi.json" > NUL

                    echo.
                    echo ==========================================
                    echo Nginx to FastAPI verification
                    echo ==========================================
                    "%DOCKER_EXE%" exec leaveflow-nginx wget -qO- http://app:8000/openapi.json > NUL

                    echo.
                    echo ==========================================
                    echo Docker upload persistence verification
                    echo ==========================================
                    "%DOCKER_EXE%" exec leaveflow-app sh -c "test -f /app/uploads/docker-test.txt"
                    "%DOCKER_EXE%" exec leaveflow-app sh -c "grep -Fx 'week11-upload-test' /app/uploads/docker-test.txt"

                    echo.
                    echo ==========================================
                    echo Docker verification successful
                    echo ==========================================
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
                bat '''
                    echo ==========================================
                    echo Selenium Target Verification
                    echo ==========================================

                    if "%DEPLOY_MODE%"=="docker" (
                        set "TARGET_URL=%DOCKER_BASE_URL%/dashboard"
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

    }

    // ================================================================
    // POST BUILD
    // ================================================================

    post {

        success {
            echo 'Jenkins CI/CD pipeline completed successfully.'

            echo(
                'Build, unit tests, Gradle packaging, artifact archiving, ' +
                'legacy deployment or Docker verification, and Selenium integration ' +
                'tests succeeded where applicable.'
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
