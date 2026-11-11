/** Texto de minutos: nunca diz "chegou"; é sempre uma previsão. */
export function textoMinutos(minutos: number): string {
  if (minutos <= 0) return 'previsto para agora';
  if (minutos === 1) return 'previsto em 1 minuto';
  return `previsto em ${minutos} minutos`;
}

/** "2026-11-12" -> "12/11/2026" (sem converter fuso). */
export function formatarData(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  return m ? `${m[3]}/${m[2]}/${m[1]}` : (iso ?? '');
}

export function formatarDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso ?? '';
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Sao_Paulo',
  });
}

export function horaCurta(d: Date): string {
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
