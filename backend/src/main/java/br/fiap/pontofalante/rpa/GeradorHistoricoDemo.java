package br.fiap.pontofalante.rpa;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Histórico SIMULADO da rede fictícia do robô RPA (linhas 1001-10..1005-10, pontos PF-0001..PF-0020).
 * Porte da lógica de rpa/tools/mock_mvp.py: mesma estrutura, ~3% de registros inválidos e ~3% de duplicados
 * de propósito, semente fixa por data (mesma data = mesmos dados). A sequência aleatória não é idêntica à do
 * Python (geradores diferentes), mas as regras e os perfis de atraso são os mesmos.
 */
public final class GeradorHistoricoDemo {
    private GeradorHistoricoDemo() {
    }

    private record Perfil(int atrasoMedio, int desvio, int intervalo, List<String> pontos) {
    }

    private static final Map<String, Perfil> PERFIS = new LinkedHashMap<>();

    static {
        PERFIS.put("1001-10", new Perfil(14, 5, 15, List.of("PF-0001", "PF-0002", "PF-0003")));
        PERFIS.put("1002-10", new Perfil(7, 3, 15, List.of("PF-0004", "PF-0005", "PF-0006")));
        PERFIS.put("1003-10", new Perfil(2, 2, 12, List.of("PF-0007", "PF-0008", "PF-0009")));
        PERFIS.put("1004-10", new Perfil(1, 2, 10, List.of("PF-0010", "PF-0011", "PF-0012")));
        PERFIS.put("1005-10", new Perfil(3, 2, 20, List.of("PF-0013", "PF-0014", "PF-0015")));
    }

    private static final int[][] FAIXAS = {{6 * 60, 9 * 60}, {17 * 60, 19 * 60}};
    private static final double TAXA_INVALIDOS = 0.03;
    private static final double TAXA_DUPLICADOS = 0.03;
    private static final ZoneOffset BRASILIA = ZoneOffset.ofHours(-3);

    private record Reg(String ponto, String linha, String veiculo, String programado, String previsto, boolean acessivel,
                       OffsetDateTime atualizadoEm) {
    }

    public static String hhmm(int minutos) {
        int m = Math.floorMod(minutos, 1440);
        return String.format("%02d:%02d", m / 60, m % 60);
    }

    static long semente(LocalDate data) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256")
                    .digest(("ponto-falante-" + data).getBytes(StandardCharsets.UTF_8));
            return ByteBuffer.wrap(h).getLong();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String hashVeiculo(String linha, int n) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest((linha + "-" + n).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h).substring(0, 12);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static OffsetDateTime instante(LocalDate data, int minutosDoDia) {
        int m = Math.floorMod(minutosDoDia, 1440);
        return OffsetDateTime.of(data, LocalTime.of(m / 60, m % 60), BRASILIA);
    }

    public static List<Passagem> gerar(LocalDate data) {
        Random rng = new Random(semente(data));
        List<Reg> regs = new ArrayList<>();
        for (Map.Entry<String, Perfil> e : PERFIS.entrySet()) {
            String linha = e.getKey();
            Perfil perfil = e.getValue();
            for (int iPonto = 0; iPonto < perfil.pontos().size(); iPonto++) {
                String ponto = perfil.pontos().get(iPonto);
                int n = 0;
                for (int[] faixa : FAIXAS) {
                    for (int prog = faixa[0] + 3 * iPonto; prog < faixa[1]; prog += perfil.intervalo()) {
                        n++;
                        int atraso = (int) Math.rint(perfil.atrasoMedio() + perfil.desvio() * rng.nextGaussian());
                        boolean acessivel = rng.nextDouble() < 0.6;
                        regs.add(new Reg(ponto, linha, hashVeiculo(linha, n), hhmm(prog), hhmm(prog + atraso), acessivel,
                                instante(data, prog + atraso)));
                    }
                }
            }
        }
        // Registros inválidos de propósito (para as regras de qualidade do robô terem o que barrar)
        int invalidos = Math.max(1, (int) (regs.size() * TAXA_INVALIDOS));
        for (int i = 0; i < invalidos; i++) {
            Reg r = regs.get(rng.nextInt(regs.size()));
            int tipo = rng.nextInt(3);
            if (tipo == 0) {
                r = new Reg(r.ponto(), "9999-99", r.veiculo(), r.programado(), r.previsto(), r.acessivel(), r.atualizadoEm());
            } else if (tipo == 1) {
                r = new Reg("", r.linha(), r.veiculo(), r.programado(), r.previsto(), r.acessivel(), r.atualizadoEm());
            } else {
                String[] hm = r.programado().split(":");
                int prog = Integer.parseInt(hm[0]) * 60 + Integer.parseInt(hm[1]);
                r = new Reg(r.ponto(), r.linha(), r.veiculo(), r.programado(), hhmm(prog - 90), r.acessivel(), r.atualizadoEm());
            }
            regs.add(r);
        }
        // Duplicados de propósito (mesmo veículo, ponto e minuto)
        int duplicados = Math.max(1, (int) (regs.size() * TAXA_DUPLICADOS));
        for (int i = 0; i < duplicados; i++) {
            regs.add(regs.get(rng.nextInt(regs.size())));
        }
        Collections.shuffle(regs, rng);
        List<Passagem> saida = new ArrayList<>(regs.size());
        for (Reg r : regs) {
            saida.add(new Passagem(data, r.ponto(), r.linha(), "Centro", r.veiculo(), r.programado(), r.previsto(),
                    r.acessivel(), "simulador", "SIMULADA", r.atualizadoEm()));
        }
        return saida;
    }
}
