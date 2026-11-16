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
        @DefaultValue("http://localhost:4200") String devOrigin,
        @DefaultValue("") String sptransGatewayChave,
        @DefaultValue("") String sptransGatewaySegredo,
        @DefaultValue("https://gateway.apilib.prefeitura.sp.gov.br/sptrans/olhovivo/v2.1") String sptransGatewayUrl,
        @DefaultValue("https://gateway.apilib.prefeitura.sp.gov.br/token") String sptransGatewayTokenUrl,
        /** Serviço do modelo de visão que lê o letreiro (vazio = conferência pela câmera desligada). */
        @DefaultValue("") String visaoUrl,
        @DefaultValue("") String visaoServicoChave) {

    private static boolean preenchido(String s) {
        return s != null && !s.isBlank();
    }

    /** Há credencial para dados reais: chave direta da Olho Vivo ou credenciais OAuth do gateway da Prefeitura. */
    public boolean temTokenSptrans() {
        return preenchido(sptransToken) || usaGatewaySptrans();
    }

    /** Gateway oficial (apilib.prefeitura.sp.gov.br): OAuth2 client_credentials, sem /Login/Autenticar. */
    public boolean usaGatewaySptrans() {
        return preenchido(sptransGatewayChave) && preenchido(sptransGatewaySegredo);
    }

    public boolean temGenai() {
        return preenchido(genaiUrl);
    }
}
