$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d postgres s3
if ($LASTEXITCODE -ne 0) { throw "Impossible de démarrer PostgreSQL/S3" }
docker compose build pipeline
if ($LASTEXITCODE -ne 0) { throw "Échec construction image" }
docker compose run --rm pipeline demo --source s3
if ($LASTEXITCODE -ne 0) { throw "Échec pipeline" }
docker compose run --rm pipeline inspect
exit $LASTEXITCODE
