# Helper script to run Antigravity for Mobile/iPad access

$LocalIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -like '*Wi-Fi*' -or $_.InterfaceAlias -like '*Ethernet*' } | Select-Object -First 1).IPAddress

if (-not $LocalIP) {
    Write-Host "❌ No se pudo determinar la IP local. Asegúrate de estar conectado a una red." -ForegroundColor Red
    $LocalIP = "0.0.0.0"
}

Write-Host "`n"
Write-Host "***************************************************" -ForegroundColor Cyan
Write-Host "🚀 INICIANDO ANTIGRAVITY PARA ACCESO MÓVIL" -ForegroundColor Cyan
Write-Host "***************************************************" -ForegroundColor Cyan
Write-Host "`n"
Write-Host "📱 Acceso desde iPad/Móvil:" -ForegroundColor Yellow
Write-Host "🔗 http://$($LocalIP):8501" -ForegroundColor Green
Write-Host "`n"
Write-Host "🔑 Código de acceso: 1234" -ForegroundColor Yellow
Write-Host "`n"
Write-Host "***************************************************" -ForegroundColor Cyan
Write-Host "`n"

streamlit run app/main.py --server.address 0.0.0.0
