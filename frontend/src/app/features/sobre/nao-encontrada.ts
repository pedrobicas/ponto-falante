import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'pf-nao-encontrada',
  imports: [RouterLink],
  template: `
    <h1>Página não encontrada</h1>
    <p class="lead">Não achamos esta página.</p>
    <a routerLink="/" class="botao botao--primario">Voltar ao início</a>
  `,
})
export class NaoEncontrada {}
