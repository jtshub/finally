# Stop and remove the FinAlly container. The data volume is kept.
$Container = "finally"

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped FinAlly (data volume 'finally-data' kept)."
} else {
    Write-Host "FinAlly is not running."
}
