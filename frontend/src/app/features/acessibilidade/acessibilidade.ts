import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Preferencias, PreferencesService, TamanhoFonte, Tema } from '../../core/preferences.service';
import { SpeechService } from '../../core/speech.service';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';

@Component({
  selector: 'pf-acessibilidade',
  imports: [RouterLink, Icone, Letreiro],
  template: `
    <div class="pagina ajustes">
      <header class="cabecalho">
        <p class="sobretitulo">Acessibilidade</p>
        <h1>Ajustes</h1>
        <p class="cabecalho__apoio">Seu jeito de ver e ouvir. As alterações são salvas automaticamente.</p>
      </header>

      <div class="ajustes__grade">
        <div class="ajustes__opcoes">
          <details class="ajuste-secao" open><summary>Tamanho das letras</summary><fieldset class="grupo"><legend class="vo">Tamanho das letras</legend>
            <div class="escolhas escolhas--quatro">
              @for (o of fontes; track o.valor) {
                <label class="escolha">
                  <input type="radio" name="fonte" [value]="o.valor" [checked]="p().tamanhoFonte === o.valor" (change)="mudar({ tamanhoFonte: o.valor }, 'Letras: ' + o.texto)" />
                  <span class="escolha__corpo">
                    <span class="escolha__amostra" [style.font-size.rem]="o.amostra" aria-hidden="true">Aa</span>
                    <span class="escolha__texto">{{ o.texto }}</span>
                  </span>
                </label>
              }
            </div>
            <label class="interruptor">
              <input type="checkbox" role="switch" [checked]="p().espacamento" (change)="mudar({ espacamento: $any($event.target).checked }, 'Espaçamento ajustado')" />
              <span class="interruptor__trilho" aria-hidden="true"></span>
              <span>Mais espaço entre letras e linhas</span>
            </label>
          </fieldset></details>

          <details class="ajuste-secao"><summary>Cores e contraste</summary><fieldset class="grupo"><legend class="vo">Cores e contraste</legend>
            <div class="escolhas escolhas--temas">
              @for (o of temas; track o.valor) {
                <label class="escolha">
                  <input type="radio" name="tema" [value]="o.valor" [checked]="p().tema === o.valor" (change)="mudar({ tema: o.valor }, 'Cores: ' + o.texto)" />
                  <span class="escolha__corpo escolha__corpo--tema">
                    <span class="miniatura miniatura--{{ o.valor }}" aria-hidden="true"><i></i><b></b><u></u></span>
                    <span class="escolha__texto">{{ o.texto }}<span class="escolha__sub">{{ o.sub }}</span></span>
                  </span>
                </label>
              }
            </div>
          </fieldset></details>

          <details class="ajuste-secao"><summary>Voz</summary><fieldset class="grupo"><legend class="vo">Voz</legend>
            <div class="campo">
              <label for="velocidade" class="campo__rotulo">Velocidade da fala <strong>{{ velocidadeTexto() }}</strong></label>
              <div class="regua">
                <span aria-hidden="true">devagar</span>
                <input
                  id="velocidade"
                  type="range"
                  min="0.5"
                  max="1.4"
                  step="0.1"
                  [value]="p().velocidadeVoz"
                  [attr.aria-valuetext]="velocidadeTexto()"
                  (change)="mudar({ velocidadeVoz: +$any($event.target).value }, 'Velocidade ' + velocidadeTexto())"
                  (input)="prefs.atualizar({ velocidadeVoz: +$any($event.target).value })"
                />
                <span aria-hidden="true">rápida</span>
              </div>
            </div>
            @if (fala.vozes().length > 1) {
              <div class="campo">
                <label for="voz" class="campo__rotulo">Voz</label>
                <select id="voz" class="seletor" (change)="mudar({ voz: $any($event.target).value }, 'Voz escolhida')">
                  <option value="" [selected]="!p().voz">Automática (português do aparelho)</option>
                  @for (v of fala.vozes(); track v.uri) {
                    <option [value]="v.uri" [selected]="p().voz === v.uri">{{ v.nome }}</option>
                  }
                </select>
              </div>
            }
            <div class="grupo__acoes">
              <button type="button" class="botao botao--contorno" (click)="testar()" [disabled]="!fala.suportaSintese">
                <pf-icone nome="volume" /> Testar a voz
              </button>
            </div>
            @if (!fala.suportaSintese) {
              <p class="ajuda">Este navegador não tem voz sintetizada. Todo o conteúdo continua disponível em texto.</p>
            }
            <label class="interruptor">
              <input type="checkbox" role="switch" [checked]="p().anunciarAuto" (change)="mudar({ anunciarAuto: $any($event.target).checked }, 'Anúncio automático ajustado')" />
              <span class="interruptor__trilho" aria-hidden="true"></span>
              <span>Falar sozinho quando o próximo ônibus mudar</span>
            </label>
            <label class="interruptor">
              <input type="checkbox" role="switch" [checked]="p().lerRespostaAuto" (change)="mudar({ lerRespostaAuto: $any($event.target).checked }, 'Leitura de respostas ajustada')" />
              <span class="interruptor__trilho" aria-hidden="true"></span>
              <span>Ler as respostas do assistente em voz alta</span>
            </label>
          </fieldset></details>

          <details class="ajuste-secao"><summary>Movimento</summary><fieldset class="grupo"><legend class="vo">Movimento</legend>
            <label class="interruptor">
              <input type="checkbox" role="switch" [checked]="p().reduzirMovimento" (change)="mudar({ reduzirMovimento: $any($event.target).checked }, 'Movimento ajustado')" />
              <span class="interruptor__trilho" aria-hidden="true"></span>
              <span>Reduzir animações</span>
            </label>
            <p class="ajuda">Se o aparelho já pede menos movimento, o aplicativo segue isso mesmo com esta opção desligada.</p>
          </fieldset></details>

          <div class="grupo__acoes">
            <button type="button" class="botao botao--contorno" (click)="restaurar()"><pf-icone nome="atualizar" /> Voltar ao padrão</button>
            <a class="botao-texto" routerLink="/sobre">Sobre, dados e privacidade</a>
          </div>
          <p class="vo" role="status">{{ salvo() }}</p>
        </div>

        <aside class="previa" aria-label="Prévia dos ajustes">
          <p class="previa__titulo" aria-hidden="true">Prévia dos ajustes</p>
          <div class="previa__quadro" aria-hidden="true">
            <div class="previa__linha">
              <pf-letreiro codigo="8000-10" />
              <span class="previa__destino">Lapa</span>
              <span class="previa__min"><b>3</b> min</span>
            </div>
            <div class="previa__linha">
              <pf-letreiro codigo="2600-10" />
              <span class="previa__destino">Circular Paulista</span>
              <span class="previa__min"><b>9</b> min</span>
            </div>
          </div>
          <p class="previa__texto">Exemplo ilustrativo. Linha 8000-10, destino Lapa, previsto em 3 minutos.</p>
        </aside>
      </div>
    </div>
  `,
})
export class Acessibilidade {
  protected readonly prefs = inject(PreferencesService);
  protected readonly fala = inject(SpeechService);
  protected readonly p = this.prefs.prefs;
  protected readonly salvo = signal('');

  protected readonly fontes: { valor: TamanhoFonte; texto: string; amostra: number }[] = [
    { valor: 'normal', texto: 'Normal', amostra: 1.1 },
    { valor: 'grande', texto: 'Grande', amostra: 1.4 },
    { valor: 'muito-grande', texto: 'Maior', amostra: 1.7 },
    { valor: 'maximo', texto: 'Máximo', amostra: 2 },
  ];
  protected readonly temas: { valor: Tema; texto: string; sub: string }[] = [
    { valor: 'auto', texto: 'Automático', sub: 'segue o aparelho' },
    { valor: 'claro', texto: 'Claro', sub: 'fundo papel' },
    { valor: 'escuro', texto: 'Escuro', sub: 'menos brilho' },
    { valor: 'alto-claro', texto: 'Alto contraste claro', sub: 'preto no branco' },
    { valor: 'alto-escuro', texto: 'Alto contraste escuro', sub: 'amarelo no preto' },
  ];

  protected velocidadeTexto(): string {
    const v = this.p().velocidadeVoz;
    const n = v.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return v < 0.8 ? `${n} (devagar)` : v > 1.1 ? `${n} (rápida)` : `${n} (normal)`;
  }

  protected mudar(parcial: Partial<Preferencias>, aviso: string): void {
    this.prefs.atualizar(parcial);
    this.salvo.set(`${aviso}. Salvo.`);
  }

  protected restaurar(): void {
    this.prefs.restaurar();
    this.salvo.set('Ajustes de volta ao padrão.');
  }

  protected testar(): void {
    this.fala.falar('Linha 8000-10, destino Lapa, previsto em 3 minutos.');
  }
}
