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
        // VALIDATION
        // ============================================================

        stage('Validate Parameters') {
            steps {
                script {
                    if (!params.DEPLOY_ENV?.trim()) {
                        error('DEPLOY_ENV must be selected.')
                    }

                    echo "Deployment environment: ${params.DEPLOY_ENV}"
                }
            }
        }

        // ============================================================
        // CHECKOUT
        // ============================================================

        stage('Checkout') {
            steps {
                deleteDir()

                git(
                    branch: 'main',
                    credentialsId: 'github-credentials',
                    url: 'https://github.com/KunalVinodJadhav7/DEVelopmentOPerationS-Project.git'
                )

                bat 'git log -1 --oneline'
            }
        }

        // ============================================================
        // PYTHON
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

        // ============================================================
        // UNIT TESTS
        // ============================================================

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
        // GRADLE BUILD
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

        // ============================================================
        // ARTIFACT VERIFICATION
        // ============================================================

        stage('Verify Artifact') {
            steps {
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
                '''
            }
        }

        // ============================================================
        // ARCHIVE ARTIFACT
        // ============================================================

        stage('Archive Artifact') {
            steps {
                archiveArtifacts(
                    artifacts: 'build/dist/*.zip',
                    fingerprint: true
                )
            }
        }

        // ============================================================
        // FASTAPI DEPLOYMENT
        // ============================================================

        stage('Deploy FastAPI') {
            options {
                timeout(
                    time: 5,
                    unit: 'MINUTES'
                )
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    # ------------------------------------------------
                    # Deployment configuration
                    # ------------------------------------------------

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

                    Write-Host "=========================================="
                    Write-Host "FastAPI Deployment"
                    Write-Host "Environment : $envName"
                    Write-Host "Port        : $port"
                    Write-Host "=========================================="

                    # ------------------------------------------------
                    # Paths
                    # ------------------------------------------------

                    $environmentDir = Join-Path `
                        $root `
                        $envName

                    $releaseDir = Join-Path `
                        $environmentDir `
                        $env:BUILD_NUMBER

                    $python = Join-Path `
                        $env:WORKSPACE `
                        ".ci-venv\\Scripts\\python.exe"

                    $stdout = Join-Path `
                        $releaseDir `
                        "uvicorn.out.log"

                    $stderr = Join-Path `
                        $releaseDir `
                        "uvicorn.err.log"

                    # ------------------------------------------------
                    # Validate Python
                    # ------------------------------------------------

                    if (-not (Test-Path $python)) {
                        throw "CI Python environment not found: $python"
                    }

                    # ------------------------------------------------
                    # Create release directory
                    # ------------------------------------------------

                    New-Item `
                        -ItemType Directory `
                        -Path $releaseDir `
                        -Force | Out-Null

                    Write-Host "Release directory:"
                    Write-Host $releaseDir

                    # ------------------------------------------------
                    # Find artifact
                    # ------------------------------------------------

                    $zip = Get-ChildItem `
                        -Path "build\\dist\\*.zip" |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1

                    if (-not $zip) {
                        throw "Application ZIP artifact not found."
                    }

                    Write-Host "Artifact:"
                    Write-Host $zip.FullName

                    # ------------------------------------------------
                    # Extract artifact
                    # ------------------------------------------------

                    Expand-Archive `
                        -LiteralPath $zip.FullName `
                        -DestinationPath $releaseDir `
                        -Force

                    # ------------------------------------------------
                    # Verify application
                    # ------------------------------------------------

                    $appFile = Join-Path `
                        $releaseDir `
                        "app\\main.py"

                    if (-not (Test-Path $appFile)) {
                        throw "FastAPI application not found: $appFile"
                    }

                    Write-Host "FastAPI application found."

                    # ------------------------------------------------
                    # Stop existing process
                    # ------------------------------------------------

                    Write-Host "Checking port $port..."

                    $connections = Get-NetTCPConnection `
                        -LocalPort $port `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($connections) {

                        $pids = $connections |
                            Select-Object -ExpandProperty OwningProcess -Unique

                        foreach ($pid in $pids) {

                            $process = Get-Process `
                                -Id $pid `
                                -ErrorAction SilentlyContinue

                            if ($process) {

                                Write-Host `
                                    "Port $port is used by PID $pid ($($process.ProcessName))."

                                if ($process.ProcessName -notin @(
                                    "python",
                                    "pythonw"
                                )) {
                                    throw `
                                        "Port $port is occupied by unexpected process: $($process.ProcessName)"
                                }

                                Write-Host `
                                    "Stopping FastAPI process PID $pid..."

                                Stop-Process `
                                    -Id $pid `
                                    -Force `
                                    -ErrorAction Stop
                            }
                        }

                        # Wait for port to become free.
                        $portFree = $false

                        for ($i = 1; $i -le 15; $i++) {

                            $listening = Get-NetTCPConnection `
                                -LocalPort $port `
                                -State Listen `
                                -ErrorAction SilentlyContinue

                            if (-not $listening) {
                                $portFree = $true
                                break
                            }

                            Start-Sleep -Seconds 1
                        }

                        if (-not $portFree) {
                            throw "Port $port did not become available."
                        }
                    }

                    Write-Host "Port $port is available."

                    # ------------------------------------------------
                    # Start FastAPI
                    # ------------------------------------------------

                    $command = @(
                        "`"$python`""
                        "-m"
                        "uvicorn"
                        "app.main:app"
                        "--host"
                        "127.0.0.1"
                        "--port"
                        "$port"
                        "--proxy-headers"
                    ) -join " "

                    Write-Host "Starting FastAPI..."

                    $originalCookie = $env:JENKINS_NODE_COOKIE

                    $env:JENKINS_NODE_COOKIE =
                        "leaveflow-$($env:BUILD_TAG)-$($env:BUILD_NUMBER)"

                    try {

                        $startCommand =
                            'start "" /b "{0}" -m uvicorn app.main:app ' +
                            '--host 127.0.0.1 ' +
                            '--port {1} ' +
                            '--proxy-headers ' +
                            '1>"{2}" 2>"{3}" <nul'

                        $startCommand = $startCommand -f `
                            $python,
                            $port,
                            $stdout,
                            $stderr

                        & $env:ComSpec /d /c $startCommand

                        if ($LASTEXITCODE -ne 0) {
                            throw "Failed to start FastAPI."
                        }

                    }
                    finally {
                        $env:JENKINS_NODE_COOKIE = $originalCookie
                    }

                    Write-Host "FastAPI process launched."

                    # ------------------------------------------------
                    # Health check
                    # ------------------------------------------------

                    $healthUrl =
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
                                    "FastAPI is healthy. HTTP $($response.StatusCode)"

                                break
                            }

                        }
                        catch {

                            Write-Host `
                                "Waiting for FastAPI... $i/15"
                        }

                        Start-Sleep -Seconds 2
                    }

                    # ------------------------------------------------
                    # Failure diagnostics
                    # ------------------------------------------------

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

                        throw "FastAPI health check failed."
                    }

                    # ------------------------------------------------
                    # Success
                    # ------------------------------------------------

                    Write-Host "=========================================="
                    Write-Host "FASTAPI DEPLOYMENT SUCCESSFUL"
                    Write-Host "Environment : $envName"
                    Write-Host "Release     : $releaseDir"
                    Write-Host "Port        : $port"
                    Write-Host "URL         : http://127.0.0.1:$port"
                    Write-Host "=========================================="
                '''
            }
        }

        // ============================================================
        // DEPLOYMENT VERIFICATION
        // ============================================================

        stage('Verify FastAPI') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $port = switch ($env:DEPLOY_ENV) {
                        "production" { 8000 }
                        "staging"    { 8001 }
                        default      { throw "Invalid deployment environment." }
                    }

                    $url =
                        "http://127.0.0.1:$port/openapi.json"

                    Write-Host "Verifying FastAPI:"
                    Write-Host $url

                    $response = Invoke-WebRequest `
                        -Uri $url `
                        -UseBasicParsing `
                        -TimeoutSec 10

                    if ($response.StatusCode -ne 200) {
                        throw "FastAPI verification failed."
                    }

                    Write-Host `
                        "FastAPI verification successful. HTTP $($response.StatusCode)"
                '''
            }
        }

        // ============================================================
        // NGINX PRODUCTION
        // ============================================================

        stage('Configure Nginx') {
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
                    Write-Host "=========================================="

                    if (-not (Test-Path $nginxExe)) {
                        throw "Nginx executable not found: $nginxExe"
                    }

                    if (-not (Test-Path $sourceConfig)) {
                        throw "Nginx configuration not found: $sourceConfig"
                    }

                    Copy-Item `
                        -Path $sourceConfig `
                        -Destination $targetConfig `
                        -Force

                    Write-Host "Nginx configuration copied."

                    # ------------------------------------------------
                    # Validate configuration
                    # ------------------------------------------------

                    & $nginxExe `
                        -p "$nginxHome\\" `
                        -c "conf\\nginx.conf" `
                        -t

                    if ($LASTEXITCODE -ne 0) {
                        throw "Nginx configuration test failed."
                    }

                    Write-Host "Nginx configuration is valid."

                    # ------------------------------------------------
                    # Start or reload Nginx
                    # ------------------------------------------------

                    $nginxProcesses = Get-Process `
                        -Name nginx `
                        -ErrorAction SilentlyContinue

                    if ($nginxProcesses) {

                        Write-Host "Nginx is running. Reloading..."

                        & $nginxExe `
                            -p "$nginxHome\\" `
                            -c "conf\\nginx.conf" `
                            -s reload

                        if ($LASTEXITCODE -ne 0) {
                            throw "Nginx reload failed."
                        }

                        Write-Host "Nginx reloaded successfully."

                    }
                    else {

                        Write-Host "Nginx is not running. Starting..."

                        $originalCookie =
                            $env:JENKINS_NODE_COOKIE

                        $env:JENKINS_NODE_COOKIE =
                            "leaveflow-nginx-$($env:BUILD_NUMBER)"

                        try {

                            $startCommand =
                                'start "" /b "{0}" ' +
                                '-p "{1}\\" ' +
                                '-c "conf\\nginx.conf" ' +
                                '>nul 2>&1 <nul'

                            $startCommand = $startCommand -f `
                                $nginxExe,
                                $nginxHome

                            & $env:ComSpec `
                                /d `
                                /c `
                                $startCommand

                            if ($LASTEXITCODE -ne 0) {
                                throw "Failed to start Nginx."
                            }

                        }
                        finally {
                            $env:JENKINS_NODE_COOKIE =
                                $originalCookie
                        }

                        Start-Sleep -Seconds 3

                        $nginxProcesses = Get-Process `
                            -Name nginx `
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

        stage('Verify Nginx') {
            when {
                expression {
                    params.DEPLOY_ENV == 'production'
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $url =
                        "http://localhost/openapi.json"

                    $healthy = $false

                    Write-Host "Testing Nginx reverse proxy:"
                    Write-Host $url

                    for ($i = 1; $i -le 10; $i++) {

                        try {

                            $response = Invoke-WebRequest `
                                -Uri $url `
                                -UseBasicParsing `
                                -TimeoutSec 5

                            if ($response.StatusCode -eq 200) {

                                $healthy = $true

                                Write-Host `
                                    "Nginx verification successful."

                                break
                            }

                        }
                        catch {

                            Write-Host `
                                "Waiting for Nginx... $i/10"
                        }

                        Start-Sleep -Seconds 2
                    }

                    if (-not $healthy) {
                        throw "Nginx reverse proxy verification failed."
                    }

                    Write-Host "Nginx + FastAPI are responding correctly."
                '''
            }
        }

        // ============================================================
        // SELENIUM CONFIGURATION
        // ============================================================

        stage('Configure Selenium') {
            steps {
                script {

                    if (params.DEPLOY_ENV == 'production') {

                        env.SELENIUM_BASE_URL =
                            'http://localhost/dashboard'

                        env.BASE_URL =
                            'http://localhost'

                        echo 'Selenium target: production/Nginx'

                    } else {

                        env.SELENIUM_BASE_URL =
                            'http://127.0.0.1:8001/dashboard'

                        env.BASE_URL =
                            'http://127.0.0.1:8001'

                        echo 'Selenium target: staging/FastAPI'
                    }
                }
            }
        }

        // ============================================================
        // SELENIUM TARGET CHECK
        // ============================================================

        stage('Verify Selenium Target') {
            steps {
                echo "Checking ${SELENIUM_BASE_URL}..."

                bat '''
                    curl.exe -f --max-time 20 "%SELENIUM_BASE_URL%"
                '''
            }
        }

        // ============================================================
        // SELENIUM TESTS
        // ============================================================

        stage('Selenium Tests') {
            steps {
                echo 'Running Selenium integration tests...'

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

    // ================================================================
    // POST BUILD
    // ================================================================

    post {

        success {
            echo '''
==========================================
PIPELINE SUCCESSFUL
==========================================
Build, tests, deployment and verification
completed successfully.
==========================================
'''
        }

        failure {
            echo '''
==========================================
PIPELINE FAILED
==========================================
Check the failed Jenkins stage and
console output for details.
==========================================
'''
        }

        always {
            archiveArtifacts(
                artifacts: 'build/dist/*.zip,*.log',
                allowEmptyArchive: true
            )
        }
    }
}
