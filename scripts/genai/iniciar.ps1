# Execute: powershell.exe -NoProfile -File scripts/genai/iniciar.ps1
param([switch]$SomenteLocal)

. (Join-Path $PSScriptRoot 'comum.ps1')
Import-GenAIEnv
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:PYTHONDONTWRITEBYTECODE = '1'
if ($SomenteLocal -and @(Get-Process -Name cloudflared -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'SomenteLocal solicitado, mas cloudflared ja esta ativo. Encerre o tunel antes de iniciar em modo local.'
}
if ($env:GENAI_AUTH_DESATIVADA -eq '1') {
    if (@(Get-Process -Name cloudflared -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'cloudflared ja esta ativo; encerre o tunel antes de iniciar com autenticacao desativada.'
    }
    Write-Warning 'GENAI_AUTH_DESATIVADA=1: somente desenvolvimento local. O tunel nao sera iniciado.'
} elseif (-not $env:GENAI_API_KEY) {
    throw 'Defina GENAI_API_KEY em scripts/genai/.env.local antes de iniciar.'
}

$python = Get-GenAIPython
# Nao altera um Ollama existente: exige que ele ja esteja restrito ao loopback.
$listeners = @(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
if (@($listeners | Where-Object { $_.LocalAddress -notin @('127.0.0.1', '::1') }).Count -gt 0) {
    throw 'Ollama esta exposto fora do loopback. Feche-o e reinicie com OLLAMA_HOST=127.0.0.1:11434.'
}
$ollama = Get-GenAIHttp 'http://127.0.0.1:11434/api/tags'
if ($ollama.Code -ne 200) {
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw 'Instale o Ollama e disponibilize ollama.exe no PATH.' }
    $startedOllama = Start-GenAIProcess -Name 'ollama' -Executable $command.Source -Arguments @('serve')
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        if ($startedOllama.HasExited) { throw 'Ollama encerrou; consulte run/ollama.err.log.' }
        $ollama = Get-GenAIHttp 'http://127.0.0.1:11434/api/tags'
        if ($ollama.Code -eq 200) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($ollama.Code -ne 200) { throw 'Ollama nao ficou disponivel em 30 s; consulte run/ollama.err.log.' }
} else { Write-Host 'Ollama ja responde em 127.0.0.1:11434.' }

$managedApi = Get-GenAIManagedProcess 'api'
if ($null -eq $managedApi) {
    $listeners = @(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) { throw 'Porta 8001 ocupada por processo nao gerenciado; libere-a antes de iniciar.' }
}
$env:PYTHONPATH = (Join-Path $script:GenAIRoot 'genai/src')
# Sem access log: nao gravar IP ou query string enviada por engano na URL.
$api = Start-GenAIProcess -Name 'api' -Executable $python -WorkingDirectory (Join-Path $script:GenAIRoot 'genai') `
    -Arguments @('-m', 'uvicorn', 'api.app:app', '--host', '127.0.0.1', '--port', '8001', '--workers', '1', '--no-access-log', '--no-proxy-headers')
$deadline = [DateTime]::UtcNow.AddSeconds(120)
do {
    if ($api.HasExited) { throw 'API encerrou; consulte run/api.err.log.' }
    $health = Get-GenAIHttp 'http://127.0.0.1:8001/health'
    if (Test-GenAIHealth $health) { break }
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)
if (-not (Test-GenAIHealth $health)) { throw 'API nao respondeu em 120 s; consulte run/api.err.log.' }
Write-Host "API: $($health.Body.status) em http://127.0.0.1:8001/health."

if ($SomenteLocal) {
    Write-Host 'Modo local: tunel nao iniciado. Configure GENAI_URL=http://127.0.0.1:8001 no Spring Boot local.'
    return
}
if ($env:GENAI_AUTH_DESATIVADA -eq '1') { return }
if (-not $env:CF_TUNNEL_NAME) {
    Write-Host 'API pronta para o Spring Boot local. Tunel opcional nao configurado; veja scripts/genai/README.md.'
    return
}
$command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
if ($null -eq $command) { throw 'Instale cloudflared e disponibilize cloudflared.exe no PATH.' }
$arguments = @('tunnel')
if ($env:CF_TUNNEL_CONFIG) {
    if (-not (Test-Path -LiteralPath $env:CF_TUNNEL_CONFIG -PathType Leaf)) { throw 'CF_TUNNEL_CONFIG nao encontrado.' }
    $arguments += @('--config', $env:CF_TUNNEL_CONFIG)
}
$arguments += @('run', $env:CF_TUNNEL_NAME)
$tunnel = Start-GenAIProcess -Name 'cloudflared' -Executable $command.Source -Arguments $arguments
Start-Sleep -Milliseconds 500
if ($tunnel.HasExited) { throw 'cloudflared encerrou; consulte run/cloudflared.err.log.' }
Write-Host 'Tunel iniciado. Use status.ps1 para verificar o processo e o /health publico.'
