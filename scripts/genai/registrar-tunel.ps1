# Informa ao backend publicado o endereco atual do Quick Tunnel (muda a cada reinicio do cloudflared).
# Execute: powershell.exe -NoProfile -File scripts/genai/registrar-tunel.ps1 [-Repetir]
# O backend so aceita https://<nome>.trycloudflare.com (ou o host de GENAI_URL), confere /health antes de trocar
# e exige X-API-Key = GENAI_API_KEY. A chave nunca e impressa.
param([switch]$Repetir, [int]$IntervaloSegundos = 600)

. (Join-Path $PSScriptRoot 'comum.ps1')
Import-GenAIEnv
if (-not $env:GENAI_API_KEY) { throw 'Defina GENAI_API_KEY em scripts/genai/.env.local (a mesma do Render).' }
$mvp = if ($env:MVP_PUBLICO_URL) { $env:MVP_PUBLICO_URL.TrimEnd('/') } else { 'https://ponto-falante.onrender.com' }
$alvo = $null
if (-not [Uri]::TryCreate($mvp, [UriKind]::Absolute, [ref]$alvo) -or $alvo.Scheme -ne 'https' -or $alvo.UserInfo -or $alvo.Query) {
    throw 'MVP_PUBLICO_URL deve ser HTTPS, sem credenciais nem parametros.'
}

function Get-TunelAtual {
    $log = Join-Path $script:GenAIRun 'cloudflared.err.log'
    if (-not (Test-Path -LiteralPath $log)) { return $null }
    # cloudflared anuncia o endereco do Quick Tunnel no log de erro; o ultimo anuncio e o vigente.
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
        $r = Invoke-RestMethod -Method Put -Uri "$mvp/api/genai/endereco" -Headers @{ 'X-API-Key' = $env:GENAI_API_KEY } `
            -ContentType 'application/json; charset=utf-8' -Body $corpo -TimeoutSec 30
        Write-Host "$(Get-Date -Format 'HH:mm:ss') registrado no backend ($($r.origem)): $url"
        return $true
    } catch {
        $codigo = 0
        if ($null -ne $_.Exception.PSObject.Properties['Response'] -and $null -ne $_.Exception.Response) {
            $codigo = [int]$_.Exception.Response.StatusCode
        }
        $dica = switch ($codigo) {
            401 { 'chave recusada: GENAI_API_KEY local diferente da do Render' }
            503 { 'GENAI_API_KEY nao configurada no Render' }
            404 { 'backend publicado ainda sem o endpoint /api/genai/endereco' }
            422 { 'o backend nao validou o tunel (/health ou desafio de identidade; confira se GENAI_API_KEY e igual a do Render)' }
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
