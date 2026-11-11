package br.fiap.pontofalante.sistema;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.boot.test.context.TestConfiguration;

import static org.assertj.core.api.Assertions.assertThat;

class ConfigSptransTest {
    @TestConfiguration(proxyBeanMethods = false)
    @EnableConfigurationProperties(PfProps.class)
    static class Props {}

    final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(Props.class, ConfigSptrans.class);

    @Test void defaultLegadoHttpViraHttpsSemRedirecionar() {
        runner.withPropertyValues("pf.sptrans-base-url=http://api.olhovivo.sptrans.com.br/v2.1")
                .run(ctx -> assertThat(ctx.getBean(PfProps.class).sptransBaseUrl())
                        .isEqualTo("https://api.olhovivo.sptrans.com.br/v2.1"));
    }

    @Test void normalizaTokenSemAlterarConteudo() {
        runner.withPropertyValues("pf.sptrans-token=  token-local  ").run(ctx ->
                assertThat(ctx.getBean(PfProps.class).sptransToken()).isEqualTo("token-local"));
    }

    @Test void demoMantemChaveArmazenadaMasNaoAUsa() {
        runner.withPropertyValues("PF_SPTRANS_MODO=demo", "pf.sptrans-token=token-nao-enviar")
                .run(ctx -> assertThat(ctx.getBean(PfProps.class).temTokenSptrans()).isFalse());
    }

    @Test void autoPermiteConsultarComChaveConfigurada() {
        runner.withPropertyValues("PF_SPTRANS_MODO=auto", "pf.sptrans-token=token-local")
                .run(ctx -> assertThat(ctx.getBean(PfProps.class).temTokenSptrans()).isTrue());
    }

    @Test void rejeitaWhitespaceInternoSemExporChave() {
        runner.withPropertyValues("pf.sptrans-token=segredo com espaco").run(ctx -> {
            assertThat(ctx).hasFailed();
            assertThat(ctx.getStartupFailure()).hasMessageNotContaining("segredo com espaco");
        });
    }

    @Test void rejeitaHttpExternoMasAceitaLoopbackDeTeste() {
        runner.withPropertyValues("pf.sptrans-base-url=http://servidor.externo/v2.1")
                .run(ctx -> assertThat(ctx).hasFailed());
        runner.withPropertyValues("pf.sptrans-base-url=http://127.0.0.1:12345/v2.1")
                .run(ctx -> assertThat(ctx).hasNotFailed());
    }
}
