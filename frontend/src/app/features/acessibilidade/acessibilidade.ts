import { Component, inject } from '@angular/core';
import { Preferencias, PreferencesService, TamanhoFonte, Tema } from '../../core/preferences.service';
import { SpeechService } from '../../core/speech.service';

@Component({
  selector: 'pf-acessibilidade',
  template: `
    <h1>Acessibilidade</h1>
    <p class="lead">Ajuste o tamanho das letras, as cores e a voz. Suas escolhas ficam salvas neste aparelho.</p>

    <fieldset class="cartao">
      <legend>Tamanho das letras</legend>
      @for (o of fontes; track o.valor) {
        <label class="opcao">
          <input type="radio" name="fonte" [value]="o.valor" [checked]="p().tamanhoFonte === o.valor" (change)="mudar({ tamanhoFonte: o.valor })" />
          <span>{{ o.texto }}</span>
        </label>
      }
    </fieldset>

    <fieldset class="cartao">
      <legend>Cores</legend>
      @for (o of temas; track o.valor) {
        <label class="opcao">
          <input type="radio" name="tema" [value]="o.valor" [checked]="p().tema === o.valor" (change)="mudar({ tema: o.valor })" />
          <span>{{ o.texto }}</span>
        </label>
      }
    </fieldset>

    <fieldset class="cartao">
      <legend>Voz</legend>
      <label for="velocidade" class="rotulo">Velocidade da voz: {{ velocidadeTexto() }}</label>
      <input
        id="velocidade"
        type="range"
        min="0.5"
        max="1.4"
        step="0.1"
        [value]="p().velocidadeVoz"
        [attr.aria-valuetext]="velocidadeTexto()"
        (input)="mudar({ velocidadeVoz: +$any($event.target).value })"
      />
      <div class="acoes">
        <button type="button" class="botao" (click)="testar()" [disabled]="!fala.suportaSintese">
          <span aria-hidden="true">🔊</span> Testar a voz
        </button>
      </div>
      @if (!fala.suportaSintese) {
        <p class="ajuda">Este navegador não tem voz sintetizada.</p>
      }
      <label class="opcao">
        <input type="checkbox" [checked]="p().anunciarAuto" (change)="mudar({ anunciarAuto: $any($event.target).checked })" />
        <span>Anunciar automaticamente os ônibus quando o primeiro mudar</span>
      </label>
      <label class="opcao">
        <input type="checkbox" [checked]="p().lerRespostaAuto" (change)="mudar({ lerRespostaAuto: $any($event.target).checked })" />
        <span>Ler as respostas do assistente em voz alta</span>
      </label>
    </fieldset>

    <fieldset class="cartao">
      <legend>Movimento</legend>
      <label class="opcao">
        <input type="checkbox" [checked]="p().reduzirMovimento" (change)="mudar({ reduzirMovimento: $any($event.target).checked })" />
        <span>Reduzir animações e movimentos</span>
      </label>
      <p class="ajuda">Se o seu aparelho já pede menos movimento, o aplicativo respeita isso mesmo sem marcar aqui.</p>
    </fieldset>

    <div class="acoes">
      <button type="button" class="botao" (click)="prefs.restaurar()">Voltar ao padrão</button>
    </div>
    <p class="status-salvo" role="status">{{ salvo }}</p>
  `,
})
export class Acessibilidade {
  protected readonly prefs = inject(PreferencesService);
  protected readonly fala = inject(SpeechService);
  protected readonly p = this.prefs.prefs;
  protected salvo = '';

  protected readonly fontes: { valor: TamanhoFonte; texto: string }[] = [
    { valor: 'normal', texto: 'Normal' },
    { valor: 'grande', texto: 'Grande' },
    { valor: 'muito-grande', texto: 'Muito grande' },
  ];
  protected readonly temas: { valor: Tema; texto: string }[] = [
    { valor: 'auto', texto: 'Automático (segue o seu aparelho)' },
    { valor: 'alto-escuro', texto: 'Alto contraste escuro (amarelo no preto)' },
    { valor: 'alto-claro', texto: 'Alto contraste claro (preto no branco)' },
  ];

  protected velocidadeTexto(): string {
    const v = this.p().velocidadeVoz;
    return v < 0.8 ? `${v.toFixed(1)} (devagar)` : v > 1.1 ? `${v.toFixed(1)} (rápida)` : `${v.toFixed(1)} (normal)`;
  }

  protected mudar(parcial: Partial<Preferencias>): void {
    this.prefs.atualizar(parcial);
    this.salvo = 'Ajuste salvo.';
  }

  protected testar(): void {
    this.fala.falar('Ônibus 8000-10, Lapa, previsto em 3 minutos.');
  }
}
