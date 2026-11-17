import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Origem } from '../../shared/origem';

@Component({
  selector: 'pf-sobre',
  imports: [RouterLink, Origem],
  template: `
    <div class="pagina sobre">
      <header class="cabecalho">
        <p class="sobretitulo">Sobre</p>
        <h1>Um ponto de ônibus que fala</h1>
        <p class="cabecalho__apoio">
          O Ponto Falante ajuda quem espera ônibus em São Paulo, sobretudo pessoas idosas e pessoas com deficiência visual:
          mostra os próximos ônibus previstos para um ponto e lê tudo em voz alta.
        </p>
      </header>

      <div class="artigo">
        <section class="artigo__secao" aria-labelledby="o-que-faz">
          <h2 id="o-que-faz">O que faz</h2>
          <ol class="itinerario">
            <li><strong>Previsões do ponto.</strong> Ônibus previstos, destino e acessibilidade, atualizados a cada 30 segundos e lidos em voz alta.</li>
            <li><strong>Assistente.</strong> Responde por texto ou voz sobre horários em tempo real e sobre gratuidade, Bilhete Único e acessibilidade, citando as fontes.</li>
            <li><strong>Boletim diário.</strong> Esperas previstas nas linhas acompanhadas, com período de referência e origem dos dados.</li>
          </ol>
        </section>

        <section class="artigo__secao" id="dados" aria-labelledby="transparencia">
          <h2 id="transparencia">Transparência dos dados</h2>
          <p>Todo dado vem com um selo dizendo de onde veio. Os selos têm forma própria, então não dependem só da cor.</p>
          <dl class="legenda__lista legenda__lista--sobre">
            <div><dt><pf-origem tipo="real" semDescricao /></dt><dd>Previsões em tempo real da SPTrans. São estimativas: o ônibus pode adiantar, atrasar ou não passar.</dd></div>
            <div><dt><pf-origem tipo="simulado" semDescricao /></dt><dd>Dados de demonstração, só para mostrar como o app funciona. Não são ônibus reais.</dd></div>
            <div><dt><pf-origem tipo="estimado" semDescricao /></dt><dd>Esperas calculadas a partir das previsões consultadas. Não confirmam chegada nem atraso.</dd></div>
            <div><dt><pf-origem tipo="base-oficial" semDescricao /></dt><dd>Respostas do assistente baseadas em documentos oficiais, com a lista de fontes.</dd></div>
            <div><dt><pf-origem tipo="indisponivel" semDescricao /></dt><dd>O serviço ou o dado não está disponível agora. Avisamos em vez de inventar.</dd></div>
          </dl>
          <p>Um horário nunca é apresentado como chegada: dizemos sempre “previsto em”.</p>
        </section>

        <section class="artigo__secao" aria-labelledby="privacidade">
          <h2 id="privacidade">Privacidade</h2>
          <ul class="lista-simples">
            <li>Não existe cadastro nem conta.</li>
            <li>As perguntas feitas ao assistente não são guardadas.</li>
            <li>Ajustes, pontos salvos e buscas recentes ficam só neste aparelho.</li>
          </ul>
          <p><a routerLink="/acessibilidade">Ajustar letras, cores e voz</a></p>
        </section>

        <section class="artigo__secao" aria-labelledby="equipe">
          <h2 id="equipe">Equipe</h2>
          <p>Projeto acadêmico da FIAP, Global Solution 2026.</p>
          <ul class="equipe">
            @for (m of equipe; track m.rm) {
              <li><span>{{ m.nome }}</span> <span class="equipe__rm">RM {{ m.rm }}</span></li>
            }
          </ul>
        </section>
      </div>
    </div>
  `,
})
export class Sobre {
  protected readonly equipe = [
    { nome: 'Pedro Henrique Bicas Couto', rm: '99534' },
    { nome: 'Bryan Willian', rm: '551305' },
    { nome: 'Felipe Masera Terra', rm: '99405' },
    { nome: 'Gabriel Fernandes Doms', rm: '98630' },
    { nome: 'Lucas Vassão Braga', rm: '98607' },
  ];
}
