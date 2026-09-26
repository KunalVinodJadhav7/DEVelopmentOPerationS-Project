# ============================================================
# Week 11 Docker Validation Script
# Jenkins-Based Employee Leave Approval System
# ============================================================

$ErrorActionPreference = "Stop"

$ComposeFile = "docker-compose.week11.yml"
$ContainerName = "leaveflow-week11"
$ImageName = "employee-leave-approval:week11"
$ApplicationUrl = "http://127.0.0.1:8002/"

Write-Host ""
Write-Host "============================================================"
Write-Host " WEEK 11 - DOCKER CONTAINERIZATION"
Write-Host "============================================================"
Write-Host ""

# ------------------------------------------------------------
# Verify Docker
# ------------------------------------------------------------

Write-Host "Checking Docker..."
docker --version

if ($LASTEXITCODE -ne 0) {
    throw "Docker is not available."
}

Write-Host ""
Write-Host "Checking Docker Compose..."
docker compose version

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose is not available."
}

# ------------------------------------------------------------
# Git status BEFORE Week 11 changes
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " GIT STATUS - BEFORE DOCKER CHANGES"
Write-Host "============================================================"

git status --short

# ------------------------------------------------------------
# Verify required Week 11 files
# ------------------------------------------------------------

$RequiredFiles = @(
    "Dockerfile.week11",
    "docker-compose.week11.yml"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Required file missing: $File"
    }

    Write-Host "Found: $File"
}

# ------------------------------------------------------------
# Build Docker image
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " BUILDING DOCKER IMAGE"
Write-Host "============================================================"

docker compose -f $ComposeFile build --no-cache

if ($LASTEXITCODE -ne 0) {
    throw "Docker image build failed."
}

# ------------------------------------------------------------
# Start container
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " STARTING DOCKER CONTAINER"
Write-Host "============================================================"

docker compose -f $ComposeFile up -d

if ($LASTEXITCODE -ne 0) {
    throw "Docker container failed to start."
}

# ------------------------------------------------------------
# Wait for container
# ------------------------------------------------------------

Write-Host ""
Write-Host "Waiting for Docker container to become healthy..."

$Healthy = $false

for ($i = 1; $i -le 30; $i++) {

    $Status = docker inspect `
        --format="{{.State.Health.Status}}" `
        $ContainerName 2>$null

    Write-Host "Health check $i/30 : $Status"

    if ($Status -eq "healthy") {
        $Healthy = $true
        break
    }

    Start-Sleep -Seconds 2
}

if (-not $Healthy) {
    Write-Host ""
    Write-Host "Container logs:"
    docker logs $ContainerName

    throw "Docker container did not become healthy."
}

# ------------------------------------------------------------
# HTTP verification
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " FASTAPI DOCKER VERIFICATION"
Write-Host "============================================================"

try {

    $Response = Invoke-WebRequest `
        -Uri $ApplicationUrl `
        -UseBasicParsing `
        -TimeoutSec 10

    Write-Host "HTTP Status : $($Response.StatusCode)"
    Write-Host "URL         : $ApplicationUrl"

}
catch {

    Write-Host ""
    Write-Host "Container logs:"
    docker logs $ContainerName

    throw "FastAPI Docker endpoint verification failed."
}

if ($Response.StatusCode -ne 200) {
    throw "Unexpected HTTP status: $($Response.StatusCode)"
}

Write-Host ""
Write-Host "FASTAPI DOCKER VERIFICATION SUCCESSFUL"

# ------------------------------------------------------------
# Docker information
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " DOCKER CONTAINER STATUS"
Write-Host "============================================================"

docker ps --filter "name=$ContainerName"

Write-Host ""
Write-Host "============================================================"
Write-Host " DOCKER IMAGE"
Write-Host "============================================================"

docker images $ImageName

# ------------------------------------------------------------
# Git status AFTER Week 11 changes
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================"
Write-Host " GIT STATUS - AFTER DOCKER CHANGES"
Write-Host "============================================================"

git status --short

Write-Host ""
Write-Host "============================================================"
Write-Host " WEEK 11 DOCKER VALIDATION COMPLETED"
Write-Host "============================================================"