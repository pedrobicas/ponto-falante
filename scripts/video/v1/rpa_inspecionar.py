"""Comandos reais e somente RPA para a gravação. Não executa testes nem avaliações GenAI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.validation/video-rpa-final'
RAW = ROOT / '.validation/video-rpa'
sys.stdout.reconfigure(encoding='utf-8')


def main() -> None:
    mode = sys.argv[1]
    if mode == 'regras':
        import yaml
        cfg = yaml.safe_load((ROOT / 'rpa/config/monitoramento.yaml').read_text(encoding='utf-8'))
        print('ARQUIVO REAL: rpa/config/monitoramento.yaml\n')
        print('regras_estimadas:  # produção: previsões reais, não chegadas')
        for key, value in cfg['regras_estimadas'].items():
            print(f'  {key}: {value}')
        print('\nregras:  # apenas histórico SIMULADO da demonstração')
        for key in ['atraso_critico_min', 'atraso_atencao_min', 'minimo_passagens']:
            print(f'  {key}: {cfg["regras"][key]}')
    elif mode == 'codigo':
        path = ROOT / 'rpa/src/pf_rpa/estimativa.py'
        lines = path.read_text(encoding='utf-8').splitlines()
        print('CÓDIGO REAL: rpa/src/pf_rpa/estimativa.py\n')
        for needle, count in [('    for linha in alvo:', 8), ('        if com < r.minimo_amostras:', 4)]:
            start = next(i for i, line in enumerate(lines) if line.startswith(needle))
            for index in range(start, start + count):
                print(f'{index + 1:3}  {lines[index]}')
            print('     [...]')
    elif mode == 'coleta':
        meta = json.loads((RAW / 'actions-coleta.json').read_text(encoding='utf-8-sig'))
        print(f'LOG JÁ REGISTRADO: GitHub Actions {meta["databaseId"]}')
        print(f'Início UTC: {meta["startedAt"]} | conclusão: {meta["conclusion"]}')
        print('Leitura do arquivo original; nenhuma nova coleta foi disparada.\n')
        for line in (RAW / 'actions-coleta.log').read_text(encoding='utf-8-sig').splitlines():
            if '| pf_rpa.coletor |' in line and any(s in line for s in ['Ponto ', 'Envio:', 'Fim da coleta']):
                print(line.split('| pf_rpa.coletor |', 1)[1].strip())
    elif mode == 'sucesso':
        result = json.loads((RAW / 'resultado-sucesso.json').read_text(encoding='utf-8'))
        b = result['boletim']
        print('RESULTADO DA EXECUÇÃO LOCAL GRAVADA ÀS 13:56:52\n')
        print(f'código de saída: {result["codigo"]} | natureza: {b["natureza_dados"]}')
        for line in result['linhas']:
            if any(s in line for s in ['Histórico simulado', 'Validação:', 'Linha ', 'publicado no MVP']):
                print(line.split('| pf_rpa.robo |', 1)[-1].strip())
        print('\nArquivos reais gerados pela mesma execução:')
        for p in sorted((RAW / 'saida').glob('boletim_2026-11-13.*')):
            print(f'  {p.name}: {p.stat().st_size} bytes')
    elif mode == 'falha':
        url = 'http://127.0.0.1:8232/admin/falha?ativo=true'
        with urlopen(Request(url, method='POST'), timeout=5) as resp:
            print('POST local /admin/falha?ativo=true ->', resp.read().decode())
        print('DEMO LOCAL: falha HTTP 503 na leitura; dados SIMULADOS.\n')
        cmd = [str(ROOT / '.venv/Scripts/python.exe'), '-m', 'pf_rpa.robo', '--config', 'config/monitoramento.yaml', '--data', '2026-11-13']
        print('python -m pf_rpa.robo --config config/monitoramento.yaml --data 2026-11-13', flush=True)
        env = {k: v for k, v in os.environ.items() if k not in {'MVP_URL', 'RPA_API_KEY', 'MOCK_API_KEY'}}
        env.update(PYTHONPATH=str(ROOT / 'rpa/src'), PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        proc = subprocess.run(cmd, cwd=WORK, env=env)
        print(f'\nCódigo de saída real: {proc.returncode}', flush=True)
        return
    elif mode == 'auditoria':
        p = WORK / 'logs/auditoria.jsonl'
        record = json.loads(p.read_text(encoding='utf-8').strip().splitlines()[-1])
        print('ARQUIVO REAL: demo local / logs/auditoria.jsonl\n')
        for key, value in record.items():
            print(f'{key}: {json.dumps(value, ensure_ascii=False)}')
        with urlopen('http://127.0.0.1:8232/boletim', timeout=5) as resp:
            b = json.load(resp)
        print('\nGET http://127.0.0.1:8232/boletim -> HTTP 200')
        for key in ['data_referencia', 'natureza_dados', 'desatualizado']:
            print(f'{key}: {json.dumps(b[key], ensure_ascii=False)}')
    else:
        raise SystemExit(f'Modo desconhecido: {mode}')


if __name__ == '__main__':
    main()
