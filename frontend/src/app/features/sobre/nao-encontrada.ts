import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icone } from '../../shared/icone';

@Component({
  selector: 'pf-nao-encontrada',
  imports: [RouterLink, Icone],
  template: `
    <div class="pagina">
      <header class="cabecalho">
        <p class="sobretitulo">Erro 404</p>
        <h1>Este ponto não existe no mapa</h1>
        <p class="cabecalho__apoio">A página pode ter mudado de lugar ou o endereço foi digitado errado.</p>
      </header>
      <div class="grupo__acoes">
        <a routerLink="/" class="botao botao--primario botao--grande"><pf-icone nome="casa" /> Voltar ao início</a>
        <a routerLink="/busca" class="botao botao--contorno botao--grande"><pf-icone nome="busca" /> Buscar um ponto</a>
      </div>
    </div>
  `,
})
export class NaoEncontrada {}
