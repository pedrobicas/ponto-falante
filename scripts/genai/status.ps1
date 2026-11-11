. (Join-Path $PSScriptRoot 'comum.ps1')
Import-GenAIEnv
$ollama = Get-GenAIHttp 'http://127.0.0.1:11434/api/tags'
if ($ollama.Code -eq 200) { Write-Host 'Ollama: disponivel em 127.0.0.1:11434.' }
else { Write-Warning 'Ollama: indisponivel.' }

function Show-GenAIHealth {
    param([string]$Label, [string]$Url)
    $result = Get-GenAIHttp $Url -TimeoutSeconds 5
    if (Test-GenAIHealth $result) {
        Write-Host "$Label`: HTTP $($result.Code), status=$($result.Body.status), llm_ok=$($result.Body.llm_ok), indice_ok=$($result.Body.indice_ok)."
    } else { Write-Warning "$Label`: indisponivel ou resposta invalida (HTTP $($result.Code))." }
}
Show-GenAIHealth 'API local' 'http://127.0.0.1:8001/health'
$tunnel = Get-GenAIManagedProcess 'cloudflared'
if ($null -ne $tunnel) { Write-Host "cloudflared: ativo (PID $($tunnel.Id))." }
elseif (@(Get-Process -Name cloudflared -ErrorAction SilentlyContinue).Count -gt 0) {
    Write-Host 'cloudflared: processo externo ativo, nao gerenciado por este worktree.'
} else { Write-Warning 'cloudflared: nenhum processo ativo.' }
if ($env:GENAI_PUBLIC_URL) {
    $url = $null
    if (-not [Uri]::TryCreate($env:GENAI_PUBLIC_URL, [UriKind]::Absolute, [ref]$url) -or
        $url.Scheme -notin @('http', 'https') -or $url.UserInfo -or $url.Query -or $url.Fragment) {
        throw 'GENAI_PUBLIC_URL deve ser uma URL HTTP(S) sem credenciais, query ou fragmento.'
    }
    Show-GenAIHealth 'API publica' ($env:GENAI_PUBLIC_URL.TrimEnd('/') + '/health')
} else { Write-Host 'API publica: configure GENAI_PUBLIC_URL em .env.local para verificar.' }
