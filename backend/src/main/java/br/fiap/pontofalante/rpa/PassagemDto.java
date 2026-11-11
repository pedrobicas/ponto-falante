package br.fiap.pontofalante.rpa;

import br.fiap.pontofalante.sistema.ConfigWeb;

import java.time.OffsetDateTime;

/** Formato do contrato openapi-integracao.yaml (Passagem) mais tipo_registro. */
public record PassagemDto(String ponto, String linha, String sentido, String veiculo, String programadoEm,
                          String previstoEm, Boolean acessivel, String fonte, String tipoRegistro,
                          OffsetDateTime atualizadoEm) {
    static PassagemDto de(Passagem p) {
        return new PassagemDto(p.ponto, p.linha, p.sentido, p.veiculo, p.programadoEm, p.previstoEm, p.acessivel,
                p.fonte, p.tipoRegistro,
                p.atualizadoEm == null ? null : p.atualizadoEm.atZoneSameInstant(ConfigWeb.SAO_PAULO).toOffsetDateTime());
    }
}
