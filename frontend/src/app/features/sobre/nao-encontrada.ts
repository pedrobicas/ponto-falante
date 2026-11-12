import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icone } from '../../shared/icone';

@Component({
  selector: 'pf-nao-encontrada',
  imports: [RouterLink, Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="vazio" /> Erro 404</p>
        <h1>Página não encontrada</h1>
        <p class="lead">Não achamos esta página. Ela pode ter mudado de lugar.</p>
      </div>
    </section>
    <div class="miolo">
      <a routerLink="/" class="botao botao--primario botao--grande"><pf-icone nome="casa" /> Voltar ao início</a>
    </div>
  `,
})
export class NaoEncontrada {}
