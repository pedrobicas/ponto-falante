# Sobe o servico de visao (visao/servico) em 127.0.0.1:8090 e, com -TunelRapido, publica-o por um Quick Tunnel da
# Cloudflare e registra o endereco no backend publicado (PUT /api/visao/endereco), como a GenAI.
# Execute: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/visao/iniciar.ps1 [-TunelRapido]
param([switch]$TunelRapido)

. (Join-Path $PSScriptRoot 'comum.ps1')
Import-VisaoEnv
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Get-VisaoPython
$porta = $script:VisaoPorta

if ($null -eq (Get-GenAIManagedProcess 'servico')) {
    $ocupada = @(Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue)
    if ($ocupada.Count -gt 0) { throw "Porta $porta ocupada por processo nao gerenciado; libere-a antes de iniciar." }
}
# Sem access log: nao gravar IPs. O servico nunca grava imagens.
$servico = Start-GenAIProcess -Name 'servico' -Executable $python -WorkingDirectory $script:VisaoDir `
    -Arguments @('-m', 'uvicorn', 'servico.app:app', '--host', '127.0.0.1', '--port', "$porta", '--workers', '1',
                 '--no-access-log', '--no-proxy-headers')
# Primeira execucao: o EasyOCR baixa ~100 MB de modelos. Depois, carregar leva ~10-30 s.
$prazo = [DateTime]::UtcNow.AddSeconds(600)
do {
    if ($servico.HasExited) { throw 'O servico de visao encerrou; consulte scripts/visao/run/servico.err.log.' }
    $saude = Get-GenAIHttp "http://127.0.0.1:$porta/health" -TimeoutSeconds 3
    if ($saude.Code -eq 200) { break }
    Start-Sleep -Seconds 2
} while ([DateTime]::UtcNow -lt $prazo)
if ($saude.Code -ne 200) { throw 'O modelo nao carregou em 10 min; consulte scripts/visao/run/servico.err.log.' }
Write-Host "Visao: modelo carregado ($($saude.Body.dispositivo)) em http://127.0.0.1:$porta."

if (-not $TunelRapido) {
    Write-Host "Modo local: use PF_VISAO_URL=http://127.0.0.1:$porta no Spring Boot local."
    return
}
$command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
if ($null -eq $command) { throw 'Instale cloudflared e disponibilize cloudflared.exe no PATH.' }
$log = Join-Path $script:GenAIRun 'cloudflared.err.log'
if ($null -eq (Get-GenAIManagedProcess 'cloudflared') -and (Test-Path -LiteralPath $log)) { Remove-Item -LiteralPath $log }
$tunel = Start-GenAIProcess -Name 'cloudflared' -Executable $command.Source `
    -Arguments @('tunnel', '--no-autoupdate', '--url', "http://127.0.0.1:$porta")
$prazo = [DateTime]::UtcNow.AddSeconds(45)
do {
    if ($tunel.HasExited) { throw 'cloudflared encerrou; consulte scripts/visao/run/cloudflared.err.log.' }
    Start-Sleep -Seconds 1
    $achado = if (Test-Path -LiteralPath $log) { Select-String -LiteralPath $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' } else { $null }
} while (-not $achado -and [DateTime]::UtcNow -lt $prazo)
if (-not $achado) { throw 'O endereco do tunel nao apareceu em 45 s; consulte scripts/visao/run/cloudflared.err.log.' }
$powershell = (Get-Process -Id $PID).Path
Start-GenAIProcess -Name 'registro' -Executable $powershell `
    -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'registrar-tunel.ps1'), '-Repetir') | Out-Null
Write-Host 'Tunel rapido ativo e registro automatico no backend iniciado (scripts/visao/run/registro.log).'
