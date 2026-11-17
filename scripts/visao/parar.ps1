# Encerra apenas os processos da visao registrados por iniciar.ps1 (scripts/visao/run).
. (Join-Path $PSScriptRoot 'comum.ps1')
foreach ($name in @('registro', 'cloudflared', 'servico')) {
    $process = Get-GenAIManagedProcess $name
    if ($null -ne $process) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel encerrar $name (PID $($process.Id))." }
        Write-Host "$name encerrado (PID $($process.Id))."
    } else { Write-Host "${name}: nenhum processo gerenciado ativo." }
    foreach ($suffix in @('pid', 'process.json')) {
        $file = Join-Path $script:GenAIRun "$name.$suffix"
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
}
