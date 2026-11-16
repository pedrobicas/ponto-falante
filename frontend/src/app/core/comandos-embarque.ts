/**
 * Intérprete de comandos do Embarque Assistido (voz ou texto). É determinístico e roda no navegador: as ações
 * do aplicativo funcionam mesmo sem a IA local (Ollama). O que não for comando vira pergunta para o assistente.
 */
export type Comando =
  | { tipo: 'sim' }
  | { tipo: 'nao' }
  | { tipo: 'ajuda' }
  | { tipo: 'repetir' }
  | { tipo: 'quanto-falta' }
  | { tipo: 'parar' }
  | { tipo: 'embarquei' }
  | { tipo: 'silenciar' }
  | { tipo: 'falar' }
  | { tipo: 'perto' }
  | { tipo: 'conferir-camera' }
  | { tipo: 'listar-favoritos' }
  | { tipo: 'salvar-favorito'; apelido?: string }
  | { tipo: 'remover-favorito'; alvo?: string }
  | { tipo: 'usar-favorito'; alvo: string }
  | { tipo: 'acompanhar'; linha?: string; ponto?: number }
  | { tipo: 'escolher'; indice: number }
  | { tipo: 'buscar-ponto'; termo: string }
  | { tipo: 'trocar-ponto' }
  | { tipo: 'pergunta'; texto: string };

export function normalizar(texto: string): string {
  return (texto ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[“”"!?¿¡.,;:]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const ORDINAIS: Record<string, number> = {
  primeiro: 1, primeira: 1, um: 1, uma: 1, '1': 1, '1o': 1, '1a': 1,
  segundo: 2, segunda: 2, dois: 2, duas: 2, '2': 2, '2o': 2, '2a': 2,
  terceiro: 3, terceira: 3, tres: 3, '3': 3, '3o': 3, '3a': 3,
  quarto: 4, quarta: 4, quatro: 4, '4': 4,
  quinto: 5, quinta: 5, cinco: 5, '5': 5,
  sexto: 6, sexta: 6, seis: 6, '6': 6,
};

/** Letreiro dito ou digitado: "875A-10", "875 a 10", "8000", "N137-11". */
const LINHA = /\b(n?\d{3,4})\s?([a-z])?(?:\s?(?:-|traco|tracinho)\s?(\d{1,2}))?\b/;

export function extrairLinha(t: string): string | undefined {
  // Códigos de ponto têm 6 a 10 dígitos e não são linhas.
  const semPonto = t.replace(/\b\d{6,10}\b/g, ' ');
  const m = LINHA.exec(semPonto);
  if (!m) return undefined;
  return (m[1] + (m[2] ?? '') + (m[3] ? '-' + m[3] : '')).toUpperCase();
}

function extrairPonto(t: string): number | undefined {
  const m = /\b(\d{6,10})\b/.exec(t);
  return m ? Number(m[1]) : undefined;
}

function depoisDe(t: string, re: RegExp): string {
  const m = re.exec(t);
  return m ? t.slice(m.index + m[0].length).replace(/^(o|a|os|as|do|da|de|meu|minha)\s+/, '').trim() : '';
}

export function interpretar(texto: string): Comando {
  const t = normalizar(texto);
  if (!t) return { tipo: 'pergunta', texto: '' };

  if (/^(sim|s|isso|isso mesmo|confirmo|confirmar|pode|pode sim|ok|certo|claro|quero|e esse|esse mesmo|correto)$/.test(t)) return { tipo: 'sim' };
  if (/^(nao|n|nao quero|cancela|cancelar|deixa|deixa pra la|esquece|errado|nenhum)$/.test(t)) return { tipo: 'nao' };
  if (/^(ajuda|socorro|comandos)$|\b(o que (voce|vc) (faz|pode fazer|sabe)|como (funciona|usar|eu uso)|quais (sao os )?comandos)\b/.test(t)) return { tipo: 'ajuda' };
  if (/^(repete|repetir|repita|de novo|fala de novo|repete por favor)$|\b(o que (voce|vc) disse|nao entendi o aviso)\b/.test(t)) return { tipo: 'repetir' };
  if (/\b(embarquei|ja embarquei|entrei no onibus|peguei o onibus|estou no onibus|to no onibus|subi no onibus)\b/.test(t)) return { tipo: 'embarquei' };
  if (/\b(silencio|silenciar|fica quiet[ao]|cala a boca|sem voz|modo mudo|parar de falar|para de falar|desligar a voz|desliga a voz)\b/.test(t)) return { tipo: 'silenciar' };
  if (/\b(volta(r)? a falar|ativar a voz|ativa a voz|ligar a voz|liga a voz|pode falar)\b/.test(t)) return { tipo: 'falar' };
  if (/\b(parar|pare|para|encerrar|encerra|cancelar|cancela|terminar|termina|desligar|desliga)\b.*\b(acompanhamento|acompanhar|avisos?|monitoramento)\b|^(parar|encerrar|desisti|nao vou mais|vou desistir)$/.test(t)) return { tipo: 'parar' };
  if (/\b(camera|letreiro|conferir o onibus|conferir onibus|e esse o (meu )?onibus|esse e o meu onibus|qual onibus (e esse|chegou))\b/.test(t)) return { tipo: 'conferir-camera' };
  if (/\b(perto de mim|perto daqui|aqui perto|onde estou|mais proximo|minha localizacao|usar (o )?gps|usar (a )?localizacao|localizacao)\b/.test(t)) return { tipo: 'perto' };
  if (/\b(trocar|mudar|outro|escolher outro) (de )?ponto\b/.test(t)) return { tipo: 'trocar-ponto' };

  if (/\b(quais|meus|listar|lista|mostrar|mostra|ver)\b.*\b(favoritos|trajetos)\b/.test(t)) return { tipo: 'listar-favoritos' };
  if (/\b(remover|remove|apagar|apaga|tirar|tira|excluir|exclui|deletar)\b.*\b(favoritos?|trajetos?)\b/.test(t)) {
    const alvo = depoisDe(t, /\b(favoritos?|trajetos?)\b/).replace(/^(de |do |da )/, '').trim();
    const linha = extrairLinha(t);
    return { tipo: 'remover-favorito', alvo: alvo || linha || undefined };
  }
  if (/\b(salvar|salva|salve|favoritar|favorita|guardar|guarda|adicionar|adiciona|coloca|colocar)\b.*\b(favoritos?|trajetos?)\b|^(favoritar|salvar trajeto|salvar)$/.test(t)) {
    const apelido = depoisDe(t, /\b(como|com o nome( de)?|chamado|com apelido( de)?)\s+/);
    return { tipo: 'salvar-favorito', apelido: apelido || undefined };
  }
  const favorito = /^(?:ir (?:para|pro|pra|ao|a)|vou (?:para|pro|pra|ao)|usar (?:o )?(?:favorito|trajeto)|abrir (?:o )?(?:favorito|trajeto)|trajeto|favorito)\s+(.+)$/.exec(t);
  if (favorito && !extrairLinha(favorito[1])) return { tipo: 'usar-favorito', alvo: favorito[1].replace(/^(o|a|do|da)\s+/, '').trim() };

  const escolha = /^(?:o |a |no |na |opcao |numero |ponto |linha )?(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|um|uma|dois|duas|tres|quatro|cinco|seis|[1-6](?:o|a)?)(?: ponto| opcao| linha| da lista)?$/.exec(t);
  if (escolha) return { tipo: 'escolher', indice: ORDINAIS[escolha[1]] ?? 1 };

  const linha = extrairLinha(t);
  const ponto = extrairPonto(t);
  const querPegar = /\b(acompanhar|acompanha|acompanhe|avisar|avisa|avise|monitorar|monitora|pegar|pego|quero|vou pegar|esperar|espero|estou esperando|to esperando|aguardar|aguardando)\b/.test(t);
  if ((linha || ponto) && querPegar) return { tipo: 'acompanhar', linha, ponto };
  if (!linha && /\b(quanto (tempo )?falta|quando (ele )?(chega|vem|passa)|ta chegando|esta chegando|ja vem|onde (esta|ta) (o )?(meu )?onibus|que horas (ele )?(chega|passa)|falta muito|demora)\b/.test(t)) return { tipo: 'quanto-falta' };

  const pontoBusca = /^(?:estou no ponto|to no ponto|meu ponto e|ponto|buscar ponto|procurar ponto|buscar|procurar|estou na|estou no|to na|to no)\s+(.{2,80})$/.exec(t);
  if (pontoBusca && !linha) {
    const termo = pontoBusca[1].trim();
    return /^\d{6,10}$/.test(termo) ? { tipo: 'acompanhar', ponto: Number(termo) } : { tipo: 'buscar-ponto', termo };
  }
  if (ponto && !linha) return { tipo: 'acompanhar', ponto };

  return { tipo: 'pergunta', texto: texto.trim() };
}

/** Escolhe o favorito pelo apelido, pela linha ou pelo nome do ponto (o mais parecido). */
export function acharFavorito<T extends { apelido?: string | null; linha: string; ponto_nome: string }>(lista: T[], alvo: string): T[] {
  const a = normalizar(alvo);
  if (!a) return [];
  const linha = extrairLinha(a);
  const exatos = lista.filter((f) => normalizar(f.apelido ?? '') === a);
  if (exatos.length) return exatos;
  if (linha) {
    const porLinha = lista.filter((f) => f.linha.toUpperCase() === linha || f.linha.toUpperCase().startsWith(linha + '-'));
    if (porLinha.length) return porLinha;
  }
  return lista.filter((f) => {
    const ap = normalizar(f.apelido ?? '');
    const nome = normalizar(f.ponto_nome);
    return (ap && (ap.includes(a) || a.includes(ap))) || nome.includes(a);
  });
}

export const AJUDA_EMBARQUE =
  'Você pode dizer, por exemplo: "pontos perto de mim", "estou no ponto Avenida Paulista", "quero pegar o 875A", ' +
  '"quanto falta", "repetir", "salvar nos favoritos como trabalho", "ir para o trabalho", "conferir o letreiro", ' +
  '"embarquei" ou "parar o acompanhamento". Também pode fazer perguntas sobre o transporte.';
