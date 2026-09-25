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
        PYTHON_EXE  = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
        DEPLOY_ROOT = 'C:\\ProgramData\\Jenkins\\deploy\\leaveflow'
        NGINX_HOME  = 'C:\\nginx-1.30.5'
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {

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

        stage('Deploy') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $envName = $env:DEPLOY_ENV
                    $root = $env:DEPLOY_ROOT

                    if ($envName -eq "production") {
                        $port = 8000
                    }
                    elseif ($envName -eq "staging") {
                        $port = 8001
                    }
                    else {
                        throw "Unsupported deployment environment: $envName"
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

                    $ciPython = Join-Path $env:WORKSPACE ".ci-venv\\Scripts\\python.exe"

                    if (-not (Test-Path $ciPython)) {
                        throw "Jenkins Python environment not found: $ciPython"
                    }

                    Write-Host "Runtime Python: $ciPython"

                    $pidFile = Join-Path $environmentDir "current.pid"

                    if (Test-Path $pidFile) {

                        $oldPidText = Get-Content $pidFile

                        if ($oldPidText -and $oldPidText.Trim() -ne "") {

                            try {
                                $oldPid = [int]$oldPidText

                                $oldProcess = Get-Process `
                                    -Id $oldPid `
                                    -ErrorAction Stop

                                Write-Host "Stopping previous FastAPI process: PID $oldPid"

                                Stop-Process `
                                    -Id $oldPid `
                                    -Force `
                                    -ErrorAction Stop

                                Write-Host "Previous FastAPI process stopped."
                            }
                            catch {
                                Write-Host "Previous FastAPI process was not running."
                            }
                        }
                    }

                    $stdout = Join-Path $releaseDir "uvicorn.out.log"
                    $stderr = Join-Path $releaseDir "uvicorn.err.log"

                    Write-Host "Starting FastAPI application..."

                    $process = Start-Process `
                        -FilePath $ciPython `
                        -ArgumentList @(
                            "-m",
                            "uvicorn",
                            "app.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "$port",
                            "--proxy-headers"
                        ) `
                        -WorkingDirectory $releaseDir `
                        -RedirectStandardOutput $stdout `
                        -RedirectStandardError $stderr `
                        -PassThru

                    $process.Id | Set-Content $pidFile

                    Write-Host "FastAPI started with PID: $($process.Id)"

                    Start-Sleep -Seconds 3

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
                    Write-Host "PID         : $($process.Id)"
                    Write-Host "URL         : http://127.0.0.1:$port"
                    Write-Host "=========================================="
                '''
            }
        }

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

        stage('Nginx Setup') {
            when {
                expression {
                    return params.DEPLOY_ENV == 'production'
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $nginxHome = $env:NGINX_HOME
                    $nginxExe = Join-Path $nginxHome "nginx.exe"
                    $sourceConfig = Join-Path $env:WORKSPACE "nginx\\nginx.conf"
                    $targetConfig = Join-Path $nginxHome "conf\\nginx.conf"

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

                    $nginxProcesses = Get-Process nginx -ErrorAction SilentlyContinue

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

                        Start-Process `
                            -FilePath $nginxExe `
                            -WorkingDirectory $nginxHome

                        Start-Sleep -Seconds 3

                        $nginxProcesses = Get-Process nginx -ErrorAction SilentlyContinue

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
                    return params.DEPLOY_ENV == 'production'
                }
            }

            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"

                    $url = "http://localhost/openapi.json"

                    Write-Host "=========================================="
                    Write-Host "Nginx End-to-End Verification"
                    Write-Host "Testing: $url"
                    Write-Host "=========================================="

                    $healthy = $false

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
    }

    post {
        success {
            echo 'Jenkins Week 8 CI/CD pipeline completed successfully.'
            echo 'Build, tests, Gradle packaging, artifact archiving, FastAPI deployment, verification, and Nginx verification succeeded where applicable.'
        }

        failure {
            echo 'Jenkins Week 8 pipeline failed. Check the failed stage and console output.'
        }

        always {
            archiveArtifacts(
                artifacts: 'build/dist/*.zip,*.log',
                allowEmptyArchive: true
            )
        }
    }
}
