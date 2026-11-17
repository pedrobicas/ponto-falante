# Mostra o estado do servico de visao, do tunel e do registro no backend.
. (Join-Path $PSScriptRoot 'comum.ps1')
$saude = Get-GenAIHttp "http://127.0.0.1:$($script:VisaoPorta)/health" -TimeoutSeconds 5
if ($saude.Code -eq 200) { Write-Host "Servico local: ok ($($saude.Body.dispositivo)), $($saude.Body.modelo)." }
else { Write-Warning "Servico local: indisponivel (HTTP $($saude.Code))." }
foreach ($name in @('cloudflared', 'registro')) {
    $p = Get-GenAIManagedProcess $name
    if ($null -ne $p) { Write-Host "${name}: ativo (PID $($p.Id))." } else { Write-Warning "${name}: nenhum processo ativo." }
}
$ultima = Get-Content -LiteralPath (Join-Path $script:GenAIRun 'registro.log') -Tail 1 -ErrorAction SilentlyContinue
if ($ultima) { Write-Host "Ultimo registro: $ultima" }
$mvp = if ($env:MVP_PUBLICO_URL) { $env:MVP_PUBLICO_URL.TrimEnd('/') } else { 'https://ponto-falante.onrender.com' }
$publico = Get-GenAIHttp "$mvp/api/embarque/visao" -TimeoutSeconds 90
if ($publico.Code -eq 200) { Write-Host "Site publicado: conectada=$($publico.Body.conectada)." }
