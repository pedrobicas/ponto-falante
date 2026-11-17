# Informa ao backend publicado o endereco atual do Quick Tunnel da visao (muda a cada reinicio do cloudflared).
# Execute: powershell.exe -NoProfile -File scripts/visao/registrar-tunel.ps1 [-Repetir]
# O backend so aceita https://<nome>.trycloudflare.com, confere /health (modelo carregado) e um desafio HMAC antes de
# trocar o endereco. A chave nunca e impressa.
param([switch]$Repetir, [int]$IntervaloSegundos = 600)

. (Join-Path $PSScriptRoot 'comum.ps1')
Import-VisaoEnv
$mvp = if ($env:MVP_PUBLICO_URL) { $env:MVP_PUBLICO_URL.TrimEnd('/') } else { 'https://ponto-falante.onrender.com' }

function Get-TunelAtual {
    $log = Join-Path $script:GenAIRun 'cloudflared.err.log'
    if (-not (Test-Path -LiteralPath $log)) { return $null }
    $achados = Select-String -LiteralPath $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches
    if (-not $achados) { return $null }
    return ($achados | Select-Object -Last 1).Matches[-1].Value
}

function Register-Tunel {
    $url = Get-TunelAtual
    if (-not $url) { Write-Warning 'Endereco do tunel ainda nao apareceu em run/cloudflared.err.log.'; return $false }
    $corpo = @{ url = $url } | ConvertTo-Json -Compress
    try {
        # Acorda o Render (plano gratuito dorme apos 15 min) antes de registrar.
        Invoke-WebRequest -Uri "$mvp/actuator/health" -UseBasicParsing -TimeoutSec 90 | Out-Null
        $r = Invoke-RestMethod -Method Put -Uri "$mvp/api/visao/endereco" -Headers @{ 'X-API-Key' = $env:PF_VISAO_SERVICO_CHAVE } `
            -ContentType 'application/json; charset=utf-8' -Body $corpo -TimeoutSec 30
        Write-Host "$(Get-Date -Format 'HH:mm:ss') registrado no backend ($($r.origem)): $url"
        return $true
    } catch {
        $codigo = 0
        if ($null -ne $_.Exception.PSObject.Properties['Response'] -and $null -ne $_.Exception.Response) {
            $codigo = [int]$_.Exception.Response.StatusCode
        }
        $dica = switch ($codigo) {
            401 { 'chave recusada: a chave local e diferente da do Render (PF_VISAO_SERVICO_CHAVE ou GENAI_API_KEY)' }
            503 { 'chave do servico de visao nao configurada no Render' }
            404 { 'backend publicado ainda sem o endpoint /api/visao/endereco' }
            422 { 'o backend nao validou o tunel (/health com modelo carregado ou desafio de identidade)' }
            default { "falha HTTP $codigo" }
        }
        Write-Warning "$(Get-Date -Format 'HH:mm:ss') registro nao concluido: $dica."
        return $false
    }
}

do {
    $ok = Register-Tunel
    if (-not $Repetir) { if ($ok) { exit 0 } else { exit 1 } }
    # Renova periodicamente: um reinicio do Render apaga o registro em memoria.
    Start-Sleep -Seconds ($(if ($ok) { $IntervaloSegundos } else { 30 }))
} while ($true)
