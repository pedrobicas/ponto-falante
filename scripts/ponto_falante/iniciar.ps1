# Liga tudo o que o site publicado (https://ponto-falante.onrender.com) precisa deste PC, com um clique:
#   Ollama + modelo -> API da GenAI (8001) -> Quick Tunnel -> registro no site (PUT /api/genai/endereco)
#   servico de visao (8090) -> Quick Tunnel -> registro no site (PUT /api/visao/endereco)
#   robo RPA (GET /historico -> classificar -> POST /boletim)
# Chamado por INICIAR_PONTO_FALANTE.bat. Para desligar: PARAR_PONTO_FALANTE.bat. Para conferir: STATUS_PONTO_FALANTE.bat.
# Os servicos so ficam no ar enquanto este PC estiver ligado e conectado a internet.
param([switch]$SemNavegador, [switch]$SemRpa, [switch]$SemVisao)

. (Join-Path $PSScriptRoot 'comum.ps1')
$ErrorActionPreference = 'Continue'   # uma etapa com problema nao impede as outras
$raiz = $script:PFRaiz
$mvp = Get-PFMvpUrl
$modelo = Get-PFModelo
$resultado = [ordered]@{}

function Update-PFPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-PFWinget([string]$Id, [string]$Nome) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($null -eq $winget) { Write-PFFalha "$Nome nao instalado e o winget nao esta disponivel. Instale $Nome manualmente."; return $false }
    Write-PFInfo "Instalando $Nome (gratuito) pelo winget..."
    & $winget.Source install --id $Id -e --silent --accept-source-agreements --accept-package-agreements | Out-Host
    Update-PFPath
    return $true
}

Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  PONTO FALANTE - iniciando os servicos locais do site' -ForegroundColor Cyan
Write-Host "  Site: $mvp" -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan

# ---------------------------------------------------------------- 1. dependencias
Write-PFTitulo '[1/7] Conferindo dependencias'
$fatal = $false
foreach ($ferramenta in @(@('ollama.exe', 'Ollama.Ollama', 'Ollama'), @('cloudflared.exe', 'Cloudflare.cloudflared', 'cloudflared'))) {
    $cmd = Get-Command $ferramenta[0] -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        Install-PFWinget $ferramenta[1] $ferramenta[2] | Out-Null
        $cmd = Get-Command $ferramenta[0] -ErrorAction SilentlyContinue
    }
    if ($null -ne $cmd) { Write-PFOk "$($ferramenta[2]): $($cmd.Source)" }
    else { Write-PFFalha "$($ferramenta[2]) nao encontrado no PATH."; $fatal = $true }
}

$python = $null
try { $python = Get-GenAIPython } catch { $python = $null }
if (-not $python -or -not (Test-Path -LiteralPath (Join-Path $raiz '.venv/Scripts/python.exe'))) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        Write-PFInfo 'Criando o ambiente Python .venv (primeira vez, pode levar varios minutos)...'
        & $py.Source -3.11 -m venv (Join-Path $raiz '.venv') | Out-Host
        $python = Join-Path $raiz '.venv/Scripts/python.exe'
        & $python -m pip install -q -r (Join-Path $raiz 'genai/requirements.txt') -r (Join-Path $raiz 'rpa/requirements.txt') | Out-Host
    }
}
if ($python -and (Test-Path -LiteralPath $python)) { Write-PFOk "Python da GenAI/RPA: $python" }
else { Write-PFFalha 'Python 3.11 nao encontrado (instale o Python 3.11 e rode de novo).'; $fatal = $true }

if (-not $SemVisao) {
    $pyVisao = Join-Path $raiz '.venv-visao/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pyVisao)) {
        Write-PFInfo 'Instalando o ambiente da visao (.venv-visao, primeira vez)...'
        Invoke-PFScript (Join-Path $raiz 'scripts/visao/instalar.ps1') | Out-Null
    }
    if (Test-Path -LiteralPath $pyVisao) { Write-PFOk "Python da visao: $pyVisao" }
    else { Write-PFAviso 'Ambiente da visao ausente: a conferencia do letreiro ficara desligada.'; $SemVisao = $true }
}

if (Get-PFEnvValor (Join-Path $raiz 'scripts/genai/.env.local') 'GENAI_API_KEY') { Write-PFOk 'Chave da GenAI (scripts/genai/.env.local) encontrada.' }
else { Write-PFFalha 'GENAI_API_KEY ausente em scripts/genai/.env.local (precisa ser a mesma do Render).'; $fatal = $true }
$temChaveRpa = [bool](Get-PFEnvValor (Join-Path $raiz '.env') 'RPA_API_KEY')
$temGh = $null -ne (Get-Command gh.exe -ErrorAction SilentlyContinue)
if ($temChaveRpa) { Write-PFOk 'Chave do RPA (.env) encontrada: o robo roda neste PC.' }
elseif ($temGh) { Write-PFOk 'Sem RPA_API_KEY local: o robo RPA roda no GitHub Actions (rpa-diario.yml) pelo gh.' }
else { Write-PFAviso 'Sem RPA_API_KEY no .env e sem GitHub CLI: o robo RPA nao sera executado.' }
if ($temGh) { Write-PFOk 'GitHub CLI: guarda do agendamento do RPA sera ligada.' }
else { Write-PFAviso 'GitHub CLI (gh) ausente: a guarda do agendamento do RPA fica desligada (opcional).' }

if ($fatal) {
    Write-PFFalha 'Dependencia obrigatoria faltando. Corrija os itens acima e rode INICIAR_PONTO_FALANTE.bat de novo.'
    exit 1
}

# ---------------------------------------------------------------- 2. acordar o site
Write-PFTitulo '[2/7] Acordando o site no Render (o plano gratuito dorme; pode levar ate 3 min)'
$acordar = Start-Job -ArgumentList $mvp -ScriptBlock {
    param($u)
    $prazo = (Get-Date).AddMinutes(6)
    while ((Get-Date) -lt $prazo) {
        try { $r = Invoke-WebRequest -Uri "$u/actuator/health" -UseBasicParsing -TimeoutSec 90; if ($r.StatusCode -eq 200) { return $true } } catch { }
        Start-Sleep -Seconds 5
    }
    return $false
}
Write-PFInfo 'Pedido enviado; enquanto isso, os servicos locais sobem.'

# ---------------------------------------------------------------- 3. GenAI
Write-PFTitulo "[3/7] Assistente (GenAI): Ollama, modelo $modelo, API e tunel"
$codigo = Invoke-PFScript (Join-Path $raiz 'scripts/genai/iniciar.ps1') @('-TunelRapido')
if ($codigo -ne 0) {
    Write-PFFalha 'A GenAI nao subiu (veja a mensagem acima e scripts/genai/run/*.err.log).'
    $resultado['GenAI'] = $false
} else {
    $resultado['GenAI'] = $true
    $tags = $null
    try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10 } catch { }
    $nomes = @(); if ($null -ne $tags) { $nomes = @($tags.models | ForEach-Object { $_.name }) }
    if ($nomes -notcontains $modelo) {
        Write-PFInfo "Baixando o modelo $modelo (primeira vez, ~4,7 GB)..."
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        & (Get-Command ollama.exe).Source pull $modelo
    }
    Write-PFInfo 'Aquecendo o modelo (a primeira resposta fica rapida no site)...'
    try {
        $corpo = @{ model = $modelo; prompt = 'Responda apenas: ok'; stream = $false; keep_alive = '24h'; options = @{ num_predict = 2 } } | ConvertTo-Json -Compress
        Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/generate' -Body $corpo -ContentType 'application/json' -TimeoutSec 300 | Out-Null
        Write-PFOk "Modelo $modelo carregado na memoria."
    } catch { Write-PFAviso "Nao consegui aquecer o modelo: $($_.Exception.Message)" }
    $t = Get-PFTunel 'genai'; if ($t) { Write-PFOk "Tunel da GenAI: $t" }
}

# ---------------------------------------------------------------- 4. visao
if ($SemVisao) {
    Write-PFTitulo '[4/7] Visao computacional: pulada'
} else {
    Write-PFTitulo '[4/7] Visao computacional (letreiro do onibus): servico e tunel'
    $codigo = Invoke-PFScript (Join-Path $raiz 'scripts/visao/iniciar.ps1') @('-TunelRapido')
    if ($codigo -ne 0) {
        Write-PFFalha 'A visao nao subiu (veja a mensagem acima e scripts/visao/run/*.err.log).'
        $resultado['Visao'] = $false
    } else {
        $resultado['Visao'] = $true
        $t = Get-PFTunel 'visao'; if ($t) { Write-PFOk "Tunel da visao: $t" }
    }
}

# ---------------------------------------------------------------- 5. manter acordado
Write-PFTitulo '[5/7] Impedindo a suspensao automatica do PC enquanto os servicos estiverem no ar'
try {
    Start-GenAIProcess -Name 'manter-acordado' -Executable $script:PFPowerShell `
        -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'manter-acordado.ps1')) | Out-Null
    Write-PFOk 'Suspensao automatica bloqueada ate PARAR_PONTO_FALANTE.bat (configuracoes de energia nao foram alteradas).'
} catch { Write-PFAviso "Nao foi possivel bloquear a suspensao: $($_.Exception.Message)" }

# ---------------------------------------------------------------- 6. registro no site
Write-PFTitulo '[6/7] Registrando os tuneis no site e conferindo /api/status'
$acordou = Receive-Job -Job $acordar -Wait -AutoRemoveJob
if ($acordou -contains $true) { Write-PFOk 'Site acordado.' } else { Write-PFAviso 'O site nao respondeu em 6 min; o registro continua tentando a cada 30 s.' }
$esperaGenai = [bool]$resultado['GenAI']
$esperaVisao = (-not $SemVisao) -and [bool]$resultado['Visao']
$prazo = (Get-Date).AddMinutes(4)
$status = $null
do {
    $status = Get-PFStatusMvp
    $okGenai = (-not $esperaGenai) -or ($null -ne $status -and $status.assistente -eq 'DISPONIVEL')
    $okVisao = (-not $esperaVisao) -or ($null -ne $status -and $status.visao -eq 'CONECTADA')
    if ($okGenai -and $okVisao) { break }
    Start-Sleep -Seconds 10
} while ((Get-Date) -lt $prazo)
if ($null -eq $status) { Write-PFFalha 'O site nao respondeu /api/status.' }
else {
    if ($status.assistente -eq 'DISPONIVEL') { Write-PFOk 'Site enxerga o assistente: DISPONIVEL.' } else { Write-PFAviso "Site ainda mostra o assistente como $($status.assistente)." }
    if ($status.visao -eq 'CONECTADA') { Write-PFOk 'Site enxerga a visao: CONECTADA.' } elseif (-not $SemVisao) { Write-PFAviso "Site ainda mostra a visao como $($status.visao)." }
}

# ---------------------------------------------------------------- 7. RPA
if ($SemRpa -or -not ($temChaveRpa -or $temGh)) {
    Write-PFTitulo '[7/7] Robo RPA: pulado'
} else {
    Write-PFTitulo '[7/7] Robo RPA: gerando o boletim de ontem (GET /historico -> classificar -> POST /boletim)'
    $codigo = Invoke-PFScript (Join-Path $PSScriptRoot 'rodar-rpa.ps1')
    if ($codigo -eq 0) { Write-PFOk 'Boletim publicado no site.' } else { Write-PFAviso "O robo terminou com codigo $codigo (detalhes em scripts/ponto_falante/run/rpa*.log)." }
}

# ---------------------------------------------------------------- resumo
Invoke-PFScript (Join-Path $PSScriptRoot 'status.ps1') | Out-Null
Write-Host ''
Write-Host '-------------------------------------------------------------' -ForegroundColor Yellow
Write-Host ' IMPORTANTE: deixe este PC LIGADO e CONECTADO a internet.' -ForegroundColor Yellow
Write-Host ' O assistente e a camera do site rodam aqui; com o PC desligado,' -ForegroundColor Yellow
Write-Host ' o site continua no ar, mas mostra essas duas funcoes como indisponiveis.' -ForegroundColor Yellow
Write-Host ' Para desligar tudo: PARAR_PONTO_FALANTE.bat' -ForegroundColor Yellow
Write-Host '-------------------------------------------------------------' -ForegroundColor Yellow
if (-not $SemNavegador) { Start-Process $mvp }
