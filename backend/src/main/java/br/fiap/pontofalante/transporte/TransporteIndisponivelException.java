package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import org.springframework.http.HttpStatus;

public class TransporteIndisponivelException extends ErroApi {
    public TransporteIndisponivelException() {
        super(HttpStatus.SERVICE_UNAVAILABLE, "SPTRANS_INDISPONIVEL",
                "Não conseguimos consultar os horários da SPTrans agora. Você pode ver a demonstração.");
    }
}
