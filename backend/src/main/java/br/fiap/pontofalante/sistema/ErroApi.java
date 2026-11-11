package br.fiap.pontofalante.sistema;

import org.springframework.http.HttpStatus;

/** Exceção de negócio que vira a resposta Erro {mensagem, codigo}. */
public class ErroApi extends RuntimeException {
    private final HttpStatus status;
    private final String codigo;

    public ErroApi(HttpStatus status, String codigo, String mensagem) {
        super(mensagem);
        this.status = status;
        this.codigo = codigo;
    }

    public HttpStatus getStatus() {
        return status;
    }

    public String getCodigo() {
        return codigo;
    }

    public static ErroApi requisicaoInvalida(String mensagem) {
        return new ErroApi(HttpStatus.BAD_REQUEST, "REQUISICAO_INVALIDA", mensagem);
    }

    public static ErroApi naoEncontrado(String mensagem) {
        return new ErroApi(HttpStatus.NOT_FOUND, "NAO_ENCONTRADO", mensagem);
    }
}
