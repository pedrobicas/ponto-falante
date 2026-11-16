package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * O Embarque Assistido não tem login. O aparelho gera um identificador aleatório (cabeçalho X-PF-Dispositivo) e o
 * backend grava só SHA-256(sal + identificador): sem o identificador, que fica no aparelho, ninguém liga os
 * registros a uma pessoa. Apagar os dados do aparelho (DELETE /api/embarque/dados) remove tudo.
 */
@Component
public class IdentificadorDispositivo {
    public static final String CABECALHO = "X-PF-Dispositivo";
    private final byte[] sal;

    public IdentificadorDispositivo(PfProps props) {
        this.sal = (props.salt() + "|embarque").getBytes(StandardCharsets.UTF_8);
    }

    public String hash(String identificador) {
        if (identificador == null || !identificador.matches("[a-f0-9]{32,64}")) {
            throw new ErroApi(org.springframework.http.HttpStatus.BAD_REQUEST, "DISPOSITIVO_INVALIDO",
                    "Não reconheci este aparelho. Recarregue a página e tente de novo.");
        }
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(sal);
            md.update((byte) 0);
            md.update(identificador.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(md.digest());
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
