# Encerra apenas processos registrados por iniciar.ps1 neste worktree.
. (Join-Path $PSScriptRoot 'comum.ps1')
foreach ($name in @('cloudflared', 'api', 'ollama')) {
    $process = Get-GenAIManagedProcess $name
    if ($null -ne $process) {
        # /T encerra tambem o filho do launcher do Python de um venv no Windows.
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel encerrar $name (PID $($process.Id))." }
        Write-Host "$name encerrado (PID $($process.Id))."
    } else { Write-Host "${name}: nenhum processo gerenciado ativo." }
    foreach ($suffix in @('pid', 'process.json')) {
        $file = Join-Path $script:GenAIRun "$name.$suffix"
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
}
