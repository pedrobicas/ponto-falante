# Guarda do agendamento do RPA. O cron do GitHub Actions e "melhor esforco": em 13/11 so 3 das 8 coletas previstas
# rodaram (17 consultas de 48) e o rpa-diario chegou a atrasar 8 h. Enquanto o PC da GenAI estiver ligado, este
# script confere a ultima execucao e dispara o MESMO workflow pelo gh (workflow_dispatch) quando o cron falhou.
# Nao coleta nada localmente, nao usa segredos do RPA e nao altera dados: so pede ao GitHub a execucao que faltou.
#
#   powershell -ExecutionPolicy Bypass -File scripts/genai/garantir-rpa.ps1            # uma verificacao
#   powershell -ExecutionPolicy Bypass -File scripts/genai/garantir-rpa.ps1 -Repetir   # a cada 15 min
param([switch]$Repetir, [int]$IntervaloSegundos = 900, [int]$ColetaMaxMinutos = 125, [string]$Ref = 'main')
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-Guarda([string]$Texto) { Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Texto" }

function Get-UltimaExecucao([string]$Workflow) {
    $json = & gh run list --workflow $Workflow --branch $Ref --limit 1 --json createdAt,status 2>$null
    if ($LASTEXITCODE -ne 0) { throw "gh run list falhou para $Workflow (gh instalado e autenticado?)" }
    $lista = @($json | ConvertFrom-Json)
    if ($lista.Count -eq 0) { return $null }
    return $lista[0]
}

function Invoke-Disparo([string]$Workflow, [string]$Motivo) {
    & gh workflow run $Workflow --ref $Ref 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Guarda "disparado $Workflow ($Motivo)" } else { Write-Guarda "AVISO falha ao disparar $Workflow" }
}

function Test-Agendamento {
    $agora = [DateTime]::UtcNow
    # Coleta: janela de 07h a 21h em Sao Paulo (10h-00h UTC), mesma do cron (0,10,12,...,22 UTC).
    $naJanela = $agora.Hour -ge 10 -or $agora.Hour -eq 0
    $coleta = Get-UltimaExecucao 'rpa-coleta.yml'
    if ($naJanela) {
        $idade = if ($null -eq $coleta) { [double]::MaxValue } else { ($agora - ([DateTime]$coleta.createdAt).ToUniversalTime()).TotalMinutes }
        $emAndamento = $null -ne $coleta -and $coleta.status -ne 'completed'
        if (-not $emAndamento -and $idade -gt $ColetaMaxMinutos) {
            Invoke-Disparo 'rpa-coleta.yml' ("ultima coleta ha {0:N0} min" -f [math]::Min($idade, 99999))
        }
    }
    # Boletim diario: o cron e 09h UTC; a partir das 10h UTC, se ainda nao houve execucao hoje (UTC), dispara.
    if ($agora.Hour -ge 10) {
        $diario = Get-UltimaExecucao 'rpa-diario.yml'
        $hoje = $null -ne $diario -and ([DateTime]$diario.createdAt).ToUniversalTime().Date -eq $agora.Date
        if (-not $hoje) { Invoke-Disparo 'rpa-diario.yml' 'nenhum boletim disparado hoje' }
    }
}

if ($null -eq (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Instale o GitHub CLI (gh) e rode gh auth login.' }
do {
    try { Test-Agendamento } catch { Write-Guarda "AVISO $($_.Exception.Message)" }
    if (-not $Repetir) { break }
    Start-Sleep -Seconds $IntervaloSegundos
} while ($true)
