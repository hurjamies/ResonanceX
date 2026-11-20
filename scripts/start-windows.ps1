# ResonanceX – Windows-käynnistin.
# Käynnistää paikallisen palvelimen (API + käyttöliittymä) ja avaa sovelluksen selaimeen.
# Sulje tämä ikkuna (tai paina Ctrl+C) pysäyttääksesi sovelluksen.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $Root 'services\api'
$Web = Join-Path $Root 'apps\web'
$Port = if ($env:RESONANCEX_PORT) { $env:RESONANCEX_PORT } else { '8000' }
$Url = "http://127.0.0.1:$Port"
$Host.UI.RawUI.WindowTitle = 'ResonanceX'

function Test-Running {
    try { Invoke-RestMethod "$Url/api/health" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

Write-Host ''
Write-Host '  RESONANCEX  ·  Personal Resonance Intelligence' -ForegroundColor Cyan
Write-Host ''

if (Test-Running) {
    Write-Host "  Sovellus on jo käynnissä – avataan $Url"
    Start-Process $Url
    Start-Sleep -Seconds 2
    exit 0
}

# Ensimmäinen käynnistys: asenna riippuvuudet, jos ne puuttuvat.
$Python = Join-Path $Api '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    Write-Host '  Asennetaan Python-riippuvuudet (vain ensimmäisellä kerralla)...' -ForegroundColor Yellow
    Push-Location $Api
    py -3.12 -m venv .venv
    & $Python -m pip install -q -r requirements-dev.txt
    Pop-Location
}
if (-not (Test-Path (Join-Path $Web 'dist\index.html'))) {
    Write-Host '  Rakennetaan käyttöliittymä (vain ensimmäisellä kerralla)...' -ForegroundColor Yellow
    Push-Location $Web
    if (-not (Test-Path 'node_modules')) { npm install --no-fund --no-audit }
    npm run build
    Pop-Location
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host '  VAROITUS: FFmpeg puuttuu – osa äänitiedostoista ei välttämättä avaudu.' -ForegroundColor Red
}

# Avaa selain heti, kun palvelin vastaa.
Start-Job -ArgumentList $Url -ScriptBlock {
    param($Url)
    for ($i = 0; $i -lt 120; $i++) {
        try { Invoke-RestMethod "$Url/api/health" -TimeoutSec 2 | Out-Null; Start-Process $Url; return } catch { Start-Sleep -Milliseconds 500 }
    }
} | Out-Null

Write-Host "  Käynnistetään palvelin osoitteeseen $Url"
Write-Host '  Sulje tämä ikkuna pysäyttääksesi sovelluksen.' -ForegroundColor DarkGray
Write-Host ''
Set-Location $Api
& (Join-Path $Api '.venv\Scripts\uvicorn.exe') app.main:app --host 127.0.0.1 --port $Port
