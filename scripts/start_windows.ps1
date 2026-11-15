# Start the FinAlly container. Usage: .\scripts\start_windows.ps1 [-Build] [-Open]
param([switch]$Build, [switch]$Open)
$ErrorActionPreference = "Stop"

$Image = "finally"
$Container = "finally"
$Volume = "finally-data"
$Port = 8000
$Url = "http://localhost:$Port"

Set-Location (Join-Path $PSScriptRoot "..")

docker image inspect $Image *> $null
if ($Build -or $LASTEXITCODE -ne 0) {
    Write-Host "Building image '$Image'..."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
}

docker rm -f $Container *> $null

$EnvArgs = @()
if (Test-Path ".env") {
    $EnvArgs = @("--env-file", ".env")
} else {
    Write-Warning ".env not found; starting without it (LLM chat needs OPENROUTER_API_KEY)."
}

docker run -d --name $Container -v "${Volume}:/app/db" -p "${Port}:8000" @EnvArgs $Image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

Write-Host "FinAlly is running at $Url"
if ($Open) { Start-Process $Url }
