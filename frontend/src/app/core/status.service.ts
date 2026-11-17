import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { Status } from './models';

export type SituacaoAssistente = 'verificando' | 'disponivel' | 'parcial' | 'indisponivel';

/** Estado dos serviços (SPTrans, assistente, boletim), consultado uma vez e compartilhado pelas telas. */
@Injectable({ providedIn: 'root' })
export class StatusService {
  private readonly api = inject(ApiService);
  readonly status = signal<Status | null>(null);
  readonly falhou = signal(false);
  private pedido: Promise<void> | null = null;
  private sequencia = 0;

  /** Situação real do assistente: a IA local pode estar fora e os horários em tempo real continuarem. */
  readonly assistente = computed<SituacaoAssistente>(() => {
    // Um status antigo não deve continuar anunciando a IA como disponível
    // quando a verificação mais recente falhou.
    if (this.falhou()) return 'indisponivel';
    const s = this.status();
    if (!s) return 'verificando';
    if (s.assistente === 'DISPONIVEL') return 'disponivel';
    return s.assistente_tempo_real ? 'parcial' : 'indisponivel';
  });

  readonly demo = computed(() => this.status()?.sptrans === 'DEMO');

  carregar(forcar = false): Promise<void> {
    if (this.pedido && !forcar) return this.pedido;
    const sequencia = ++this.sequencia;
    this.pedido = firstValueFrom(this.api.status())
      .then((s) => {
        if (sequencia !== this.sequencia) return;
        this.status.set(s);
        this.falhou.set(false);
      })
      .catch(() => {
        if (sequencia !== this.sequencia) return;
        this.status.set(null);
        this.falhou.set(true);
        this.pedido = null;
      });
    return this.pedido;
  }
}
