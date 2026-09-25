$ErrorActionPreference = 'Stop'

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

$required = @('JENKINS_URL', 'JENKINS_JOB', 'JENKINS_USER', 'JENKINS_API_TOKEN')
foreach ($name in $required) {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
        throw "Set $name in .env before starting the application."
    }
}

$buildUrl = "$($env:JENKINS_URL.TrimEnd('/'))/job/$($env:JENKINS_JOB)/build"
$pair = "{0}:{1}" -f $env:JENKINS_USER, $env:JENKINS_API_TOKEN
$encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))

Write-Host "Triggering Jenkins build..."
Invoke-WebRequest -Method Post -Uri $buildUrl -Headers @{ Authorization = "Basic $encoded" } | Out-Null
Write-Host "Jenkins build triggered."

Write-Host "Starting the local Nginx/PostgreSQL deployment..."
docker compose up -d --build
if (-not $env:APP_PORT) { $env:APP_PORT = '8000' }
Write-Host "Application: http://localhost:$($env:APP_PORT)/dashboard"
