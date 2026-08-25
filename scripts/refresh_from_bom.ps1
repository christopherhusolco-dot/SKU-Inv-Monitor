param(
    [string]$SourceDir = "E:\BOM",
    [string]$RepoDir = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$DataDir = Join-Path $RepoDir "data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

Push-Location $RepoDir
try {
    Write-Host "Building fast deploy snapshot from $SourceDir ..."
    python scripts\build_deploy_snapshot.py --source-dir $SourceDir --output-dir $DataDir
    if ($LASTEXITCODE -ne 0) { throw "Snapshot build failed with exit code $LASTEXITCODE" }

    Write-Host "Validating deploy snapshot ..."
    python scripts\validate_data.py --data-dir data
    if ($LASTEXITCODE -ne 0) { throw "Snapshot validation failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

Write-Host "Refresh complete. Raw BOM workbooks stayed in the centralized BOM folder."
Write-Host "Next: git add data/inventory_snapshot.csv.gz data/snapshot_metadata.json"
Write-Host "Then commit and push to refresh the Streamlit app."
