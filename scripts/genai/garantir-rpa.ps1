# Guarda do agendamento do RPA. O cron do GitHub Actions e "melhor esforco": em 13/11 so 3 das 8 coletas previstas
# rodaram (17 consultas de 48) e o rpa-diario chegou a atrasar 8 h. Enquanto o PC da GenAI estiver ligado, este
# script confere a ultima execucao e dispara o MESMO workflow pelo gh (workflow_dispatch) quando o cron falhou.
# Nao coleta nada localmente, nao usa segredos do RPA e nao altera dados: so pede ao GitHub a execucao que faltou.
#
#   powershell -ExecutionPolicy Bypass -File scripts/genai/garantir-rpa.ps1            # uma verificacao
#   powershell -ExecutionPolicy Bypass -File scripts/genai/garantir-rpa.ps1 -Repetir   # a cada 15 min
param([switch]$Repetir, [int]$IntervaloSegundos = 900, [int]$TentativasMax = 3, [string]$Ref = 'main', [switch]$SoMostrar, [string]$AgoraUtc = '')
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-Guarda([string]$Texto) { Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Texto" }

function Get-Execucoes([string]$Workflow) {
    $json = & gh run list --workflow $Workflow --branch $Ref --limit 30 --json createdAt,status,conclusion 2>$null
    if ($LASTEXITCODE -ne 0) { throw "gh run list falhou para $Workflow (gh instalado e autenticado?)" }
    # Parenteses: no PowerShell 5.1 o ConvertFrom-Json entrega o array inteiro como um unico objeto no pipeline.
    $lista = (($json -join "`n") | ConvertFrom-Json)
    return @($lista | ForEach-Object {
        [pscustomobject]@{ Criado = ([DateTime]$_.createdAt).ToUniversalTime(); Status = $_.status; Conclusao = $_.conclusion }
    })
}

# Horarios do cron de rpa-coleta.yml (UTC, minuto 17). Cada coleta cobre a janela de 2 h que comeca na sua hora,
# a mesma usada no calculo de cobertura do boletim (07h-09h, 09h-11h, ..., 21h-23h em Sao Paulo).
$HorasColeta = @(0, 10, 12, 14, 16, 18, 20, 22)

function Get-SlotAtual([DateTime]$Agora) {
    $candidatos = foreach ($dia in @($Agora.Date.AddDays(-1), $Agora.Date)) {
        foreach ($h in $HorasColeta) { $dia.AddHours($h).AddMinutes(17) }
    }
    return @($candidatos | Where-Object { $_ -le $Agora } | Sort-Object)[-1]
}

function Invoke-Disparo([string]$Workflow, [string]$Motivo) {
    if ($SoMostrar) { Write-Guarda "dispararia $Workflow ($Motivo)"; return }
    & gh workflow run $Workflow --ref $Ref 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Guarda "disparado $Workflow ($Motivo)" } else { Write-Guarda "AVISO falha ao disparar $Workflow" }
}

function Test-Agendamento {
    $agora = if ($AgoraUtc) { [DateTime]::Parse($AgoraUtc, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal) } else { [DateTime]::UtcNow }
    # Coleta: so age dentro da janela do horario previsto, depois de dar 25 min de tolerancia ao cron.
    # Nao dispara se ja existe execucao (agendada ou manual) criada a partir de 20 min antes do horario.
    $slot = Get-SlotAtual $agora
    $fimJanela = $slot.AddMinutes(-17).AddHours(2)
    if ($agora -ge $slot.AddMinutes(25) -and $agora -lt $fimJanela) {
        $doSlot = @(Get-Execucoes 'rpa-coleta.yml' | Where-Object { $_.Criado -ge $slot.AddMinutes(-20) })
        $ok = @($doSlot | Where-Object { $_.Status -ne 'completed' -or $_.Conclusao -eq 'success' })
        if ($ok.Count -eq 0 -and $doSlot.Count -lt $TentativasMax) {
            Invoke-Disparo 'rpa-coleta.yml' ("coleta das {0:HH:mm} UTC nao rodou ({1} tentativa(s) falha(s))" -f $slot, $doSlot.Count)
        }
    }
    # Boletim diario: o cron e 09h UTC. A partir das 10h UTC, exige uma execucao BEM-SUCEDIDA hoje (UTC); falhas e
    # cancelamentos contam como tentativa, com no maximo $TentativasMax por dia.
    if ($agora.Hour -ge 10) {
        $hoje = @(Get-Execucoes 'rpa-diario.yml' | Where-Object { $_.Criado.Date -eq $agora.Date })
        $ok = @($hoje | Where-Object { $_.Status -ne 'completed' -or $_.Conclusao -eq 'success' })
        if ($ok.Count -eq 0) {
            if ($hoje.Count -lt $TentativasMax) { Invoke-Disparo 'rpa-diario.yml' ("sem boletim bem-sucedido hoje ({0} tentativa(s))" -f $hoje.Count) }
            else { Write-Guarda "AVISO rpa-diario falhou $($hoje.Count) vezes hoje; nao dispara de novo" }
        }
    }
}

if ($null -eq (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Instale o GitHub CLI (gh) e rode gh auth login.' }
do {
    try { Test-Agendamento } catch { Write-Guarda "AVISO $($_.Exception.Message)" }
    if (-not $Repetir) { break }
    Start-Sleep -Seconds $IntervaloSegundos
} while ($true)
