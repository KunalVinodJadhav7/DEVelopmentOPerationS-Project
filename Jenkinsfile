pipeline {
    agent any

    parameters {
        choice(
            name: 'DEPLOY_ENV',
            choices: ['staging', 'production'],
            description: 'Deployment environment'
        )
    }

    environment {
        PYTHON_EXE        = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
        DEPLOY_ROOT       = 'C:\\ProgramData\\Jenkins\\deploy\\leaveflow'
        NGINX_HOME        = 'C:\\nginx-1.30.5'
        SELENIUM_BASE_URL = 'http://localhost/dashboard'
        BASE_URL          = 'http://localhost'
        SECRET_KEY        = credentials('leaveflow-secret-key')
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
                }
            }
        }

        stage('Checkout') {
            steps {
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
        // Jenkins only creates/starts the task and verifies HTTP health.
        // ============================================================

        stage('Deploy FastAPI') {
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

                        Write-Host `
                            "Existing FastAPI task found. Stopping it..."

                        try {
                            Stop-ScheduledTask `
                                -TaskName $taskName `
                                -ErrorAction SilentlyContinue
                        }
                        catch {
                            Write-Host `
                                "Previous scheduled task was not running."
                        }

                        Start-Sleep -Seconds 2

                        Unregister-ScheduledTask `
                            -TaskName $taskName `
                            -Confirm:$false `
                            -ErrorAction SilentlyContinue

                        Start-Sleep -Seconds 1
                    }

                    # ------------------------------------------------
                    # Clean any process currently using deployment port
                    # ------------------------------------------------

                    Write-Host "Checking port $port..."

                    $existingConnections = Get-NetTCPConnection `
                        -LocalPort $port `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($existingConnections) {

                        $existingPid = $existingConnections |
                            Select-Object -First 1 -ExpandProperty OwningProcess

                        Write-Host `
                            "Port $port is currently owned by PID $existingPid"

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

                        $stillListening = Get-NetTCPConnection `
                            -LocalPort $port `
                            -State Listen `
                            -ErrorAction SilentlyContinue

                        if ($stillListening) {
                            throw `
                                "Port $port is still occupied after cleanup."
                        }
                    }

                    Write-Host "Port $port is available."

                    # ------------------------------------------------
                    # Runtime secret
                    # ------------------------------------------------

                    $secretFile = Join-Path `
                        $releaseDir `
                        "runtime-secret.txt"

                    Set-Content `
                        -Path $secretFile `
                        -Value $env:SECRET_KEY `
                        -Encoding UTF8

                    # ------------------------------------------------
                    # FastAPI logs
                    # ------------------------------------------------

                    $stdout = Join-Path `
                        $releaseDir `
                        "uvicorn.out.log"

                    $stderr = Join-Path `
                        $releaseDir `
                        "uvicorn.err.log"

                    # ------------------------------------------------
                    # Create scheduled-task launcher
                    # ------------------------------------------------

                    $launcher = Join-Path `
                        $releaseDir `
                        "launch_fastapi.ps1"

                    $launcherContent = @"
`$ErrorActionPreference = "Stop"

`$releaseDir = '$releaseDir'
`$python = '$ciPython'
`$secretFile = '$secretFile'
`$stdout = '$stdout'
`$stderr = '$stderr'

Set-Location -Path `$releaseDir

if (-not (Test-Path `$python)) {
    throw "Python executable not found: `$python"
}

if (-not (Test-Path `$secretFile)) {
    throw "Runtime secret file not found: `$secretFile"
}

`$env:SECRET_KEY = (Get-Content -LiteralPath `$secretFile -Raw).Trim()

`$env:PYTHONUNBUFFERED = "1"

& `$python -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port $port `
    --proxy-headers `
    *> `$stdout

if (`$LASTEXITCODE -ne 0) {
    exit `$LASTEXITCODE
}
"@

                    Set-Content `
                        -Path $launcher `
                        -Value $launcherContent `
                        -Encoding UTF8

                    Write-Host "FastAPI launcher created:"
                    Write-Host $launcher

                    # ------------------------------------------------
                    # Register Windows Scheduled Task
                    # ------------------------------------------------

                    $powershellExe = Join-Path `
                        $env:WINDIR `
                        "System32\\WindowsPowerShell\\v1.0\\powershell.exe"

                    if (-not (Test-Path $powershellExe)) {
                        throw `
                            "Windows PowerShell executable not found."
                    }

                    $action = New-ScheduledTaskAction `
                        -Execute $powershellExe `
                        -Argument `
                            "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""

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

                    Write-Host `
                        "Scheduled Task registered successfully."

                    # ------------------------------------------------
                    # Start task
                    # ------------------------------------------------

                    Write-Host "Starting FastAPI Scheduled Task..."

                    Start-ScheduledTask `
                        -TaskName $taskName

                    Write-Host `
                        "FastAPI task start command returned to Jenkins."

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

                                Write-Host `
                                    "FastAPI is healthy. HTTP 200"

                                break
                            }
                        }
                        catch {

                            Write-Host `
                                "Waiting for FastAPI... attempt $i/15"
                        }

                        Start-Sleep -Seconds 2
                    }

                    if (-not $healthy) {

                        Write-Host "=========================================="
                        Write-Host "FastAPI STDOUT"
                        Write-Host "=========================================="

                        if (Test-Path $stdout) {
                            Get-Content $stdout
                        }

                        Write-Host "=========================================="
                        Write-Host "FastAPI STDERR"
                        Write-Host "=========================================="

                        if (Test-Path $stderr) {
                            Get-Content $stderr
                        }

                        $taskInfo = `
                            Get-ScheduledTaskInfo `
                                -TaskName $taskName `
                                -ErrorAction SilentlyContinue

                        if ($taskInfo) {

                            Write-Host `
                                "Scheduled Task Last Run Result:"

                            Write-Host `
                                $taskInfo.LastTaskResult
                        }

                        throw "FastAPI health check failed."
                    }

                    # ------------------------------------------------
                    # Remove temporary secret after application startup
                    # ------------------------------------------------

                    Remove-Item `
                        -LiteralPath $secretFile `
                        -Force `
                        -ErrorAction SilentlyContinue

                    Write-Host `
                        "Temporary runtime secret removed."

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

                    Write-Host `
                        "Application is responding successfully."

                    Write-Host `
                        "HTTP Status: $($response.StatusCode)"
                '''
            }
        }

        // ============================================================
        // NGINX
        // ============================================================

        stage('Nginx Setup') {
            when {
                expression {
                    params.DEPLOY_ENV == 'production'
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
                        throw `
                            "Nginx executable not found: $nginxExe"
                    }

                    if (-not (Test-Path $sourceConfig)) {
                        throw `
                            "Repository Nginx configuration not found: $sourceConfig"
                    }

                    Copy-Item `
                        -Path $sourceConfig `
                        -Destination $targetConfig `
                        -Force

                    Write-Host `
                        "Nginx configuration copied."

                    Write-Host `
                        "Testing Nginx configuration..."

                    & $nginxExe `
                        -p "$nginxHome\\" `
                        -c "conf\\nginx.conf" `
                        -t

                    if ($LASTEXITCODE -ne 0) {
                        throw `
                            "Nginx configuration test failed."
                    }

                    Write-Host `
                        "Nginx configuration test successful."

                    $nginxProcesses = Get-Process `
                        nginx `
                        -ErrorAction SilentlyContinue

                    if ($nginxProcesses) {

                        Write-Host `
                            "Nginx is already running. Reloading..."

                        & $nginxExe `
                            -p "$nginxHome\\" `
                            -c "conf\\nginx.conf" `
                            -s reload

                        if ($LASTEXITCODE -ne 0) {
                            throw "Nginx reload failed."
                        }

                        Write-Host `
                            "Nginx reload successful."
                    }
                    else {

                        Write-Host `
                            "Nginx is not running. Starting Nginx..."

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

                        Write-Host `
                            "Nginx started successfully."
                    }
                '''
            }
        }

        stage('Nginx Verification') {
            when {
                expression {
                    params.DEPLOY_ENV == 'production'
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
                    Write-Host `
                        "NGINX + FASTAPI VERIFICATION SUCCESSFUL"
                    Write-Host `
                        "URL: http://localhost/openapi.json"
                    Write-Host "=========================================="
                '''
            }
        }

        // ============================================================
        // SELENIUM
        // ============================================================

        stage('Configure Selenium Target') {
            steps {
                script {

                    if (params.DEPLOY_ENV == 'production') {

                        env.SELENIUM_BASE_URL =
                            'http://localhost/dashboard'

                        env.BASE_URL =
                            'http://localhost'

                        echo `
                            'Selenium target: production through Nginx.'
                    }
                    else {

                        env.SELENIUM_BASE_URL =
                            'http://127.0.0.1:8001/dashboard'

                        env.BASE_URL =
                            'http://127.0.0.1:8001'

                        echo `
                            'Selenium target: staging through FastAPI.'
                    }
                }
            }
        }

        stage('Verify Selenium Target') {
            steps {
                echo `
                    "Checking ${SELENIUM_BASE_URL} before Selenium..."

                bat '''
                    curl.exe -f --max-time 20 "%SELENIUM_BASE_URL%"
                '''
            }
        }

        stage('Selenium Integration Tests') {
            steps {
                echo 'Running Week 10 Selenium integration tests...'

                bat '''
                    if not exist test-results mkdir test-results
                    if not exist selenium_tests\\artifacts mkdir selenium_tests\\artifacts

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

    // POST BUILD

    post {

        success {
            echo `
                'Jenkins Week 10 CI/CD pipeline completed successfully.'

            echo(
                'Build, unit tests, Gradle packaging, artifact archiving, ' +
                'FastAPI deployment, FastAPI verification, Nginx verification, ' +
                'and Selenium integration tests succeeded where applicable.'
            )
        }

        failure {
            echo(
                'Jenkins Week 10 pipeline failed. ' +
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
