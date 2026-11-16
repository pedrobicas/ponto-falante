const CHAVE = 'pf.dispositivo';
let emMemoria: string | null = null;

/**
 * Identificador aleatório deste aparelho (32 caracteres hexadecimais). Não é dado pessoal: não sai de outro lugar
 * além do navegador e o servidor guarda só o hash dele. Sem armazenamento local, vale até fechar a aba.
 */
export function identificadorDoAparelho(): string {
  try {
    const salvo = localStorage.getItem(CHAVE);
    if (salvo && /^[a-f0-9]{32,64}$/.test(salvo)) return salvo;
  } catch {
    /* armazenamento bloqueado */
  }
  if (emMemoria) return emMemoria;
  const novo = gerar();
  emMemoria = novo;
  try {
    localStorage.setItem(CHAVE, novo);
  } catch {
    /* segue só em memória */
  }
  return novo;
}

/** Depois de apagar os dados, o aparelho passa a ser outro para o servidor. */
export function trocarIdentificador(): void {
  emMemoria = null;
  try {
    localStorage.removeItem(CHAVE);
  } catch {
    /* ignora */
  }
}

function gerar(): string {
  const bytes = new Uint8Array(16);
  const c = globalThis.crypto;
  if (c?.getRandomValues) c.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}
