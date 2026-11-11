package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Linha;
import br.fiap.pontofalante.transporte.Modelos.Ponto;

import java.util.List;

/** Origem dos dados de transporte: SPTrans Olho Vivo (real) ou simulador (demonstração). */
public interface ProvedorTransporte {
    Fonte fonte();

    List<Ponto> buscarPontos(String termo);

    List<Linha> buscarLinhas(String termo);

    /** @throws br.fiap.pontofalante.sistema.ErroApi 404 se o ponto não existe; 503 se a origem falhar */
    DadosPrevisao previsoes(long codigoPonto);
}
