import { Component, inject } from '@angular/core';
import { Preferencias, PreferencesService, TamanhoFonte, Tema } from '../../core/preferences.service';
import { SpeechService } from '../../core/speech.service';
import { Icone } from '../../shared/icone';

@Component({
  selector: 'pf-acessibilidade',
  imports: [Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="ajustes" /> Ajustes</p>
        <h1>Acessibilidade</h1>
        <p class="lead">Ajuste o tamanho das letras, as cores e a voz. Suas escolhas ficam salvas neste aparelho.</p>
      </div>
    </section>

    <div class="miolo">
      <fieldset class="grupo">
        <legend><pf-icone nome="letras" /> Tamanho das letras</legend>
        <div class="escolhas escolhas--tres">
          @for (o of fontes; track o.valor) {
            <label class="escolha">
              <input type="radio" name="fonte" [value]="o.valor" [checked]="p().tamanhoFonte === o.valor" (change)="mudar({ tamanhoFonte: o.valor })" />
              <span class="escolha__corpo">
                <span class="escolha__amostra" [style.font-size.rem]="o.amostra" aria-hidden="true">Aa</span>
                <span class="escolha__texto">{{ o.texto }}</span>
                <pf-icone class="escolha__marca" nome="certo" />
              </span>
            </label>
          }
        </div>
      </fieldset>

      <fieldset class="grupo">
        <legend><pf-icone nome="paleta" /> Cores</legend>
        <div class="escolhas">
          @for (o of temas; track o.valor) {
            <label class="escolha">
              <input type="radio" name="tema" [value]="o.valor" [checked]="p().tema === o.valor" (change)="mudar({ tema: o.valor })" />
              <span class="escolha__corpo escolha__corpo--linha">
                <span class="amostra amostra--{{ o.valor }}" aria-hidden="true"><i></i><i></i></span>
                <span class="escolha__texto">{{ o.texto }}</span>
                <pf-icone class="escolha__marca" nome="certo" />
              </span>
            </label>
          }
        </div>
      </fieldset>

      <fieldset class="grupo">
        <legend><pf-icone nome="volume" /> Voz</legend>
        <label for="velocidade" class="rotulo">Velocidade da voz: <strong>{{ velocidadeTexto() }}</strong></label>
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
            <pf-icone nome="volume" /> Testar a voz
          </button>
        </div>
        @if (!fala.suportaSintese) {
          <p class="ajuda">Este navegador não tem voz sintetizada.</p>
        }
        <label class="interruptor">
          <input type="checkbox" [checked]="p().anunciarAuto" (change)="mudar({ anunciarAuto: $any($event.target).checked })" />
          <span class="interruptor__trilho" aria-hidden="true"></span>
          <span>Anunciar automaticamente os ônibus quando o primeiro mudar</span>
        </label>
        <label class="interruptor">
          <input type="checkbox" [checked]="p().lerRespostaAuto" (change)="mudar({ lerRespostaAuto: $any($event.target).checked })" />
          <span class="interruptor__trilho" aria-hidden="true"></span>
          <span>Ler as respostas do assistente em voz alta</span>
        </label>
      </fieldset>

      <fieldset class="grupo">
        <legend><pf-icone nome="brilho" /> Movimento</legend>
        <label class="interruptor">
          <input type="checkbox" [checked]="p().reduzirMovimento" (change)="mudar({ reduzirMovimento: $any($event.target).checked })" />
          <span class="interruptor__trilho" aria-hidden="true"></span>
          <span>Reduzir animações e movimentos</span>
        </label>
        <p class="ajuda">Se o seu aparelho já pede menos movimento, o aplicativo respeita isso mesmo sem marcar aqui.</p>
      </fieldset>

      <div class="acoes">
        <button type="button" class="botao" (click)="prefs.restaurar()"><pf-icone nome="atualizar" /> Voltar ao padrão</button>
      </div>
      <p class="status-salvo" role="status">{{ salvo }}</p>
    </div>
  `,
})
export class Acessibilidade {
  protected readonly prefs = inject(PreferencesService);
  protected readonly fala = inject(SpeechService);
  protected readonly p = this.prefs.prefs;
  protected salvo = '';

  protected readonly fontes: { valor: TamanhoFonte; texto: string; amostra: number }[] = [
    { valor: 'normal', texto: 'Normal', amostra: 1.3 },
    { valor: 'grande', texto: 'Grande', amostra: 1.7 },
    { valor: 'muito-grande', texto: 'Muito grande', amostra: 2.1 },
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
