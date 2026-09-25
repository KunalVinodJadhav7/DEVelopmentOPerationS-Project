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
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {

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

                    .ci-venv\\Scripts\\python.exe -m pytest tests -q --junitxml=build\\test-results\\pytest-jenkins.xml
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
                    Write-Host "Deployment environment: $envName"
                    Write-Host "Application port: $port"
                    Write-Host "=========================================="

                    $environmentDir = Join-Path $root $envName
                    $releaseDir = Join-Path $environmentDir $env:BUILD_NUMBER

                    New-Item `
                        -ItemType Directory `
                        -Force `
                        -Path $releaseDir | Out-Null

                    Write-Host "Release directory: $releaseDir"

                    $zip = Get-ChildItem "build\\dist\\*.zip" |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1

                    if (-not $zip) {
                        throw "Deployment ZIP was not found."
                    }

                    Write-Host "Deploying artifact: $($zip.FullName)"

                    Expand-Archive `
                        -LiteralPath $zip.FullName `
                        -DestinationPath $releaseDir `
                        -Force

                    $python = $env:PYTHON_EXE
                    $venv = Join-Path $releaseDir ".venv"

                    Write-Host "Creating deployment virtual environment..."

                    & $python -m venv $venv

                    $venvPython = Join-Path $venv "Scripts\\python.exe"
                    $requirements = Join-Path $releaseDir "requirements.txt"

                    if (-not (Test-Path $requirements)) {
                        throw "requirements.txt not found in deployed artifact."
                    }

                    Write-Host "Installing deployment dependencies..."

                    & $venvPython -m pip install --upgrade pip
                    & $venvPython -m pip install -r $requirements

                    $pidFile = Join-Path $environmentDir "current.pid"

                    if (Test-Path $pidFile) {
                        $oldPid = Get-Content $pidFile

                        if ($oldPid) {
                            try {
                                Stop-Process `
                                    -Id ([int]$oldPid) `
                                    -Force `
                                    -ErrorAction Stop

                                Write-Host "Stopped previous $envName process: $oldPid"
                            }
                            catch {
                                Write-Host "Previous $envName process was not running."
                            }
                        }
                    }

                    $stdout = Join-Path $releaseDir "uvicorn.out.log"
                    $stderr = Join-Path $releaseDir "uvicorn.err.log"

                    Write-Host "Starting FastAPI application..."

                    $process = Start-Process `
                            -FilePath $venvPython `
                            -ArgumentList @(
                                "-m",
                                "uvicorn",
                                "app.main:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                $port,
                                "--proxy-headers"
                            ) `
                            -WorkingDirectory $releaseDir `
                            -RedirectStandardOutput $stdout `
                            -RedirectStandardError $stderr `
                            -PassThru

                    $process.Id | Set-Content $pidFile

                    Write-Host "FastAPI PID: $($process.Id)"

                    Start-Sleep -Seconds 3

                    $healthUrl = "http://127.0.0.1:$port/openapi.json"
                    $healthy = $false

                    Write-Host "Checking FastAPI health: $healthUrl"

                    for ($i = 1; $i -le 12; $i++) {
                        try {
                            $response = Invoke-WebRequest `
                                -Uri $healthUrl `
                                -UseBasicParsing `
                                -TimeoutSec 5

                            if ($response.StatusCode -eq 200) {
                                $healthy = $true
                                Write-Host "Health check successful."
                                break
                            }
                        }
                        catch {
                            Write-Host "Waiting for FastAPI... attempt $i/12"
                        }

                        Start-Sleep -Seconds 2
                    }

                    if (-not $healthy) {
                        Write-Host "=========================================="
                        Write-Host "FastAPI stdout"
                        Write-Host "=========================================="

                        if (Test-Path $stdout) {
                            Get-Content $stdout
                        }

                        Write-Host "=========================================="
                        Write-Host "FastAPI stderr"
                        Write-Host "=========================================="

                        if (Test-Path $stderr) {
                            Get-Content $stderr
                        }

                        throw "FastAPI health check failed."
                    }

                    Write-Host "=========================================="
                    Write-Host "FastAPI deployment successful."
                    Write-Host "Environment : $envName"
                    Write-Host "Release     : $releaseDir"
                    Write-Host "Port        : $port"
                    Write-Host "URL         : http://127.0.0.1:$port"
                    Write-Host "=========================================="
                '''
            }
        }
    }

    post {
        success {
            echo 'Jenkins CI/CD pipeline completed successfully.'
            echo 'Checkout, Python setup, tests, Gradle packaging, artifact archiving, deployment, and health check succeeded.'
        }

        failure {
            echo 'Jenkins CI/CD pipeline failed. Check the failed stage in the Jenkins console output.'
        }
    }
}
