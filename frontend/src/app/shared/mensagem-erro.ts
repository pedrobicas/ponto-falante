import { Component, input, output } from '@angular/core';
import { Icone } from './icone';

/** Caixa de erro/aviso amigável. Anunciada por leitores de tela (role=alert). */
@Component({
  selector: 'pf-erro',
  imports: [Icone],
  template: `
    <div class="caixa caixa--{{ tom() }}" role="alert">
      <p class="caixa__titulo">
        <pf-icone [nome]="tom() === 'erro' ? 'erro-circulo' : 'info'" />
        <span>{{ titulo() }}</span>
      </p>
      <p>{{ mensagem() }}</p>
      <div class="acoes">
        <ng-content />
        @if (tentarNovamente()) {
          <button type="button" class="botao" (click)="repetir.emit()">
            <pf-icone nome="atualizar" /> Tentar de novo
          </button>
        }
      </div>
    </div>
  `,
})
export class MensagemErro {
  readonly titulo = input('Não deu certo');
  readonly mensagem = input.required<string>();
  readonly tom = input<'erro' | 'calmo'>('erro');
  readonly tentarNovamente = input(true);
  readonly repetir = output<void>();
}
