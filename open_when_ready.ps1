param(
    [string]$ExpectedVersion = '2.2.2-cloud'
)

$ErrorActionPreference = 'SilentlyContinue'
$url = 'http://127.0.0.1:8080/api/health'
$openUrl = "http://127.0.0.1:8080/?v=$ExpectedVersion"

for ($i = 0; $i -lt 120; $i++) {
    try {
        $health = Invoke-RestMethod -Uri $url -TimeoutSec 1
        if ($health.service -eq 'Spectoom' -and [string]$health.version -eq $ExpectedVersion) {
            Start-Process $openUrl
            exit 0
        }
    } catch {}
    Start-Sleep -Milliseconds 250
}

Write-Host "Spectoom $ExpectedVersion ne repond pas sur le port 8080."
Write-Host 'Consultez la fenetre noire de run.bat pour lire le message d erreur.'
exit 1
