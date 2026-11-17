import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { EmbarqueApiService } from '../../core/embarque-api.service';
import { ConferenciaLetreiro, EstadoVisao } from '../../core/embarque.models';
import { EmbarqueStore } from '../../core/embarque.store';
import { ErroApi } from '../../core/models';
import { Icone } from '../../shared/icone';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Livre = any;

/** Lado máximo do quadro enviado ao modelo: suficiente para ler o letreiro, leve para o 4G. */
export const LADO_MAXIMO_PX = 1280;
/** Fotos por toque em "Conferir": o letreiro de SP alterna número e destino, então uma foto só costuma pegar o destino. */
export const TENTATIVAS = 3;

/**
 * Conferência do letreiro pela câmera. A foto vai ao backend, que a repassa ao modelo de visão da equipe (YOLO11n
 * treinado com ônibus de São Paulo + OCR, pasta visao/). Sem o modelo ligado, a tela diz isso e NÃO abre a câmera nem
 * mostra resultado algum. Quando a foto não dá leitura segura, tira outra sozinha (até TENTATIVAS) antes de responder.
 */
@Component({
  selector: 'pf-conferir-letreiro',
  imports: [Icone],
  template: `
    <section class="camera" aria-labelledby="camera-titulo">
      <div class="camera__topo">
        <h3 id="camera-titulo" tabindex="-1" #titulo><pf-icone nome="onibus" /> Conferir o letreiro pela câmera</h3>
        <button type="button" class="botao-icone" (click)="fechar.emit()"><pf-icone nome="fechar" /><span class="vo">Fechar conferência pela câmera</span></button>
      </div>

      @if (estado() === null) {
        <p class="ajuda" role="status">Verificando se o reconhecimento do letreiro está disponível…</p>
      } @else if (!estado()!.conectada) {
        <div class="camera__indisponivel" role="status">
          <pf-icone nome="info" />
          <div>
            <p><strong>Indisponível agora.</strong> {{ estado()!.mensagem }}</p>
            <p class="ajuda">Com o reconhecimento ligado, esta tela lê o letreiro da frente do ônibus com o modelo de visão da equipe e compara com a linha {{ linha() }}. Nenhuma foto é guardada.</p>
          </div>
        </div>
      } @else {
        <p class="ajuda">Aponte a câmera para o letreiro da frente do ônibus e toque em Conferir. Se a primeira foto não der para ler, o aplicativo tira até {{ tentativas }} fotos seguidas; mantenha a câmera apontada. As fotos são usadas só nesta conferência e não são guardadas.</p>
        @if (!aberta()) {
          <button type="button" class="botao botao--primario botao--grande" (click)="abrir()"><pf-icone nome="busca" /> Abrir a câmera</button>
        }
        <video #video class="camera__video" [class.camera__video--oculto]="!aberta()" playsinline muted aria-label="Imagem da câmera"></video>
        @if (aberta()) {
          <div class="camera__acoes">
            <button type="button" class="botao botao--primario botao--grande" (click)="conferir()" [disabled]="conferindo()">
              <pf-icone nome="certo-circulo" /> {{ conferindo() ? 'Conferindo…' : 'Conferir letreiro' }}
            </button>
            <button type="button" class="botao botao--contorno" (click)="pararCamera()">Fechar a câmera</button>
          </div>
        }
        <p class="ajuda" role="status">{{ progresso() }}</p>
        @if (resultado(); as r) {
          <div class="camera__resultado" [attr.data-resultado]="r.resultado" role="alert">
            <p class="camera__veredito">{{ rotulo(r) }}</p>
            <p>{{ r.frase_falada }}</p>
            <p class="ajuda">Leitura do modelo {{ r.modelo }}{{ r.confianca != null ? ', confiança ' + porcento(r.confianca) : '' }}.</p>
          </div>
        }
      }
      @if (erro()) {
        <p class="aviso-linha" role="alert"><pf-icone nome="alerta" /> <span>{{ erro() }}</span></p>
      }
    </section>
  `,
})
export class ConferirLetreiro {
  private readonly api = inject(EmbarqueApiService);
  private readonly store = inject(EmbarqueStore);
  private readonly doc = inject(DOCUMENT);
  readonly linha = input.required<string>();
  readonly sessao = input<string | null>(null);
  readonly fechar = output<void>();

  protected readonly estado = signal<EstadoVisao | null>(null);
  protected readonly aberta = signal(false);
  protected readonly conferindo = signal(false);
  protected readonly resultado = signal<ConferenciaLetreiro | null>(null);
  protected readonly erro = signal('');
  protected readonly progresso = signal('');
  protected readonly tentativas = TENTATIVAS;
  /** Intervalo entre as fotos de uma conferência (o letreiro troca de número para destino a cada poucos segundos). */
  esperaEntreFotosMs = 1200;
  private readonly video = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly titulo = viewChild<ElementRef<HTMLElement>>('titulo');
  private stream: Livre = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.pararCamera());
    void this.verificar();
    queueMicrotask(() => this.titulo()?.nativeElement.focus());
  }

  private async verificar(): Promise<void> {
    try {
      this.estado.set(await firstValueFrom(this.api.estadoVisao()));
    } catch {
      this.estado.set({ conectada: false, mensagem: 'Não consegui verificar o reconhecimento agora. Confirme a linha com o motorista.' });
    }
  }

  protected async abrir(): Promise<void> {
    this.erro.set('');
    const midia = (this.doc.defaultView as Livre)?.navigator?.mediaDevices;
    if (!midia?.getUserMedia) {
      this.erro.set('Este navegador não dá acesso à câmera. Confirme a linha com o motorista.');
      return;
    }
    try {
      this.stream = await midia.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } }, audio: false });
      const v = this.video()?.nativeElement;
      if (v) {
        v.srcObject = this.stream;
        await v.play().catch(() => undefined);
      }
      this.aberta.set(true);
    } catch (e: Livre) {
      this.erro.set(e?.name === 'NotAllowedError'
        ? 'Sem permissão para usar a câmera. Você pode liberar nas configurações do navegador.'
        : 'Não consegui abrir a câmera. Confirme a linha com o motorista.');
    }
  }

  pararCamera(): void {
    try {
      this.stream?.getTracks?.().forEach((t: Livre) => t.stop());
    } catch {
      /* ignora */
    }
    this.stream = null;
    this.aberta.set(false);
  }

  protected async conferir(): Promise<void> {
    if (!this.video()?.nativeElement?.videoWidth) {
      this.erro.set('A câmera ainda está abrindo. Tente de novo em um instante.');
      return;
    }
    this.conferindo.set(true);
    this.erro.set('');
    this.resultado.set(null);
    try {
      let r: ConferenciaLetreiro | null = null;
      for (let i = 1; i <= TENTATIVAS && this.aberta(); i++) {
        if (i > 1) {
          this.progresso.set(`Não deu para ler ainda. Tirando outra foto, ${i} de ${TENTATIVAS}. Mantenha a câmera apontada.`);
          await new Promise((ok) => setTimeout(ok, this.esperaEntreFotosMs));
          if (!this.aberta()) break;
        }
        const foto = await this.capturar();
        if (!foto) throw new ErroApi(-1, 'Não consegui capturar a imagem. Tente de novo.');
        r = await firstValueFrom(this.api.conferirLetreiro(foto, this.linha(), this.sessao()));
        if (r.resultado !== 'INCONCLUSIVO') break;
      }
      if (r) {
        this.resultado.set(r);
        this.store.dizer(r.frase_falada, true);
      }
    } catch (e) {
      this.erro.set(e instanceof ErroApi ? e.message : 'Não consegui conferir agora. Confirme a linha com o motorista.');
    } finally {
      this.progresso.set('');
      this.conferindo.set(false);
    }
  }

  /** Um quadro da câmera em JPEG, reduzido para no máximo LADO_MAXIMO_PX. */
  protected async capturar(): Promise<Blob | null> {
    const v = this.video()?.nativeElement;
    if (!v || !v.videoWidth) return null;
    const escala = Math.min(1, LADO_MAXIMO_PX / Math.max(v.videoWidth, v.videoHeight));
    const canvas = this.doc.createElement('canvas');
    canvas.width = Math.round(v.videoWidth * escala);
    canvas.height = Math.round(v.videoHeight * escala);
    canvas.getContext('2d')?.drawImage(v, 0, 0, canvas.width, canvas.height);
    return new Promise<Blob | null>((ok) => canvas.toBlob(ok, 'image/jpeg', 0.85));
  }

  protected rotulo(r: ConferenciaLetreiro): string {
    switch (r.resultado) {
      case 'CONFERE': return `Parece ser a linha ${r.linha_esperada}`;
      case 'NUMERO_CONFERE': return 'Número confere, confirme o destino';
      case 'NAO_CONFERE': return `Atenção: parece ser outra linha${r.linha_lida ? ' (' + r.linha_lida + ')' : ''}`;
      default: return 'Não deu para ler o letreiro';
    }
  }

  protected porcento(c: number): string {
    return `${Math.round(c * 100)}%`;
  }
}
