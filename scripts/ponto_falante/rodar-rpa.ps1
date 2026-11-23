# Roda o robo RPA uma vez contra o site publicado: GET /historico -> classifica atrasos -> POST /boletim.
#  - Com RPA_API_KEY no .env da raiz (a mesma do Render): roda o robo neste PC.
#  - Sem ela: pede ao GitHub o MESMO robo (workflow rpa-diario.yml, que usa os segredos do repositorio) e acompanha a
#    execucao. Se ja houver uma execucao de hoje em andamento ou concluida com sucesso, so acompanha/relata.
# Execute: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ponto_falante/rodar-rpa.ps1 [-Data AAAA-MM-DD]
param([string]$Data = '', [int]$EsperaMinutos = 15)

. (Join-Path $PSScriptRoot 'comum.ps1')
if ($Data -and $Data -notmatch '^\d{4}-\d{2}-\d{2}$') { throw 'Use -Data no formato AAAA-MM-DD.' }
$rpa = Join-Path $script:PFRaiz 'rpa'
$chave = Get-PFEnvValor (Join-Path $script:PFRaiz '.env') 'RPA_API_KEY'

function Invoke-PFRpaLocal {
    $python = Get-GenAIPython
    $ErrorActionPreference = 'Continue'   # PowerShell 5.1 transforma stderr redirecionado em erro com 'Stop'
    & $python -c 'import requests, yaml' 2>$null
    $falta = ($LASTEXITCODE -ne 0)
    $ErrorActionPreference = 'Stop'
    if ($falta) {
        Write-Host 'Instalando dependencias do RPA (rpa/requirements.txt)...'
        & $python -m pip install -q -r (Join-Path $rpa 'requirements.txt') | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel instalar rpa/requirements.txt.' }
    }
    New-Item -ItemType Directory -Path $script:GenAIRun -Force | Out-Null
    $saida = Join-Path $script:GenAIRun 'rpa.log'
    $erros = Join-Path $script:GenAIRun 'rpa.err.log'
    $env:MVP_URL = (Get-PFMvpUrl) + '/api'
    $env:RPA_API_KEY = $chave
    $env:PYTHONPATH = Join-Path $rpa 'src'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $argumentos = @('-m', 'pf_rpa.robo')
    if ($Data) { $argumentos += @('--data', $Data) }
    Write-Host 'Robo RPA rodando neste PC...'
    $p = Start-Process -FilePath $python -ArgumentList $argumentos -WorkingDirectory $rpa -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $saida -RedirectStandardError $erros
    # O robo registra no stderr (logging); as ultimas linhas resumem o resultado.
    Get-Content -LiteralPath $erros, $saida -Tail 6 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    return $p.ExitCode
}

function Get-PFExecucoesHoje {
    $json = & gh run list --workflow rpa-diario.yml --branch main --limit 10 --json databaseId,createdAt,status,conclusion
    if ($LASTEXITCODE -ne 0) { throw 'gh run list falhou (gh instalado e autenticado?).' }
    $hoje = [DateTime]::UtcNow.Date
    return @((($json -join "`n") | ConvertFrom-Json) | Where-Object { ([DateTime]$_.createdAt).ToUniversalTime().Date -eq $hoje })
}

function Invoke-PFRpaGithub {
    if ($null -eq (Get-Command gh.exe -ErrorAction SilentlyContinue)) {
        throw 'Sem RPA_API_KEY no .env e sem GitHub CLI: coloque a chave do Render em RPA_API_KEY no .env da raiz.'
    }
    Set-Location -LiteralPath $script:PFRaiz
    $hoje = Get-PFExecucoesHoje
    $alvo = @($hoje | Where-Object { $_.status -ne 'completed' -or $_.conclusion -eq 'success' }) | Select-Object -First 1
    if ($null -eq $alvo -or $Data) {
        Write-Host 'Sem RPA_API_KEY local: pedindo ao GitHub Actions o robo rpa-diario (usa os segredos do repositorio)...'
        $extra = @(); if ($Data) { $extra = @('-f', "data=$Data") }
        & gh workflow run rpa-diario.yml --ref main @extra | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'gh workflow run falhou.' }
        $prazo = (Get-Date).AddSeconds(60)
        do {
            Start-Sleep -Seconds 5
            $alvo = @(Get-PFExecucoesHoje | Where-Object { $_.status -ne 'completed' }) | Select-Object -First 1
        } while ($null -eq $alvo -and (Get-Date) -lt $prazo)
        if ($null -eq $alvo) { throw 'A execucao pedida nao apareceu no GitHub em 60 s.' }
    } else { Write-Host "Ja existe execucao do robo hoje no GitHub (id $($alvo.databaseId)); acompanhando." }
    $id = $alvo.databaseId
    $prazo = (Get-Date).AddMinutes($EsperaMinutos)
    do {
        $v = (& gh run view $id --json status,conclusion,url) -join "`n" | ConvertFrom-Json
        if ($v.status -eq 'completed') { break }
        Start-Sleep -Seconds 10
    } while ((Get-Date) -lt $prazo)
    Write-Host "    Execucao: $($v.url)"
    Write-Host "    Resultado: $($v.status) / $($v.conclusion)"
    if ($v.status -ne 'completed') { return 2 }
    if ($v.conclusion -eq 'success') { return 0 } else { return 1 }
}

if ($chave) { exit (Invoke-PFRpaLocal) } else { exit (Invoke-PFRpaGithub) }
