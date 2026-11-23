# Funcoes do inicializador unico (INICIAR/PARAR/STATUS_PONTO_FALANTE.bat), compativeis com Windows PowerShell 5.1.
# Reaproveita o gerenciamento de processos da GenAI (scripts/genai/comum.ps1) com pasta de execucao propria.
. (Join-Path $PSScriptRoot '../genai/comum.ps1')
$script:GenAIRun = Join-Path $PSScriptRoot 'run'
$script:PFRaiz = $script:GenAIRoot
$script:PFPowerShell = (Get-Process -Id $PID).Path

function Write-PFTitulo([string]$Texto) {
    Write-Host ''
    Write-Host $Texto -ForegroundColor Cyan
}
function Write-PFOk([string]$Texto) { Write-Host "  [ OK ]  $Texto" -ForegroundColor Green }
function Write-PFAviso([string]$Texto) { Write-Host "  [AVISO] $Texto" -ForegroundColor Yellow }
function Write-PFFalha([string]$Texto) { Write-Host "  [FALHA] $Texto" -ForegroundColor Red }
function Write-PFInfo([string]$Texto) { Write-Host "          $Texto" }

function Get-PFEnvValor {
    # Le um valor de um arquivo NOME=valor sem imprimi-lo. Devolve $null se nao existir.
    param([Parameter(Mandatory=$true)][string]$Arquivo, [Parameter(Mandatory=$true)][string]$Nome)
    if (-not (Test-Path -LiteralPath $Arquivo)) { return $null }
    foreach ($linha in Get-Content -LiteralPath $Arquivo -Encoding UTF8) {
        $t = $linha.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        if ($t -match '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$' -and $Matches[1] -eq $Nome) {
            $v = $Matches[2].Trim().Trim('"').Trim("'")
            if ($v) { return $v }
        }
    }
    return $null
}

function Get-PFMvpUrl {
    $url = Get-PFEnvValor (Join-Path $script:PFRaiz 'scripts/genai/.env.local') 'MVP_PUBLICO_URL'
    if (-not $url) { $url = 'https://ponto-falante.onrender.com' }
    return $url.TrimEnd('/')
}

function Get-PFModelo {
    $m = Get-PFEnvValor (Join-Path $script:PFRaiz 'scripts/genai/.env.local') 'PF_MODELO'
    if (-not $m) { $m = 'qwen2.5:7b' }
    return $m
}

function Get-PFStatusMvp {
    # GET /api/status do site publicado; $null se nao respondeu.
    param([int]$TimeoutSeconds = 30)
    try { return Invoke-RestMethod -Uri ((Get-PFMvpUrl) + '/api/status') -TimeoutSec $TimeoutSeconds }
    catch { return $null }
}

function Get-PFTunel {
    # Endereco vigente do Quick Tunnel anunciado no log do cloudflared de um modulo (genai ou visao).
    param([Parameter(Mandatory=$true)][ValidateSet('genai', 'visao')][string]$Modulo)
    $log = Join-Path $script:PFRaiz "scripts/$Modulo/run/cloudflared.err.log"
    if (-not (Test-Path -LiteralPath $log)) { return $null }
    $achados = Select-String -LiteralPath $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches
    if (-not $achados) { return $null }
    return ($achados | Select-Object -Last 1).Matches[-1].Value
}

function Test-PFProcessoModulo {
    # $true se o processo gerenciado <Nome> de scripts/<Modulo>/run estiver vivo.
    param([string]$Modulo, [string]$Nome)
    $anterior = $script:GenAIRun
    try {
        $script:GenAIRun = Join-Path $script:PFRaiz "scripts/$Modulo/run"
        return ($null -ne (Get-GenAIManagedProcess $Nome))
    } finally { $script:GenAIRun = $anterior }
}

function Invoke-PFScript {
    # Roda outro .ps1 num processo separado (um throw la nao derruba este script). Devolve o codigo de saida.
    # Sem pipe: os servicos que o filho inicia herdam o stdout dele, e um pipe so fecharia quando eles terminassem.
    # Tambem sem Start-Process -Wait, que no PowerShell 5.1 espera a arvore inteira de processos.
    param([Parameter(Mandatory=$true)][string]$Script, [string[]]$Argumentos = @())
    $lista = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $Script + '"')) + $Argumentos
    $p = Start-Process -FilePath $script:PFPowerShell -ArgumentList $lista -NoNewWindow -PassThru
    $null = $p.Handle   # guarda o handle para ler ExitCode depois que o processo terminar
    $p.WaitForExit()
    return $p.ExitCode
}
