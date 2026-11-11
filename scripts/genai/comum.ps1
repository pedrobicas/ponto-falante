# Funcoes compartilhadas, compativeis com Windows PowerShell 5.1.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:GenAIRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$script:GenAIRun = Join-Path $PSScriptRoot 'run'

function Import-GenAIEnv {
    $envFile = Join-Path $PSScriptRoot '.env.local'
    if (-not (Test-Path -LiteralPath $envFile)) { return }
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $lineNumber++
        $text = $line.Trim()
        if (-not $text -or $text.StartsWith('#')) { continue }
        if ($text -notmatch '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            throw "Linha $lineNumber invalida em .env.local; use NOME=valor."
        }
        $name = $Matches[1]
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
             ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        # Nunca executar, interpolar ou imprimir o valor de um segredo.
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

function Get-GenAIManagedProcess {
    param([Parameter(Mandatory=$true)][string]$Name)
    $pidFile = Join-Path $script:GenAIRun "$Name.pid"
    $identityFile = Join-Path $script:GenAIRun "$Name.process.json"
    if (-not (Test-Path -LiteralPath $pidFile) -or -not (Test-Path -LiteralPath $identityFile)) { return $null }
    try {
        $processId = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
        $identity = Get-Content -LiteralPath $identityFile -Raw | ConvertFrom-Json
        $process = Get-Process -Id $processId -ErrorAction Stop
        if ($process.Id -ne $identity.Id -or
            $process.StartTime.ToUniversalTime().Ticks.ToString() -ne $identity.StartTimeTicks -or
            $process.Path -ne $identity.Path) { return $null }
        return $process
    } catch { return $null }
}

function Start-GenAIProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [string]$WorkingDirectory = $script:GenAIRoot
    )
    $existing = Get-GenAIManagedProcess $Name
    if ($null -ne $existing) {
        if ($Name -eq 'api') {
            $identity = Get-Content -LiteralPath (Join-Path $script:GenAIRun 'api.process.json') -Raw | ConvertFrom-Json
            if ($null -eq $identity.PSObject.Properties['AuthDisabled'] -or
                $identity.AuthDisabled -ne ($env:GENAI_AUTH_DESATIVADA -eq '1')) {
                throw 'Modo de autenticacao da API mudou; execute parar.ps1 e iniciar.ps1 antes de reutilizar.'
            }
        }
        Write-Host "$Name ja iniciado (PID $($existing.Id))."
        return $existing
    }
    New-Item -ItemType Directory -Path $script:GenAIRun -Force | Out-Null
    # Start-Process junta argumentos com espacos: citar cada argumento explicitamente.
    $quoted = foreach ($argument in $Arguments) {
        if ($argument.Contains('"') -or $argument.Contains("`n") -or $argument.Contains("`r")) {
            throw 'Argumento de processo invalido: aspas ou quebra de linha.'
        }
        '"' + $argument + '"'
    }
    $process = Start-Process -FilePath $Executable -ArgumentList ($quoted -join ' ') `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $script:GenAIRun "$Name.log") `
        -RedirectStandardError (Join-Path $script:GenAIRun "$Name.err.log")
    try {
        $identity = @{
            Id = $process.Id
            StartTimeTicks = $process.StartTime.ToUniversalTime().Ticks.ToString()
            Path = $process.Path
        }
        if ($Name -eq 'api') { $identity['AuthDisabled'] = ($env:GENAI_AUTH_DESATIVADA -eq '1') }
        $identity | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $script:GenAIRun "$Name.process.json") -Encoding UTF8
        $process.Id | Set-Content -LiteralPath (Join-Path $script:GenAIRun "$Name.pid") -Encoding ASCII
    } catch {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        throw 'Nao foi possivel registrar o processo; consulte os logs em scripts/genai/run/.'
    }
    Write-Host "$Name iniciado (PID $($process.Id))."
    return $process
}

function Get-GenAIHttp {
    param([string]$Url, [int]$TimeoutSeconds = 3)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return [pscustomobject]@{ Code = [int]$response.StatusCode; Body = ($response.Content | ConvertFrom-Json) }
    } catch {
        # PowerShell 5.1 lanca excecao para 503; o corpo ainda e util no /health.
        $response = $null
        if ($null -ne $_.Exception.PSObject.Properties['Response']) { $response = $_.Exception.Response }
        if ($null -ne $response) {
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            try { $body = $reader.ReadToEnd() | ConvertFrom-Json } catch { $body = $null } finally { $reader.Dispose() }
            return [pscustomobject]@{ Code = [int]$response.StatusCode; Body = $body }
        }
        return [pscustomobject]@{ Code = 0; Body = $null }
    }
}

function Test-GenAIHealth {
    param($Result)
    return ($Result.Code -in @(200, 503) -and $null -ne $Result.Body -and
            $null -ne $Result.Body.PSObject.Properties['status'] -and
            $null -ne $Result.Body.PSObject.Properties['llm_ok'] -and
            $null -ne $Result.Body.PSObject.Properties['indice_ok'])
}

function Get-GenAIPython {
    if ($env:GENAI_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:GENAI_PYTHON -PathType Leaf)) { throw 'GENAI_PYTHON nao encontrado.' }
        return $env:GENAI_PYTHON
    }
    $candidate = Join-Path $script:GenAIRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    # Worktrees podem compartilhar o ambiente virtual do checkout principal.
    $common = & git -C $script:GenAIRoot rev-parse --git-common-dir 2>$null
    if ($LASTEXITCODE -eq 0 -and $common) {
        if (-not [IO.Path]::IsPathRooted($common)) { $common = Join-Path $script:GenAIRoot $common }; $common = [IO.Path]::GetFullPath($common)
        $candidate = Join-Path (Split-Path $common -Parent) '.venv/Scripts/python.exe'
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw 'Configure GENAI_PYTHON em scripts/genai/.env.local.' }
    return $command.Source
}
