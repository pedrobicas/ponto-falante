"""Verifica os scripts com PowerShell 5.1, usando processos e HTTP controlados."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "genai"
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="Requer Windows PowerShell 5.1")


def ps(codigo, timeout=20):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GENAI_", "CF_TUNNEL_", "PF_"))}
    r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                        "$ErrorActionPreference = 'Stop'; " + codigo],
                       capture_output=True, text=True, timeout=timeout, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def literal(caminho):
    return "'" + str(caminho).replace("'", "''") + "'"


@contextmanager
def copia_scripts():
    # Tudo que este teste grava fica dentro de genai/tests/ e e removido ao sair.
    with tempfile.TemporaryDirectory(prefix="scripts teste ", dir=Path(__file__).parent) as base:
        pasta = Path(base) / "scripts" / "genai"
        pasta.mkdir(parents=True)
        for arquivo in SCRIPTS.glob("*.ps1"):
            shutil.copy2(arquivo, pasta / arquivo.name)
        (Path(base) / "genai").mkdir()
        yield pasta


def test_scripts_sintaxe_windows_powershell():
    ps("""
        if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Use Windows PowerShell 5.1' }
        Get-ChildItem %s -Filter *.ps1 | ForEach-Object {
            $tokens = $null; $errors = $null
            [Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors) | Out-Null
            if ($errors) { throw ($errors | Out-String) }
        }
    """ % literal(SCRIPTS))


def test_env_local_lido_sem_executar_ou_expor_segredo():
    with copia_scripts() as pasta:
        (pasta / ".env.local").write_text(
            '# comentario\nGENAI_API_KEY="segredo-$(throw 123)#literal"\n'
            "GENAI_PUBLIC_URL='https://genai.example.invalid'\n", encoding="utf-8")
        saida = ps("""
            . %s
            Import-GenAIEnv
            if ($env:GENAI_API_KEY -cne 'segredo-$(throw 123)#literal') { throw 'Chave modificada' }
            if ($env:GENAI_PUBLIC_URL -ne 'https://genai.example.invalid') { throw 'URL invalida' }
            Write-Output 'ok'
        """ % literal(pasta / "comum.ps1"))
        assert saida.strip() == "ok"


def test_parar_ignora_pid_reutilizado():
    with copia_scripts() as pasta:
        run = pasta / "run"
        run.mkdir()
        ps("""
            $PID | Set-Content -LiteralPath %s
            @{ Id=$PID; StartTimeTicks='0'; Path='outro.exe' } | ConvertTo-Json | Set-Content -LiteralPath %s
            function taskkill.exe { throw 'Tentou matar PID reutilizado' }
            . %s
        """ % (literal(run / "api.pid"), literal(run / "api.process.json"), literal(pasta / "parar.ps1")))
        assert not (run / "api.pid").exists()


def test_iniciar_sem_chave_falha_antes_de_subir_processos():
    with copia_scripts() as pasta:
        saida = ps("""
            function Start-Process { throw 'Nao deve iniciar processo sem chave' }
            try { . %s; throw 'Nao recusou' }
            catch { if ($_.Exception.Message -notlike '*GENAI_API_KEY*') { throw }; Write-Output 'recusou' }
        """ % literal(pasta / "iniciar.ps1"))
        assert "recusou" in saida
        assert not (pasta / "run").exists()


@pytest.mark.parametrize("desativada,com_tunel,ollama_ativo", [(False, True, True), (True, True, True), (False, False, True), (False, True, False)])
def test_iniciar_loopback_e_tunel_nomeado(desativada, com_tunel, ollama_ativo):
    with copia_scripts() as pasta:
        (pasta / ".env.local").write_text(
            f"GENAI_API_KEY=chave-fake\nCF_TUNNEL_NAME={'meu-tunel' if com_tunel else ''}\n"
            f"GENAI_AUTH_DESATIVADA={int(desativada)}\n", encoding="utf-8")
        saida = ps("""
            $script:launches = @(); $script:ollamaAtivo = %s
            function Get-Process { param($Name,$Id,$ErrorAction) @() }
            function Get-NetTCPConnection { param($LocalPort, $State, $ErrorAction) @() }
            function Get-Command { param($Name, $ErrorAction) [pscustomobject]@{ Source='fake.exe' } }
            function Invoke-WebRequest {
                param($Uri, [switch]$UseBasicParsing, $TimeoutSec)
                if ($Uri -like '*/api/tags' -and -not $script:ollamaAtivo) { $script:ollamaAtivo=$true; throw (New-Object Net.WebException 'offline') }; [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' }
            }
            function Start-Process {
                param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
                $script:launches += [pscustomobject]@{
                    Arguments=$ArgumentList; HostEnv=$env:OLLAMA_HOST; Window=$WindowStyle
                    Log=$RedirectStandardOutput; Workdir=$WorkingDirectory
                }
                [pscustomobject]@{ Id=424242; StartTime=[DateTime]::UtcNow; Path=$FilePath; HasExited=$false }
            }
            function Start-Sleep { param($Milliseconds) }
            $env:GENAI_PYTHON = %s
            . %s
            $script:launches | ConvertTo-Json -Compress
        """ % ("$true" if ollama_ativo else "$false", literal(POWERSHELL), literal(pasta / "iniciar.ps1")))
        linhas = [s for s in saida.splitlines() if s.startswith(("{", "["))]
        launches = json.loads(linhas[-1])
        if isinstance(launches, dict):
            launches = [launches]
        if not ollama_ativo:
            assert launches[0]["Arguments"] == '"serve"'
            assert launches[0]["HostEnv"] == "127.0.0.1:11434"
            launches = launches[1:]
        api = launches[0]
        assert api["HostEnv"] == "127.0.0.1:11434"
        assert api["Window"] == "Hidden"
        assert '"--host" "127.0.0.1" "--port" "8001"' in api["Arguments"]
        assert '"--workers" "1"' in api["Arguments"]
        assert '"--no-access-log"' in api["Arguments"]
        assert api["Log"].endswith("api.log")
        assert (pasta / "run" / "api.pid").read_text().strip() == "424242"
        if desativada or not com_tunel:
            assert len(launches) == 1
        else:
            assert launches[1]["Arguments"] == '"tunnel" "run" "meu-tunel"'


def test_status_consulta_health_publico_sem_chave():
    with copia_scripts() as pasta:
        (pasta / ".env.local").write_text("GENAI_PUBLIC_URL=https://genai.example.invalid/\n", encoding="utf-8")
        saida = ps("""
            $script:urls = @()
            function Invoke-WebRequest {
                param($Uri, [switch]$UseBasicParsing, $TimeoutSec)
                $script:urls += $Uri
                [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' }
            }
            function Get-Process { param($Name, $ErrorAction) @() }
            . %s
            $script:urls | ConvertTo-Json -Compress
        """ % literal(pasta / "status.ps1"))
        urls = json.loads([s for s in saida.splitlines() if s.startswith("[")][-1])
        assert urls == ["http://127.0.0.1:11434/api/tags", "http://127.0.0.1:8001/health",
                        "https://genai.example.invalid/health"]


def test_python_do_checkout_principal_em_worktree():
    with copia_scripts() as pasta:
        checkout = pasta.parents[1] / "principal"
        ambiente = checkout / ".venv" / "Scripts" / "python.exe"
        ambiente.parent.mkdir(parents=True)
        ambiente.touch()
        saida = ps("""
            . %s
            function git { $global:LASTEXITCODE = 0; Write-Output %s }
            Get-GenAIPython
        """ % (literal(pasta / "comum.ps1"), literal(checkout / ".git")))
        assert Path(saida.strip()) == ambiente


def test_ollama_exposto_na_rede_impede_inicializacao():
    with copia_scripts() as pasta:
        saida = ps("""
            $env:GENAI_API_KEY='chave-fake'
            $env:GENAI_PYTHON=%s
            function Get-NetTCPConnection { param($LocalPort,$State,$ErrorAction) [pscustomobject]@{ LocalAddress='0.0.0.0' } }
            function Start-Process { throw 'Nao pode iniciar' }
            try { . %s; throw 'Aceitou listener publico' }
            catch { if ($_.Exception.Message -notlike '*fora do loopback*') { throw }; Write-Output 'recusou' }
        """ % (literal(POWERSHELL), literal(pasta / "iniciar.ps1")))
        assert "recusou" in saida


def test_http_indisponivel_nao_quebra_status():
    with copia_scripts() as pasta:
        saida = ps("""
            . %s
            function Invoke-WebRequest { throw (New-Object Net.WebException 'offline') }
            $result = Get-GenAIHttp 'http://127.0.0.1:8001/health'
            if ($result.Code -ne 0) { throw 'HTTP incorreto' }
            if (Test-GenAIHealth $result) { throw 'Health deveria falhar' }
            Write-Output 'offline'
        """ % literal(pasta / "comum.ps1"))
        assert saida.strip() == "offline"


def test_parar_processo_gerenciado_confere_identidade():
    with copia_scripts() as pasta:
        (pasta / "run").mkdir()
        saida = ps("""
            . %s
            $current = Get-Process -Id $PID
            $current.Id | Set-Content -LiteralPath (Join-Path $script:GenAIRun 'api.pid')
            @{
                Id=$current.Id
                StartTimeTicks=$current.StartTime.ToUniversalTime().Ticks.ToString()
                Path=$current.Path
            } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $script:GenAIRun 'api.process.json')
            $found = Get-GenAIManagedProcess 'api'
            if ($found.Id -ne $current.Id) { throw 'Nao reconheceu processo' }
            $script:stopped = @()
            function taskkill.exe { $script:stopped = $args; $global:LASTEXITCODE=0 }
            . %s
            if (($script:stopped -join ' ') -ne "/PID $PID /T /F") { throw 'Parada incorreta' }
            Write-Output 'parada-simulada'
        """ % (literal(pasta / "comum.ps1"), literal(pasta / "parar.ps1")))
        assert "parada-simulada" in saida
        assert not (pasta / "run" / "api.pid").exists()
        assert not (pasta / "run" / "api.process.json").exists()


def test_status_tolero_resposta_html():
    with copia_scripts() as pasta:
        saida = ps("""
            . %s
            function Invoke-WebRequest {
                [pscustomobject]@{ StatusCode=200; Content='<html>login</html>' }
            }
            $result = Get-GenAIHttp 'https://genai.example.invalid/health'
            if (Test-GenAIHealth $result) { throw 'HTML nao e health' }
            Write-Output 'invalido'
        """ % literal(pasta / "comum.ps1"))
        assert saida.strip() == "invalido"


def test_nao_publica_api_antiga_com_auth_desativada():
    with copia_scripts() as pasta:
        (pasta / "run").mkdir()
        saida = ps("""
            . %s
            $current = Get-Process -Id $PID
            $current.Id | Set-Content -LiteralPath (Join-Path $script:GenAIRun 'api.pid')
            @{
                Id=$current.Id
                StartTimeTicks=$current.StartTime.ToUniversalTime().Ticks.ToString()
                Path=$current.Path
                AuthDisabled=$true
            } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $script:GenAIRun 'api.process.json')
            $env:GENAI_API_KEY='chave-fake'
            $env:GENAI_AUTH_DESATIVADA='0'
            $env:CF_TUNNEL_NAME='meu-tunel'
            $env:GENAI_PYTHON=%s
            function Get-NetTCPConnection { param($LocalPort,$State,$ErrorAction) @() }
            function Get-Command { param($Name,$ErrorAction) [pscustomobject]@{ Source='fake.exe' } }
            function Invoke-WebRequest {
                [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' }
            }
            function Start-Process { throw 'Tentou publicar API antiga' }
            try { . %s; throw 'Nao exigiu reinicio' }
            catch {
                if ($_.Exception.Message -notlike '*parar*iniciar*') { throw }
                Write-Output 'reinicio-obrigatorio'
            }
        """ % (literal(pasta / "comum.ps1"), literal(POWERSHELL), literal(pasta / "iniciar.ps1")))
        assert "reinicio-obrigatorio" in saida


def test_dev_recusa_tunel_ja_ativo():
    with copia_scripts() as pasta:
        saida = ps("""
            $env:GENAI_AUTH_DESATIVADA='1'
            $env:GENAI_PYTHON=%s
            function Get-NetTCPConnection { param($LocalPort,$State,$ErrorAction) @() }
            function Invoke-WebRequest { [pscustomobject]@{ StatusCode=200; Content='{"status":"ok","llm_ok":true,"indice_ok":true}' } }
            function Get-Process { param($Name,$ErrorAction) [pscustomobject]@{ Id=424242 } }
            function Start-Process { throw 'Tentou expor desenvolvimento' }
            try { . %s; throw 'Nao recusou tunel ativo' }
            catch {
                if ($_.Exception.Message -notlike '*cloudflared*ativo*') { throw }
                Write-Output 'recusou'
            }
        """ % (literal(POWERSHELL), literal(pasta / "iniciar.ps1")))
        assert "recusou" in saida
