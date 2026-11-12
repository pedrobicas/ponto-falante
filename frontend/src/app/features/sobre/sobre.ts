import { Component } from '@angular/core';
import { Icone } from '../../shared/icone';

@Component({
  selector: 'pf-sobre',
  imports: [Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="info" /> Quem somos</p>
        <h1>Sobre o Ponto Falante</h1>
        <p class="lead">
          O Ponto Falante ajuda quem espera ônibus em São Paulo, especialmente pessoas idosas e pessoas com deficiência
          visual. Ele mostra os próximos ônibus previstos para um ponto e lê a informação em voz alta.
        </p>
      </div>
    </section>

    <div class="miolo">
      <section class="cartao cartao--icone" aria-labelledby="o-que-faz">
        <span class="cartao__selo"><pf-icone nome="onibus" /></span>
        <h2 id="o-que-faz">O que o aplicativo faz</h2>
        <ul>
          <li>Mostra os próximos ônibus previstos para o seu ponto e os lê em voz alta.</li>
          <li>Tem um assistente que responde perguntas simples, também por voz.</li>
          <li>Publica um boletim diário com as linhas que estão atrasadas.</li>
        </ul>
      </section>

      <section class="cartao cartao--icone" aria-labelledby="honestidade">
        <span class="cartao__selo"><pf-icone nome="certo-circulo" /></span>
        <h2 id="honestidade">Dados com honestidade</h2>
        <ul>
          <li>Os horários são <strong>previsões</strong> estimadas pela SPTrans. Um ônibus previsto pode atrasar ou não passar.</li>
          <li>Quando aparece “Dados de demonstração”, as informações são <strong>simuladas</strong>, só para mostrar como o app funciona.</li>
          <li>O boletim é gerado e publicado automaticamente por um robô. Quando está desatualizado, avisamos.</li>
          <li>O assistente pode errar. Em decisões importantes, confirme com a SPTrans ou a prefeitura.</li>
        </ul>
      </section>

      <section class="cartao cartao--icone" aria-labelledby="privacidade">
        <span class="cartao__selo"><pf-icone nome="escudo" /></span>
        <h2 id="privacidade">Privacidade</h2>
        <ul>
          <li>Não existe cadastro nem conta.</li>
          <li>As perguntas feitas ao assistente não são guardadas.</li>
          <li>Seus ajustes e os pontos recentes ficam só neste aparelho.</li>
        </ul>
      </section>

      <section class="cartao cartao--icone" aria-labelledby="equipe">
        <span class="cartao__selo"><pf-icone nome="pessoas" /></span>
        <h2 id="equipe">Equipe</h2>
        <p>Projeto acadêmico da FIAP (Global Solution).</p>
        <ul class="equipe">
          @for (m of equipe; track m.rm) {
            <li>{{ m.nome }} <span class="ajuda">RM {{ m.rm }}</span></li>
          }
        </ul>
      </section>
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
