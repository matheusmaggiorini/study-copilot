Set-Location $PSScriptRoot
Write-Host "Ativando ambiente Python..." -ForegroundColor Cyan
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"
Write-Host "Subindo backend em http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --reload --port 8000
