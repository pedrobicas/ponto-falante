package br.fiap.pontofalante.sistema;

import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/** Converte qualquer falha em Erro {mensagem, codigo}; nunca devolve stack trace nem texto do usuário. */
@RestControllerAdvice
public class TratadorDeErros {
    private static final Logger log = LoggerFactory.getLogger(TratadorDeErros.class);

    private static ResponseEntity<Erro> resposta(HttpStatus status, String codigo, String mensagem) {
        return ResponseEntity.status(status).body(new Erro(mensagem, codigo));
    }

    @ExceptionHandler(ErroApi.class)
    ResponseEntity<Erro> erroApi(ErroApi e) {
        return resposta(e.getStatus(), e.getCodigo(), e.getMessage());
    }

    @ExceptionHandler(org.springframework.web.multipart.MaxUploadSizeExceededException.class)
    ResponseEntity<Erro> arquivoGrande(Exception e) {
        return resposta(HttpStatus.PAYLOAD_TOO_LARGE, "ARQUIVO_GRANDE", "A foto é grande demais. Envie uma imagem de até 2 MB.");
    }

    @ExceptionHandler({org.springframework.web.multipart.support.MissingServletRequestPartException.class,
            org.springframework.web.multipart.MultipartException.class})
    ResponseEntity<Erro> semArquivo(Exception e) {
        return resposta(HttpStatus.BAD_REQUEST, "IMAGEM_AUSENTE", "Envie a foto do letreiro.");
    }

    @ExceptionHandler(org.springframework.web.HttpMediaTypeNotSupportedException.class)
    ResponseEntity<Erro> tipoNaoSuportado(Exception e) {
        return resposta(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "TIPO_NAO_SUPORTADO", "O formato enviado não é aceito aqui.");
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<Erro> validacao(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream().findFirst()
                .map(FieldError::getDefaultMessage).orElse("Dados inválidos.");
        return resposta(HttpStatus.BAD_REQUEST, "REQUISICAO_INVALIDA", msg);
    }

    @ExceptionHandler({HandlerMethodValidationException.class, ConstraintViolationException.class})
    ResponseEntity<Erro> validacaoMetodo(Exception e) {
        return resposta(HttpStatus.BAD_REQUEST, "REQUISICAO_INVALIDA", "Dados inválidos. Confira o que foi enviado.");
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<Erro> jsonInvalido(HttpMessageNotReadableException e) {
        return resposta(HttpStatus.BAD_REQUEST, "JSON_INVALIDO", "O conteúdo enviado não está num formato válido.");
    }

    @ExceptionHandler({MissingServletRequestParameterException.class, MissingRequestHeaderException.class})
    ResponseEntity<Erro> faltaParametro(Exception e) {
        return resposta(HttpStatus.BAD_REQUEST, "PARAMETRO_AUSENTE", "Faltou informar um dado obrigatório.");
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ResponseEntity<Erro> tipoErrado(MethodArgumentTypeMismatchException e) {
        return resposta(HttpStatus.BAD_REQUEST, "PARAMETRO_INVALIDO", "Um dos dados informados está num formato inválido.");
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<Erro> semRecurso(NoResourceFoundException e) {
        return resposta(HttpStatus.NOT_FOUND, "NAO_ENCONTRADO", "Não encontramos o que você procurou.");
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<Erro> metodo(HttpRequestMethodNotSupportedException e) {
        return resposta(HttpStatus.METHOD_NOT_ALLOWED, "METODO_NAO_PERMITIDO", "Esta operação não é permitida aqui.");
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<Erro> inesperado(Exception e) {
        log.error("Erro inesperado: {}", e.getClass().getName(), e);
        return resposta(HttpStatus.INTERNAL_SERVER_ERROR, "ERRO_INTERNO", "Algo deu errado do nosso lado. Tente de novo em instantes.");
    }
}
