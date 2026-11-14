package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.Acao;
import br.fiap.pontofalante.assistente.Chat.Contexto;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import br.fiap.pontofalante.transporte.RedeGtfs;
import br.fiap.pontofalante.transporte.RedeGtfs.Parada;
import br.fiap.pontofalante.transporte.RedeGtfs.ParadaEncontrada;
import br.fiap.pontofalante.transporte.RedeGtfs.Viagem;
import br.fiap.pontofalante.transporte.TransporteService;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Ferramentas determinísticas sobre o cadastro oficial (GTFS): linha direta de uma origem a um destino, se a linha
 * passa em uma via, e o ponto do sentido contrário. Só afirma o que a sequência de paradas do cadastro sustenta;
 * não calcula baldeação nem tempo de viagem.
 */
final class FerramentasRota {
    record Resultado(String texto, Contexto contexto, List<Acao> acoes) {
    }

    /** Ponto do outro sentido da linha mais perto do ponto atual. */
    record PontoContrario(Parada parada, int sentido, String destino, int metros) {
    }

    private static final Pattern DESTINO = Pattern.compile(
            "\\b(?:vai|vao|vou|ir|chegar|chego|chega|leva|levam|passa|passam)\\s+(?:ate\\s+)?(?:para|pra|pro|ao|aos|a|ate)\\s+"
                    + "(?:o |a |os |as )?(.+?)(?=\\s+(?:saindo|partindo|a partir|desde)\\b|\\s*[?!.]*$)");
    private static final Pattern ORIGEM = Pattern.compile(
            "\\b(?:saindo|partindo|a partir|desde)\\s+(?:d[aeo]s?\\s+)?(?:o |a )?(.+?)(?=\\s+(?:para|pra|pro|ate)\\s|\\s*[?!.]*$)");
    private static final Pattern DE_PARA = Pattern.compile(
            "\\bd[aeo]\\s+(.+?)\\s+(?:para|pra|pro|ate)\\s+(?:o |a |os |as )?(.+?)\\s*[?!.]*$");
    private static final Pattern VIA = Pattern.compile(
            "\\bpassa[m]?\\s+(?:na|no|nas|nos|pela|pelo|pelas|pelos|em|perto d[aeo])\\s+(.+?)\\s*[?!.]*$");
    /** Regiões sem parada com esse nome: centro geográfico e raio em metros (declarado na resposta). */
    private static final Map<String, double[]> REGIOES = Map.of("centro", new double[] {-23.5505, -46.6333, 1500});
    private static final Set<String> CENTRO = Set.of("centro", "centro da cidade", "regiao central", "centrao",
            "centro de sao paulo", "centro de sp");

    private FerramentasRota() {
    }

    static boolean perguntaDeRota(String t) {
        return (DESTINO.matcher(t).find() && (ORIGEM.matcher(t).find() || t.contains("como ") || t.contains("qual ")
                || t.contains("quais ") || t.contains("que onibus"))) || viaPerguntada(t) != null;
    }

    static String viaPerguntada(String t) {
        Matcher m = VIA.matcher(t);
        // "quais linhas passam no ponto 160015580" pergunta pelo ponto, não por uma via.
        return m.find() && !m.group(1).matches("^(ponto|parada|pto)\\b.*|.*\\d{6,}.*") ? m.group(1) : null;
    }

    /** "Qual ônibus vai para X saindo de Y?" Vazio quando a frase não é esse tipo de pergunta. */
    static Optional<Resultado> linhaDireta(TransporteService transporte, String t, Contexto c) {
        if (!transporte.usaCadastro(null) || viaPerguntada(t) != null) {
            return Optional.empty();
        }
        String destinoTexto = null;
        String origemTexto = null;
        Matcher md = DESTINO.matcher(t);
        if (md.find()) {
            destinoTexto = md.group(1).strip();
        }
        Matcher mo = ORIGEM.matcher(t);
        if (mo.find()) {
            origemTexto = mo.group(1).strip();
        } else {
            Matcher dp = DE_PARA.matcher(t);
            if (destinoTexto != null && dp.find() && !dp.group(1).matches(".*\\b(onibus|linha)\\b.*")) {
                origemTexto = dp.group(1).strip();
                destinoTexto = dp.group(2).strip();
            }
        }
        if (destinoTexto == null || destinoTexto.isBlank() || destinoTexto.matches("(la|ali|aqui|casa|trabalho)")) {
            return Optional.empty();
        }
        RedeGtfs rede = transporte.rede();
        Parada origem = null;
        if (origemTexto != null && !origemTexto.isBlank()) {
            List<Ponto> achados = transporte.buscarPontos(origemTexto, null).pontos();
            if (achados.isEmpty()) {
                return Optional.of(new Resultado("Não encontrei o ponto de saída \"" + origemTexto
                        + "\". Diga o nome da rua com o número ou o código da placa do ponto.", c, List.of()));
            }
            origem = rede.parada(achados.getFirst().codigo());
        } else if (c != null && c.ponto() != null) {
            origem = rede.parada(c.ponto());
        }
        if (origem == null) {
            return Optional.of(new Resultado("De onde você vai sair? Diga, por exemplo: qual ônibus vai para "
                    + destinoTexto + " saindo da Avenida Paulista, 1000. Se preferir, veja os pontos perto de você.",
                    c, List.of(new Acao("Pontos perto de mim", null, "/busca?perto=1"))));
        }

        // Origem: o ponto dito e os vizinhos a até 250 m (o outro lado da rua costuma ser o sentido oposto).
        Map<Long, Integer> origens = new LinkedHashMap<>();
        origens.put(origem.codigo(), 0);
        for (ParadaEncontrada e : rede.proximas(origem.latitude(), origem.longitude(), 250, 12)) {
            origens.putIfAbsent(e.parada().codigo(), e.distanciaMetros());
        }
        Set<Long> destinos = new LinkedHashSet<>();
        String destinoDito = destinoTexto;
        String nota = "";
        double[] regiao = CENTRO.contains(destinoTexto) ? REGIOES.get("centro") : null;
        List<String> tokensDestino = RedeGtfs.tokens(destinoTexto);
        if (regiao != null) {
            for (ParadaEncontrada e : rede.proximas(regiao[0], regiao[1], (int) regiao[2], 2000)) {
                destinos.add(e.parada().codigo());
            }
            destinoDito = "o Centro";
            nota = " Considerei Centro a região a até 1,5 km da Praça da Sé.";
        } else {
            List<ParadaEncontrada> achados = rede.buscarParadas(destinoTexto, 30);
            for (ParadaEncontrada e : achados) {
                destinos.add(e.parada().codigo());
            }
            if (!achados.isEmpty()) {
                Parada principal = achados.getFirst().parada();
                for (ParadaEncontrada e : rede.proximas(principal.latitude(), principal.longitude(), 300, 20)) {
                    destinos.add(e.parada().codigo());
                }
            }
        }

        record Opcao(Viagem v, Parada embarque, Parada desembarque, int metros) {
        }
        Map<String, Opcao> opcoes = new LinkedHashMap<>();
        for (Viagem v : viagensQuePassam(rede, origens.keySet())) {
            int iEmbarque = -1;
            Parada desembarque = null;
            for (int i = 0; i < v.paradas().length; i++) {
                long id = v.paradas()[i];
                if (origens.containsKey(id) && desembarque == null
                        && (iEmbarque < 0 || id == origem.codigo())) {
                    // Entre os pontos vizinhos, prefere embarcar no ponto que a pessoa disse.
                    iEmbarque = i;
                } else if (iEmbarque >= 0 && destinos.contains(id) && !origens.containsKey(id)) {
                    desembarque = rede.parada(id);
                    break;
                }
            }
            if (iEmbarque < 0 || iEmbarque >= v.paradas().length - 1) {
                continue;
            }
            // Sem parada com esse nome no trajeto, vale o destino do letreiro (ex.: "Term. Sto. Amaro").
            boolean peloLetreiro = desembarque == null && !tokensDestino.isEmpty() && regiao == null
                    && RedeGtfs.tokens(v.destino()).containsAll(tokensDestino);
            if (desembarque == null && !peloLetreiro) {
                continue;
            }
            Parada embarque = rede.parada(v.paradas()[iEmbarque]);
            Opcao nova = new Opcao(v, embarque, desembarque, origens.get(embarque.codigo()));
            opcoes.merge(v.letreiro() + "|" + v.sentido(), nova, (a, b) -> a.metros() <= b.metros() ? a : b);
        }
        if (opcoes.isEmpty()) {
            return Optional.of(new Resultado("Não encontrei linha direta de " + origem.nome() + " para " + destinoDito
                    + " no cadastro da SPTrans." + nota + " Ainda não calculo trajetos com baldeação. "
                    + "Você pode ver todas as linhas que passam neste ponto.",
                    new Contexto(origem.codigo(), null, null, null, null),
                    List.of(new Acao("Linhas deste ponto", "quais linhas passam no ponto " + origem.codigo(), null))));
        }
        List<Opcao> ordenadas = new ArrayList<>(opcoes.values());
        ordenadas.sort(java.util.Comparator.comparingInt(Opcao::metros).thenComparing(o -> o.v().letreiro()));
        StringBuilder sb = new StringBuilder("Saindo de ").append(origem.nome()).append(", ")
                .append(ordenadas.size() == 1 ? "esta linha vai" : "estas linhas vão").append(" direto para ")
                .append(destinoDito).append(", sem baldeação, segundo o cadastro da SPTrans:\n");
        List<Acao> acoes = new ArrayList<>();
        int mostradas = 0;
        for (Opcao o : ordenadas) {
            if (mostradas++ >= 5) {
                break;
            }
            sb.append(o.v().letreiro()).append(", sentido ").append(o.v().destino());
            if (o.embarque().codigo() != origem.codigo()) {
                sb.append(", embarque em ").append(o.embarque().nome()).append(" (a ").append(o.metros()).append(" m)");
            }
            if (o.desembarque() != null) {
                sb.append(", passa em ").append(o.desembarque().nome());
            }
            sb.append(".\n");
            if (acoes.size() < 3) {
                acoes.add(new Acao("Quanto falta para a " + o.v().letreiro() + "?", "previsão da linha "
                        + o.v().letreiro() + " no ponto " + o.embarque().codigo() + " no sentido " + o.v().sentido(), null));
            }
        }
        if (ordenadas.size() > 5) {
            sb.append("Há mais ").append(ordenadas.size() - 5).append(" linhas; veja todas na página do ponto.\n");
        }
        sb.append("O cadastro mostra o trajeto, não o tempo de viagem.").append(nota);
        acoes.add(new Acao("Ver ponto e previsões", null, "/ponto/" + origem.codigo()));
        return Optional.of(new Resultado(sb.toString(), new Contexto(origem.codigo(), null, null, null, null), acoes));
    }

    private static List<Viagem> viagensQuePassam(RedeGtfs rede, Set<Long> pontos) {
        Set<Viagem> vistas = new LinkedHashSet<>();
        for (long id : pontos) {
            vistas.addAll(rede.viagensDaParada(id));
        }
        return new ArrayList<>(vistas);
    }

    /** Paradas da linha cujo nome ou referência contém todas as palavras da via (com abreviações e sem acento). */
    static List<Parada> paradasNaVia(RedeGtfs rede, Viagem v, String via) {
        List<String> palavras = RedeGtfs.tokens(via);
        List<Parada> saida = new ArrayList<>();
        if (palavras.isEmpty()) {
            return saida;
        }
        for (long id : v.paradas()) {
            Parada p = rede.parada(id);
            if (p != null && RedeGtfs.tokens(p.nome() + " " + p.referencia()).containsAll(palavras)) {
                saida.add(p);
            }
        }
        return saida;
    }

    /** O ponto fica no lugar perguntado: pelo nome da via (palavras, abreviações) ou dentro da região (Centro). */
    static boolean lugarCasa(Ponto p, String termo) {
        String limpo = termo == null ? "" : termo.strip();
        double[] regiao = CENTRO.contains(limpo) ? REGIOES.get("centro") : null;
        if (regiao != null) {
            return p.latitude() != null && p.longitude() != null
                    && RedeGtfs.metros(regiao[0], regiao[1], p.latitude(), p.longitude()) <= regiao[2];
        }
        List<String> palavras = RedeGtfs.tokens(limpo);
        return !palavras.isEmpty() && RedeGtfs.tokens(p.nome() + " " + (p.endereco() == null ? "" : p.endereco())).containsAll(palavras);
    }

    /** Sentido em que a linha atende o ponto; nulo se não atende ou se os dois sentidos param nele. */
    static Integer sentidoNoPonto(RedeGtfs rede, String linha, long ponto) {
        Integer achado = null;
        for (Viagem v : rede.viagensDaLinha(linha)) {
            for (long id : v.paradas()) {
                if (id == ponto) {
                    if (achado != null && achado != v.sentido()) {
                        return null;
                    }
                    achado = v.sentido();
                    break;
                }
            }
        }
        return achado;
    }

    /** O ponto do outro sentido mais próximo do ponto atual, a até 600 m. */
    static Optional<PontoContrario> pontoDoSentidoContrario(RedeGtfs rede, String linha, long ponto, int sentidoAtual) {
        Parada atual = rede.parada(ponto);
        if (atual == null) {
            return Optional.empty();
        }
        PontoContrario melhor = null;
        for (Viagem v : rede.viagensDaLinha(linha)) {
            if (v.sentido() == sentidoAtual) {
                continue;
            }
            for (long id : v.paradas()) {
                Parada p = rede.parada(id);
                if (p == null || id == ponto) {
                    continue;
                }
                int d = RedeGtfs.metros(atual.latitude(), atual.longitude(), p.latitude(), p.longitude());
                if (d <= 600 && (melhor == null || d < melhor.metros())) {
                    melhor = new PontoContrario(p, v.sentido(), v.destino(), d);
                }
            }
        }
        return Optional.ofNullable(melhor);
    }
}
