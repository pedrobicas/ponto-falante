import { Component, input, output } from '@angular/core';
import { Icone } from './icone';

/** Aviso de erro/indisponibilidade. Anunciado por leitores de tela (role=alert). */
@Component({
  selector: 'pf-erro',
  imports: [Icone],
  template: `
    <div class="aviso aviso--{{ tom() }}" role="alert">
      <pf-icone class="aviso__icone" [nome]="tom() === 'erro' ? 'alerta' : 'info'" />
      <div class="aviso__corpo">
        <p class="aviso__titulo">{{ titulo() }}</p>
        <p>{{ mensagem() }}</p>
        <div class="aviso__acoes">
          @if (tentarNovamente()) {
            <button type="button" class="botao botao--contorno" (click)="repetir.emit()">
              <pf-icone nome="atualizar" /> Tentar de novo
            </button>
          }
          <ng-content />
        </div>
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
