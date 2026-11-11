package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** Anonimiza o prefixo do veículo: SHA-256(sal + prefixo) truncado em 10 caracteres hexadecimais. */
@Component
public class HashVeiculo {
    private final String salt;

    public HashVeiculo(PfProps props) {
        this.salt = props.salt();
    }

    public String hash(String prefixo) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] h = md.digest((salt + ":" + prefixo).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h).substring(0, 10);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
