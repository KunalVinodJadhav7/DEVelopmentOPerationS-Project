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
        // VALIDATION & CHECKOUT
        // ============================================================

        stage('Validate Deployment Parameter') {
            steps {
                script {
                    if (!params.DEPLOY_ENV?.trim()) {
                        error(
                            'DEPLOY_ENV was not provided. ' +
                            'Use Build with Parameters and select staging or production.'
                        )
                    }

                    echo "Selected deployment environment: ${params.DEPLOY_ENV}"
                }
            }
        }

        stage('GitHub Checkout') {
            steps {
                deleteDir()

                echo 'Checking out Employee Leave Approval System from GitHub...'

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
        // PYTHON SETUP & TESTING
        // ============================================================

        stage('Python Setup') {
            steps {
                echo 'Creating Python CI environment...'

                bat '''
                    "%PYTHON_EXE%" -m venv .ci-venv

                    .ci-venv\\Scripts\\python.exe -m pip install --upgrade pip

                    .ci-venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running Python unit tests...'

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
                echo 'Running Gradle build and packaging...'

                bat '''
                    where gradle
                    gradle --version

                    gradle --no-daemon clean build "-PappVersion=1.0.%BUILD_NUMBER%"
                '''
            }
        }

        stage('Verify Artifact') {
            steps {
                echo 'Verifying generated ZIP artifact...'

                bat '''
                    if not exist build\\dist (
                        echo ERROR: build\\dist directory was not created.
                        exit /b 1
                    )

                    dir build\\dist

                    if not exist build\\dist\\*.zip (
                        echo ERROR: ZIP artifact was not created.
                        exit /b 1
                    )

                    echo ZIP artifact successfully created.
                '''
            }
        }

        stage('Archive ZIP Artifact') {
            steps {
                echo 'Archiving ZIP artifact in Jenkins...'

                archiveArtifacts(
                    artifacts: 'build/dist/*.zip',
                    fingerprint: true
                )
            }
        }

        // ============================================================
        // FASTAPI DEPLOYMENT
        // ============================================================

        stage('Deploy') {
            options {
                timeout(
                    time: 5,
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

                    Write-Host "=========================================="
                    Write-Host "Starting FastAPI deployment"
                    Write-Host "Environment : $envName"
                    Write-Host "Port        : $port"
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

                    Write-Host "Release directory: $releaseDir"

                    $zip = Get-ChildItem "build\\dist\\*.zip" |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1

                    if (-not $zip) {
                        throw "Application ZIP was not found."
                    }

                    Write-Host "Deploying artifact: $($zip.FullName)"

                    Expand-Archive `
                        -LiteralPath $zip.FullName `
                        -DestinationPath $releaseDir `
                        -Force

                    $appFile = Join-Path $releaseDir "app\\main.py"

                    if (-not (Test-Path $appFile)) {
                        throw "FastAPI application not found: $appFile"
                    }

                    Write-Host "FastAPI application found: $appFile"

                    $ciPython = Join-Path `
                        $env:WORKSPACE `
                        ".ci-venv\\Scripts\\python.exe"

                    if (-not (Test-Path $ciPython)) {
                        throw "Jenkins Python environment not found: $ciPython"
                    }

                    Write-Host "Runtime Python: $ciPython"

                    # ------------------------------------------------
                    # Stop existing FastAPI process
                    # ------------------------------------------------

                    Write-Host "Checking whether port $port is already in use..."

                    $existingConnections = Get-NetTCPConnection `
                        -LocalPort $port `
                        -State Listen `
                        -ErrorAction SilentlyContinue

                    if ($existingConnections) {

                        $existingPid = $existingConnections |
                            Select-Object -First 1 -ExpandProperty OwningProcess

                        Write-Host "Port $port is owned by PID $existingPid"

                        try {
                            Get-Process `
                                -Id $existingPid `
                                -ErrorAction Stop | Out-Null

                            Write-Host "Stopping existing process: PID $existingPid"

                            Stop-Process `
                                -Id $existingPid `
                                -Force `
                                -ErrorAction Stop

                            Start-Sleep -Seconds 2

                            Write-Host "Existing process stopped."
                        }
                        catch {
                            throw "Port $port is still occupied. Deployment cannot continue."
                        }
                    }
                    else {
                        Write-Host "Port $port is available."
                    }

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
                    # Start FastAPI detached from Jenkins
                    # ------------------------------------------------

                    Write-Host "Starting FastAPI application..."

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
                            $ciPython,
                            $port,
                            $stdout,
                            $stderr

                        Write-Host "Launching detached FastAPI process..."

                        & $env:ComSpec /d /c $startCommand

                        if ($LASTEXITCODE -ne 0) {
                            throw "Windows failed to launch the FastAPI background process."
                        }
                    }
                    finally {
                        $env:JENKINS_NODE_COOKIE = $originalCookie
                    }

                    Write-Host "FastAPI launch command returned successfully."

                    # ------------------------------------------------
                    # FastAPI health check
                    # ------------------------------------------------

                    $healthUrl = "http://127.0.0.1:$port/openapi.json"
                    $healthy = $false

                    Write-Host "Checking FastAPI health: $healthUrl"

                    for ($i = 1; $i -le 15; $i++) {
                        try {
                            $response = Invoke-WebRequest `
                                -Uri $healthUrl `
                                -UseBasicParsing `
                                -TimeoutSec 5

                            if ($response.StatusCode -eq 200) {
                                $healthy = $true

                                Write-Host "FastAPI health check successful."
                                Write-Host "HTTP Status: $($response.StatusCode)"

                                break
                            }
                        }
                        catch {
                            Write-Host "Waiting for FastAPI... attempt $i/15"
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

                        throw "FastAPI health check failed."
                    }

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

                    $url = "http://127.0.0.1:$port/openapi.json"

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
                        throw "Nginx executable not found: $nginxExe"
                    }

                    if (-not (Test-Path $sourceConfig)) {
                        throw "Repository Nginx configuration not found: $sourceConfig"
                    }

                    Copy-Item `
                        -Path $sourceConfig `
                        -Destination $targetConfig `
                        -Force

                    Write-Host "Nginx configuration copied to:"
                    Write-Host $targetConfig

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

                        Write-Host "Nginx is already running. Reloading configuration..."

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

                        $originalCookie = $env:JENKINS_NODE_COOKIE

                        $env:JENKINS_NODE_COOKIE =
                            "leaveflow-nginx-$($env:BUILD_NUMBER)"

                        try {
                            $nginxStartCommand =
                                'start "" /b "{0}" ' +
                                '-p "{1}\\" ' +
                                '-c "conf\\nginx.conf" ' +
                                '>nul 2>&1 <nul'

                            $nginxStartCommand = $nginxStartCommand -f `
                                $nginxExe,
                                $nginxHome

                            & $env:ComSpec `
                                /d `
                                /c `
                                $nginxStartCommand

                            if ($LASTEXITCODE -ne 0) {
                                throw "Windows failed to launch Nginx."
                            }
                        }
                        finally {
                            $env:JENKINS_NODE_COOKIE = $originalCookie
                        }

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

                                Write-Host "Nginx reverse proxy verification successful."
                                Write-Host "HTTP Status: $($response.StatusCode)"

                                break
                            }
                        }
                        catch {
                            Write-Host "Waiting for Nginx... attempt $i/10"
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
        // SELENIUM
        // ============================================================

        stage('Configure Selenium Target') {
            steps {
                script {
                    if (params.DEPLOY_ENV == 'production') {
                        env.SELENIUM_BASE_URL = 'http://localhost/dashboard'
                        env.BASE_URL = 'http://localhost'

                        echo 'Selenium target configured for production through Nginx.'
                    }
                    else {
                        env.SELENIUM_BASE_URL =
                            'http://127.0.0.1:8001/dashboard'

                        env.BASE_URL = 'http://127.0.0.1:8001'

                        echo 'Selenium target configured for staging through FastAPI.'
                    }
                }
            }
        }

        stage('Verify Selenium Target') {
            steps {
                echo "Checking ${SELENIUM_BASE_URL} before Selenium..."

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

    // ================================================================
    // POST BUILD
    // ================================================================

    post {
        success {
            echo 'Jenkins Week 10 CI/CD pipeline completed successfully.'

            echo(
                'Build, unit tests, deployment, Selenium integration tests, ' +
                'artifact archiving, FastAPI verification, and Nginx verification ' +
                'succeeded where applicable.'
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
                artifacts: 'build/dist/*.zip,*.log',
                allowEmptyArchive: true
            )
        }
    }
}
