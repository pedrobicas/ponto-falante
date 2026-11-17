# Funcoes da visao, compativeis com Windows PowerShell 5.1. Reaproveita o gerenciamento de processos da GenAI
# (scripts/genai/comum.ps1), mas com pasta de execucao propria: scripts/visao/run.
. (Join-Path $PSScriptRoot '../genai/comum.ps1')
$script:GenAIRun = Join-Path $PSScriptRoot 'run'
$script:VisaoDir = Join-Path $script:GenAIRoot 'visao'
$script:VisaoPorta = 8090

function Import-VisaoEnv {
    # Chave: PF_VISAO_SERVICO_CHAVE de scripts/visao/.env.local; sem ela, a GENAI_API_KEY de scripts/genai/.env.local
    # (o backend faz o mesmo fallback). Os valores nunca sao impressos.
    Import-GenAIEnv
    $envFile = Join-Path $PSScriptRoot '.env.local'
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
            $text = $line.Trim()
            if (-not $text -or $text.StartsWith('#')) { continue }
            if ($text -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { throw 'Linha invalida em scripts/visao/.env.local; use NOME=valor.' }
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($Matches[1], $value, 'Process')
        }
    }
    if (-not $env:PF_VISAO_SERVICO_CHAVE) { $env:PF_VISAO_SERVICO_CHAVE = $env:GENAI_API_KEY }
    if (-not $env:PF_VISAO_SERVICO_CHAVE -or $env:PF_VISAO_SERVICO_CHAVE.Length -lt 16) {
        throw 'Defina PF_VISAO_SERVICO_CHAVE em scripts/visao/.env.local (ou GENAI_API_KEY em scripts/genai/.env.local), com 16+ caracteres e igual a do Render.'
    }
}

function Get-VisaoVenv {
    # Worktrees compartilham o ambiente do checkout principal (como a GenAI): .venv-visao fica la.
    $common = & git -C $script:GenAIRoot rev-parse --git-common-dir 2>$null
    if ($LASTEXITCODE -eq 0 -and $common) {
        if (-not [IO.Path]::IsPathRooted($common)) { $common = Join-Path $script:GenAIRoot $common }
        return Join-Path (Split-Path ([IO.Path]::GetFullPath($common)) -Parent) '.venv-visao'
    }
    return Join-Path $script:GenAIRoot '.venv-visao'
}

function Get-VisaoPython {
    if ($env:VISAO_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:VISAO_PYTHON -PathType Leaf)) { throw 'VISAO_PYTHON nao encontrado.' }
        return $env:VISAO_PYTHON
    }
    foreach ($venv in @((Join-Path $script:GenAIRoot '.venv-visao'), (Get-VisaoVenv))) {
        $candidate = Join-Path $venv 'Scripts/python.exe'
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw 'Ambiente da visao nao encontrado. Rode scripts/visao/instalar.ps1 (cria .venv-visao) ou defina VISAO_PYTHON.'
}
