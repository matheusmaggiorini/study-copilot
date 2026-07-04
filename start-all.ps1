Write-Host "=== Study Copilot ===" -ForegroundColor Cyan
Write-Host "1) Backend: http://localhost:8000"
Write-Host "2) Frontend: http://localhost:3000"
Write-Host ""
Write-Host "Abrindo backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\backend\start-backend.ps1"
Start-Sleep -Seconds 2
Write-Host "Abrindo frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\frontend\start-frontend.ps1"
Write-Host ""
Write-Host "Pronto. Abra http://localhost:3000 e clique em Conectar Blackboard." -ForegroundColor Yellow
