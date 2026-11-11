/** Acesso seguro ao localStorage (pode lançar em janela privada ou com dados bloqueados). */
export function lerJson<T>(chave: string): T | null {
  try {
    const bruto = localStorage.getItem(chave);
    return bruto ? (JSON.parse(bruto) as T) : null;
  } catch {
    return null;
  }
}

export function gravarJson(chave: string, valor: unknown): void {
  try {
    localStorage.setItem(chave, JSON.stringify(valor));
  } catch {
    /* sem armazenamento: o app continua funcionando */
  }
}
