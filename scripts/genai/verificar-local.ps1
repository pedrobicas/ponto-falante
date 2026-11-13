# Verificacao funcional manual: usa somente loopback e nao imprime pergunta, resposta ou chave.
param(
    [ValidateRange(1, 65535)][int]$PortaMvp = 8080,
    [string]$Pergunta = 'O Bilhete Unico e pessoal e intransferivel?'
)

. (Join-Path $PSScriptRoot 'comum.ps1')
Import-GenAIEnv

function Test-RespostaFundamentada {
    param($Resposta, [string]$Camada)
    if ($null -eq $Resposta -or
        $null -eq $Resposta.PSObject.Properties['resposta'] -or
        $Resposta.resposta -isnot [string] -or -not $Resposta.resposta.Trim() -or
        $null -eq $Resposta.PSObject.Properties['nao_consta'] -or
        $Resposta.nao_consta -isnot [bool] -or
        $null -eq $Resposta.PSObject.Properties['fontes'] -or
        $null -eq $Resposta.PSObject.Properties['modo']) {
        throw "$Camada retornou contrato invalido."
    }
    if ($Resposta.nao_consta -or @($Resposta.fontes).Count -eq 0 -or
        $Resposta.modo -notin @('rag', 'rag_agente', 'rag_agente_v2', 'rag_agente_v3')) {
        throw "$Camada nao retornou uma resposta fundamentada. Verifique modo, fontes e disponibilidade localmente."
    }
    Write-Host "$Camada`: resposta com $(@($Resposta.fontes).Count) fonte(s); modo=$($Resposta.modo)."
}

$health = Get-GenAIHttp 'http://127.0.0.1:8001/health' -TimeoutSeconds 10
if (-not (Test-GenAIHealth $health) -or $health.Code -ne 200 -or
    $health.Body.llm_ok -ne $true -or $health.Body.indice_ok -ne $true) {
    throw 'GenAI local nao esta pronta. Execute status.ps1 e confira modelo/indice antes do teste.'
}
if (-not $env:GENAI_API_KEY -and $env:GENAI_AUTH_DESATIVADA -ne '1') {
    throw 'GENAI_API_KEY nao configurada para verificar a API local.'
}
$headers = @{}
if ($env:GENAI_API_KEY) { $headers['X-API-Key'] = $env:GENAI_API_KEY }
$body = [Text.Encoding]::UTF8.GetBytes((@{ pergunta = $Pergunta } | ConvertTo-Json -Compress))
try {
    $direta = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8001/chat' `
        -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 120
} catch { throw 'Falha na chamada direta ao /chat local. Consulte o status e os logs sem divulgar chaves.' }
Test-RespostaFundamentada $direta 'FastAPI/Ollama'

try {
    $mvp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$PortaMvp/api/chat" `
        -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 120
} catch { throw 'Falha no /api/chat do MVP. Confira Spring, GENAI_URL e a igualdade das chaves nos dois processos.' }
Test-RespostaFundamentada $mvp 'Spring/FastAPI/Ollama'
Write-Host 'Integracao HTTP local confirmada. Ainda valide o fluxo do assistente no navegador e com teclado/voz.'
