# Signum — seamless runner for Windows (PowerShell)
# Usage:  .\run.ps1 up        # build + start stack, then prime real data
#         .\run.ps1 ingest    # trigger real-data ingestion
#         .\run.ps1 signals   # show emerging skill pairs
#         .\run.ps1 bench     # bitmap-vs-btree benchmark
#         .\run.ps1 test      # backend tests
#         .\run.ps1 down      # stop stack

param([string]$Cmd = "up")
$ErrorActionPreference = "Stop"
$API = "http://localhost:8000/api/v1"
$KEY = "dev-api-key-change-in-production"

switch ($Cmd) {
  "up" {
    docker compose up --build -d
    Write-Host "Waiting for API..."
    for ($i = 0; $i -lt 10; $i++) {
      try { curl.exe -s "$API/health" | Out-Null; break } catch { Start-Sleep 2 }
    }
    Write-Host "Priming with real data (Remotive + Arbeitnow)..."
    curl.exe -s -X POST "$API/pipeline/run" -H "Authorization: Bearer $KEY"
  }
  "ingest" { curl.exe -s -X POST "$API/pipeline/run" -H "Authorization: Bearer $KEY" | python -m json.tool }
  "signals" { curl.exe -s "$API/signals?limit=20" | python -m json.tool }
  "status" { curl.exe -s "$API/pipeline/status" | python -m json.tool }
  "bench" { cd backend; python -m scripts.benchmark }
  "test" { cd backend; python -m pytest -q }
  "down" { docker compose down }
  default { Write-Host "Unknown command: $Cmd" }
}
