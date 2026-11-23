# Impede a suspensao automatica do Windows enquanto os servicos do Ponto Falante estao no ar (como um player de
# video faz). Nao altera nenhuma configuracao de energia: ao encerrar este processo (PARAR_PONTO_FALANTE.bat), o
# Windows volta ao comportamento normal. Nao impede a suspensao por botao, tampa do notebook ou menu Iniciar.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
Add-Type -Namespace PontoFalante -Name Energia -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
# ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001)
$flags = [uint32]2147483649
while ($true) {
    [PontoFalante.Energia]::SetThreadExecutionState($flags) | Out-Null
    Start-Sleep -Seconds 60
}
