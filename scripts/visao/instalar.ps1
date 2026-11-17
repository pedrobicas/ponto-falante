# Cria .venv-visao na raiz do checkout principal (worktrees reaproveitam o mesmo ambiente) com o que o servico de visao precisa (YOLO, EasyOCR, FastAPI).
# Com placa NVIDIA, instala o PyTorch com CUDA (inferencia ~10x mais rapida); sem ela, o PyTorch de CPU.
# Execute: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/visao/instalar.ps1 [-Cpu]
param([switch]$Cpu)
. (Join-Path $PSScriptRoot 'comum.ps1')
$venv = Get-VisaoVenv
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts/python.exe'))) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $py) { & $py.Source -3.11 -m venv $venv; if ($LASTEXITCODE -ne 0) { & $py.Source -3 -m venv $venv } }
    else { & python.exe -m venv $venv }
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar .venv-visao (Python 3.10 a 3.12).' }
}
$python = Join-Path $venv 'Scripts/python.exe'
& $python -m pip install --upgrade pip | Out-Null
$temGpu = (-not $Cpu) -and ($null -ne (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue))
if ($temGpu) {
    Write-Host 'Placa NVIDIA encontrada: instalando PyTorch com CUDA 12.4.'
    & $python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
} else {
    Write-Host 'Instalando PyTorch de CPU.'
    & $python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
}
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o PyTorch.' }
& $python -m pip install -r (Join-Path $script:VisaoDir 'requirements-servico.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar requirements-servico.txt.' }
& $python -c "import torch, ultralytics, easyocr, fastapi; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
Write-Host 'Pronto. Inicie com: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/visao/iniciar.ps1 -TunelRapido'
