import { Injectable, signal } from '@angular/core';
import { ContextoChat, RespostaChat } from './models';

export interface Mensagem {
  id: number;
  pergunta: string;
  estado: 'enviando' | 'ok' | 'erro';
  resposta?: RespostaChat;
  erro?: string;
  contexto?: ContextoChat | null;
}

/** Histórico da sessão em memória: sobrevive à navegação, sem gravar dados em disco. */
@Injectable({ providedIn: 'root' })
export class ConversaService {
  readonly mensagens = signal<Mensagem[]>([]);
  readonly contexto = signal<ContextoChat | null>(null);
  contador = 0;
  limpar(): void { this.mensagens.set([]); this.contexto.set(null); }
}
