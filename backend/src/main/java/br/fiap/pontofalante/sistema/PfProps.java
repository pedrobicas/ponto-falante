package br.fiap.pontofalante.sistema;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** Toda a configuração do Ponto Falante (prefixo pf.*), lida de variáveis de ambiente via application.yml. */
@ConfigurationProperties("pf")
public record PfProps(
        @DefaultValue("") String sptransToken,
        @DefaultValue("http://api.olhovivo.sptrans.com.br/v2.1") String sptransBaseUrl,
        @DefaultValue("3000") int sptransConnectTimeoutMs,
        @DefaultValue("8000") int sptransReadTimeoutMs,
        @DefaultValue("") String genaiUrl,
        @DefaultValue("") String genaiApiKey,
        @DefaultValue("3000") int genaiConnectTimeoutMs,
        @DefaultValue("45000") int genaiReadTimeoutMs,
        @DefaultValue("30") int genaiCircuitoSegundos,
        @DefaultValue("10") int chatLimitePorMinuto,
        @DefaultValue("troque-este-sal-em-producao") String salt,
        @DefaultValue("") String rpaApiKey,
        @DefaultValue("") String visaoApiKey,
        @DefaultValue("") String dispositivoApiKey,
        @DefaultValue("") String dadosApiKey,
        @DefaultValue("http://localhost:4200") String devOrigin) {

    private static boolean preenchido(String s) {
        return s != null && !s.isBlank();
    }

    public boolean temTokenSptrans() {
        return preenchido(sptransToken);
    }

    public boolean temGenai() {
        return preenchido(genaiUrl);
    }
}
