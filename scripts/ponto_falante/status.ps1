# Mostra, em uma tabela, o estado de cada servico local e o que o site publicado enxerga.
# Com -Testar, faz tambem um teste de ponta a ponta pelo site: uma pergunta ao assistente e uma foto de letreiro.
# Chamado por STATUS_PONTO_FALANTE.bat e no fim de INICIAR_PONTO_FALANTE.bat.
param([switch]$Testar)

. (Join-Path $PSScriptRoot 'comum.ps1')
$ErrorActionPreference = 'Continue'
$raiz = $script:PFRaiz
$mvp = Get-PFMvpUrl
$modelo = Get-PFModelo
$linhas = New-Object System.Collections.Generic.List[object]
function Add-PFLinha([string]$Item, [bool]$Ok, [string]$Detalhe) {
    $linhas.Add([pscustomobject]@{ Item = $Item; Ok = $Ok; Detalhe = $Detalhe })
}

# Ollama e modelo
$tags = $null
try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 } catch { }
if ($null -eq $tags) { Add-PFLinha 'Ollama' $false 'nao responde em 127.0.0.1:11434' }
else {
    $tem = @($tags.models | ForEach-Object { $_.name }) -contains $modelo
    Add-PFLinha 'Ollama' $true '127.0.0.1:11434'
    Add-PFLinha "Modelo $modelo" $tem $(if ($tem) { 'baixado' } else { 'NAO baixado (ollama pull)' })
}

# GenAI local e tunel
$saude = Get-GenAIHttp 'http://127.0.0.1:8001/health' -TimeoutSeconds 5
if (Test-GenAIHealth $saude) {
    Add-PFLinha 'API GenAI (local)' ($saude.Code -eq 200) ("status={0} llm_ok={1} indice_ok={2}" -f $saude.Body.status, $saude.Body.llm_ok, $saude.Body.indice_ok)
} else { Add-PFLinha 'API GenAI (local)' $false 'nao responde em 127.0.0.1:8001' }
$tunel = Get-PFTunel 'genai'
$vivo = Test-PFProcessoModulo 'genai' 'cloudflared'
if ($vivo -and $tunel) {
    $pub = Get-GenAIHttp "$tunel/health" -TimeoutSeconds 15
    Add-PFLinha 'Tunel GenAI' ($pub.Code -eq 200) "$tunel (HTTP $($pub.Code))"
} else { Add-PFLinha 'Tunel GenAI' $false 'cloudflared da GenAI parado' }

# Visao local e tunel
$saudeVisao = Get-GenAIHttp 'http://127.0.0.1:8090/health' -TimeoutSeconds 5
if ($saudeVisao.Code -eq 200) {
    $disp = ''; if ($null -ne $saudeVisao.Body -and $null -ne $saudeVisao.Body.PSObject.Properties['dispositivo']) { $disp = "modelo carregado ($($saudeVisao.Body.dispositivo))" }
    Add-PFLinha 'Servico de visao (local)' $true $disp
} else { Add-PFLinha 'Servico de visao (local)' $false 'nao responde em 127.0.0.1:8090' }
$tunelVisao = Get-PFTunel 'visao'
$vivoVisao = Test-PFProcessoModulo 'visao' 'cloudflared'
if ($vivoVisao -and $tunelVisao) {
    $pubV = Get-GenAIHttp "$tunelVisao/health" -TimeoutSeconds 15
    Add-PFLinha 'Tunel visao' ($pubV.Code -eq 200) "$tunelVisao (HTTP $($pubV.Code))"
} else { Add-PFLinha 'Tunel visao' $false 'cloudflared da visao parado' }

# Processos de apoio
Add-PFLinha 'Registro automatico (GenAI)' (Test-PFProcessoModulo 'genai' 'registro') 'renova o endereco no site a cada 10 min'
Add-PFLinha 'Registro automatico (visao)' (Test-PFProcessoModulo 'visao' 'registro') 'renova o endereco no site a cada 10 min'
Add-PFLinha 'Guarda do agendamento RPA' (Test-PFProcessoModulo 'genai' 'guarda-rpa') 'dispara o workflow se o cron do GitHub falhar'
Add-PFLinha 'PC sem suspensao automatica' (Test-PFProcessoModulo 'ponto_falante' 'manter-acordado') 'ate PARAR_PONTO_FALANTE.bat'

# O que o site enxerga
$status = Get-PFStatusMvp -TimeoutSeconds 90
if ($null -eq $status) { Add-PFLinha 'Site publicado' $false "$mvp nao respondeu /api/status" }
else {
    Add-PFLinha 'Site publicado' $true "$mvp (versao $($status.versao), SPTrans $($status.sptrans))"
    Add-PFLinha 'Site -> assistente' ($status.assistente -eq 'DISPONIVEL') $status.assistente
    Add-PFLinha 'Site -> visao' ($status.visao -eq 'CONECTADA') $status.visao
    $ontem = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
    $boletim = [string]$status.ultimo_boletim
    Add-PFLinha 'Site -> ultimo boletim RPA' ($boletim -ge $ontem) $(if ($boletim) { $boletim } else { 'nenhum' })
}

if ($Testar -and $null -ne $status) {
    # Pergunta real ao assistente pelo site (Render -> tunel -> API -> Ollama).
    try {
        $corpo = [Text.Encoding]::UTF8.GetBytes((@{ pergunta = 'O que e o Bilhete Unico?' } | ConvertTo-Json -Compress))
        $ini = Get-Date
        $w = Invoke-WebRequest -Method Post -Uri "$mvp/api/chat" -Body $corpo -ContentType 'application/json; charset=utf-8' -TimeoutSec 120 -UseBasicParsing
        # Decodifica como UTF-8 (o PowerShell 5.1 erra os acentos quando o Content-Type nao traz charset).
        $r = [Text.Encoding]::UTF8.GetString($w.RawContentStream.ToArray()) | ConvertFrom-Json
        $seg = [int]((Get-Date) - $ini).TotalSeconds
        $txt = [string]$r.resposta; if ($txt.Length -gt 90) { $txt = $txt.Substring(0, 90) + '...' }
        Add-PFLinha 'Teste: pergunta no site' ([bool]$r.disponivel) ("{0} s, origem {1}: {2}" -f $seg, $r.origem, $txt)
    } catch { Add-PFLinha 'Teste: pergunta no site' $false $_.Exception.Message }
    # Foto real de letreiro pelo site (Render -> tunel -> servico de visao).
    $foto = Join-Path $raiz 'visao/amostras/imagens/demo/01_647P-10.jpg'
    if (Test-Path -LiteralPath $foto) {
        try {
            Add-Type -AssemblyName System.Net.Http
            $cliente = New-Object System.Net.Http.HttpClient
            $cliente.Timeout = [TimeSpan]::FromSeconds(120)
            $form = New-Object System.Net.Http.MultipartFormDataContent
            $bytes = New-Object System.Net.Http.ByteArrayContent(,[IO.File]::ReadAllBytes($foto))
            $bytes.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('image/jpeg')
            $form.Add($bytes, 'imagem', 'letreiro.jpg')
            $form.Add((New-Object System.Net.Http.StringContent('647P-10')), 'linha_esperada')
            $req = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, "$mvp/api/embarque/visao/conferir")
            $req.Headers.Add('X-PF-Dispositivo', ([guid]::NewGuid().ToString('N')))
            $req.Content = $form
            $ini = Get-Date
            $resp = $cliente.SendAsync($req).Result
            $seg = [int]((Get-Date) - $ini).TotalSeconds
            $json = [Text.Encoding]::UTF8.GetString($resp.Content.ReadAsByteArrayAsync().Result)
            try { $c = $json | ConvertFrom-Json; $txt = "$($c.resultado), leu $($c.linha_lida): $($c.frase_falada)" } catch { $txt = $json }
            if ($txt.Length -gt 110) { $txt = $txt.Substring(0, 110) + '...' }
            Add-PFLinha 'Teste: foto do letreiro no site' $resp.IsSuccessStatusCode ("HTTP {0}, {1} s: {2}" -f [int]$resp.StatusCode, $seg, $txt)
        } catch { Add-PFLinha 'Teste: foto do letreiro no site' $false $_.Exception.Message }
    }
}

Write-Host ''
Write-Host "PONTO FALANTE - estado em $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')" -ForegroundColor Cyan
foreach ($l in $linhas) {
    $cor = if ($l.Ok) { 'Green' } else { 'Red' }
    $marca = if ($l.Ok) { '[ OK ]' } else { '[ -- ]' }
    Write-Host ("  {0} {1,-32} {2}" -f $marca, $l.Item, $l.Detalhe) -ForegroundColor $cor
}
$falhas = @($linhas | Where-Object { -not $_.Ok }).Count
Write-Host ''
if ($falhas -eq 0) { Write-Host "Tudo funcionando. Site: $mvp" -ForegroundColor Green }
else { Write-Host "$falhas item(ns) com problema. Logs: scripts/genai/run, scripts/visao/run e scripts/ponto_falante/run." -ForegroundColor Yellow }
exit $falhas
