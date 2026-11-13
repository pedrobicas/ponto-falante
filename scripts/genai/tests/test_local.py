"""Regressões dos controles locais; nunca iniciam túnel ou alteram credenciais."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("scripts_genai_herdados", RAIZ / "genai/tests/test_scripts_genai.py")
herdados = importlib.util.module_from_spec(spec)
spec.loader.exec_module(herdados)
pytestmark = pytest.mark.skipif(not herdados.POWERSHELL, reason="Requer Windows PowerShell 5.1")


def test_somente_local_nao_inicia_tunel_configurado():
    with herdados.copia_scripts() as pasta:
        (pasta / ".env.local").write_text("GENAI_API_KEY=teste-local\nCF_TUNNEL_NAME=nao-iniciar\n", encoding="utf-8")
        saida = herdados.ps("""
            $env:GENAI_PYTHON = %s
            $script:launches = @()
            function Get-Process { param($Name,$Id,$ErrorAction) @() }
            function Get-NetTCPConnection { param($LocalPort,$State,$ErrorAction) @() }
            function Invoke-WebRequest {
                [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' }
            }
            function Start-Process {
                param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
                $script:launches += $ArgumentList
                [pscustomobject]@{ Id=424242; StartTime=[DateTime]::UtcNow; Path=$FilePath; HasExited=$false }
            }
            . %s -SomenteLocal
            if ($script:launches.Count -ne 1 -or $script:launches[0] -notlike '*uvicorn*') { throw 'Iniciou tunel' }
            if ($env:GENAI_API_KEY -ne 'teste-local') { throw 'Alterou chave' }
            Write-Output 'local-seguro'
        """ % (herdados.literal(herdados.POWERSHELL), herdados.literal(pasta / "iniciar.ps1")))
        assert "local-seguro" in saida


def test_somente_local_recusa_tunel_existente():
    with herdados.copia_scripts() as pasta:
        saida = herdados.ps("""
            function Get-Process { param($Name,$ErrorAction) [pscustomobject]@{ Id=424242 } }
            function Start-Process { throw 'Nao deve iniciar' }
            try { . %s -SomenteLocal; throw 'Aceitou tunel ativo' }
            catch { if ($_.Exception.Message -notlike '*SomenteLocal*cloudflared*ativo*') { throw }; Write-Output 'recusou' }
        """ % herdados.literal(pasta / "iniciar.ps1"))
        assert "recusou" in saida


@pytest.mark.parametrize("recusa", [False, True])
def test_verificacao_exige_fundamentacao_e_nao_envia_chave_ao_navegador(recusa):
    with herdados.copia_scripts() as pasta:
        (pasta / ".env.local").write_text("GENAI_API_KEY=segredo-local\n", encoding="utf-8")
        saida = herdados.ps("""
            $script:chamadas = 0
            function Invoke-WebRequest {
                [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' }
            }
            function Invoke-RestMethod {
                param($Method,$Uri,$Headers,$ContentType,$Body,$TimeoutSec)
                $script:chamadas++
                if ($Uri -like '*8001/chat' -and $Headers['X-API-Key'] -ne 'segredo-local') { throw 'Chave ausente' }
                if ($Uri -like '*8080/api/chat' -and $null -ne $Headers) { throw 'Chave enviada ao MVP publico' }
                [pscustomobject]@{ resposta='Texto verificado.'; nao_consta=%s; fontes=@(@{documento='teste';trecho_id='a'});modo='rag_agente_v3' }
            }
            try { . %s; Write-Output 'passou' }
            catch { if ($_.Exception.Message -notlike '*nao retornou uma resposta fundamentada*') { throw }; Write-Output 'recusou' }
            Write-Output "chamadas=$script:chamadas"
        """ % ("$true" if recusa else "$false", herdados.literal(pasta / "verificar-local.ps1")))
        assert "segredo-local" not in saida
        assert ("recusou" if recusa else "passou") in saida
        assert f"chamadas={1 if recusa else 2}" in saida
