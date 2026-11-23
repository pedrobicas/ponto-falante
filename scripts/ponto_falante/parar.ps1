# Desliga tudo o que INICIAR_PONTO_FALANTE.bat ligou: visao, GenAI (tuneis, registros, API e o Ollama que ela
# iniciou) e o bloqueio de suspensao. Um Ollama aberto por fora (icone na bandeja) nao e encerrado.
# Chamado por PARAR_PONTO_FALANTE.bat.
. (Join-Path $PSScriptRoot 'comum.ps1')
$ErrorActionPreference = 'Continue'
$raiz = $script:PFRaiz

Write-PFTitulo 'Desligando a visao computacional'
Invoke-PFScript (Join-Path $raiz 'scripts/visao/parar.ps1') | Out-Null
Write-PFTitulo 'Desligando a GenAI (tunel, registro, API, Ollama)'
Invoke-PFScript (Join-Path $raiz 'scripts/genai/parar.ps1') | Out-Null
Write-PFTitulo 'Liberando a suspensao automatica do PC'
$p = Get-GenAIManagedProcess 'manter-acordado'
if ($null -ne $p) { & taskkill.exe /PID $p.Id /T /F | Out-Null; Write-Host "manter-acordado encerrado (PID $($p.Id))." }
else { Write-Host 'manter-acordado: nenhum processo ativo.' }
foreach ($sufixo in @('pid', 'process.json')) {
    $arq = Join-Path $script:GenAIRun "manter-acordado.$sufixo"
    if (Test-Path -LiteralPath $arq) { Remove-Item -LiteralPath $arq }
}
Write-Host ''
Write-Host 'Servicos locais desligados. O site continua no ar, mas o assistente e a camera ficam indisponiveis' -ForegroundColor Yellow
Write-Host 'ate rodar INICIAR_PONTO_FALANTE.bat de novo.' -ForegroundColor Yellow
