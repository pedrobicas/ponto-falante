package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.*;
import br.fiap.pontofalante.transporte.*;
import br.fiap.pontofalante.transporte.Modelos.*;
import br.fiap.pontofalante.sistema.ErroApi;
import java.util.*;
import java.util.regex.Pattern;

/** Roteador de ferramentas. Memória contém apenas entidades, nunca previsões ou instruções da LLM. */
final class ConversaTransporte {
    private static final Pattern PONTO = Pattern.compile("\\b(\\d{6,10})\\b");
    private static final Pattern LINHA = Pattern.compile("\\b(\\d{3,4}[a-z]?-\\d{1,2})\\b");
    private static final Pattern REGRA = Pattern.compile("\\b(bilhete|gratuidade|gratuit[oa]|gratis|idos[oa]s?|pagar|paga|pago|tarifa|passagem|deficiencia|cadeira|cadeirante|acessibilidade|direito|recarga|cartao|acompanhante|descer|desembarque|motorista|lei|anos|rg|identidade|estudante|beneficio|custa|preco)\\b");
    private static final Pattern TEMPO = Pattern.compile("\\b(proxim[oa]s?|previsao|previsoes|quando|que horas|demora|demoram|chega|chegam|agora|vem|falta|faltam|quanto tempo)\\b");
    private final TransporteService transporte;
    private final AssistenteTempoReal formatador;

    ConversaTransporte(TransporteService transporte, AssistenteTempoReal formatador) {
        this.transporte = transporte;
        this.formatador = formatador;
    }

    Optional<RespostaChat> responder(String pergunta, Contexto anterior) {
        if (pergunta == null || pergunta.isBlank()) return Optional.empty();
        String t = AssistenteTempoReal.normalizar(pergunta)
                .replaceAll("\\bqnto\\b", "quanto").replaceAll("\\bqto\\b", "quanto").replaceAll("\\bqdo\\b", "quando")
                .replaceAll("\\bq horas\\b", "que horas").replaceAll("\\bprox\\b", "proximo").replaceAll("\\bbus\\b", "onibus");
        if (REGRA.matcher(t).find() || t.contains("ignore") || t.contains("instrucoes")) return Optional.empty();
        Contexto c = anterior == null ? Contexto.vazio() : anterior;
        if (t.matches(".*\\b(chuva|chover|futebol|receita|capital|presidente)\\b.*")) return Optional.empty();
        if (t.matches(".*\\b(perto de mim|perto daqui|aqui perto|proximo de mim|proximos de mim|onde estou|minha localizacao|mais perto)\\b.*")) {
            // A localização só é pedida e usada na tela de busca; o chat não recebe coordenadas.
            return Optional.of(resposta("Posso mostrar os pontos perto de você e as linhas de cada um. Toque em Pontos perto de mim; "
                    + "a localização é usada só para essa busca e não fica guardada. Se preferir, diga o nome da rua com o número.",
                    c, List.of(new Acao("Pontos perto de mim", null, "/busca?perto=1"))));
        }
        var mp = PONTO.matcher(t);
        var ml = LINHA.matcher(t);
        Long pontoExplicito = mp.find() ? Long.parseLong(mp.group(1)) : null;
        String linhaExplicita = ml.find() ? ml.group(1).toUpperCase(Locale.ROOT) : null;
        if (linhaExplicita == null && ("LINHA".equals(c.pendencia()) || "PONTO_EMBARQUE".equals(c.pendencia())) && t.matches("\\d{3,4}[a-z]?")) linhaExplicita = t.toUpperCase(Locale.ROOT);
        if (linhaExplicita == null && t.matches(".*\\b(linha|busao|onibus)\\s+\\d{3,4}[a-z]?\\b.*")) {
            var prefixo = Pattern.compile("\\b(?:linha|busao|onibus)\\s+(\\d{3,4}[a-z]?)\\b").matcher(t);
            if (prefixo.find()) linhaExplicita = prefixo.group(1).toUpperCase(Locale.ROOT);
        }
        if (linhaExplicita == null && TEMPO.matcher(t).find()) {
            // "quanto falta pro 875A": número solto só vale como linha se existir no cadastro.
            var solto = Pattern.compile("\\b(?:pro|pra|para o|para a|do|da|o|a)\\s+(\\d{3,4}[a-z]?)\\b").matcher(t);
            if (solto.find() && transporte.usaCadastro(null) && !transporte.rede().letreirosPorNumero(solto.group(1)).isEmpty()) {
                linhaExplicita = solto.group(1).toUpperCase(Locale.ROOT);
            }
        }
        boolean contrario = t.contains("contrario") || t.contains("volta");
        boolean destino = t.matches(".*\\b(destino|sentido|vai pra|vai para|pra onde|para onde|itinerario|trajeto)\\b.*");
        // "ônibus" sozinho não basta: "qual a cor do ônibus..." não é consulta ao ponto e segue para a GenAI.
        // Perguntas elípticas ("quais ônibus?") continuam valendo, apoiadas no ponto do contexto.
        boolean linhasPonto = (t.matches(".*\\blinhas\\b.*") || t.matches("^(?:e )?(?:quais|qual) (?:os |o )?(?:onibus|busoes)[?!.]*$")
                || t.matches(".*\\b(onibus|busoes)\\b.*")
                && t.matches(".*\\b(passa|passam|para|param|atende|atendem|tem|aqui|ponto|parada|vai|vao|sai|saem|pego|pegar|pegam)\\b.*")) &&
                (t.contains("quais") || t.contains("qual") || t.contains("linhas do") || t.contains("linhas nesse")) && linhaExplicita == null;
        boolean tempo = TEMPO.matcher(t).find();
        boolean pontoNome = t.matches(".*\\b(ponto|parada|pto)\\b.*");
        boolean rota = FerramentasRota.perguntaDeRota(t);
        // Uma pergunta explícita de trajeto interrompe a escolha de referência de embarque.
        boolean respostaPendente = c.pendencia() != null && t.length() < 120 && !tempo && !destino && !contrario && !linhasPonto && !rota && !t.startsWith("onde ");
        boolean embarque = t.matches(".*\\bonde\\b.*\\b(pegar|pego|embarcar|embarco)\\b.*");
        boolean seguimento = t.matches("^(e |esse |essa |ele |ela |nesse |nessa ).*");
        // Lugar dito sem a palavra "ponto": "... na paulista 1374", "... na avenida paulista".
        String lugarDito = null;
        var lugar = Pattern.compile("\\b(?:na|no|em|perto d[aeo])\\s+([a-z][a-z0-9 .,]{2,60})$").matcher(t.replaceAll("[?!.]+$", "").strip());
        if (tempo && pontoExplicito == null && !pontoNome && !rota && lugar.find()
                && !lugar.group(1).matches("^(sentido|linha|ponto|parada|minutos?|breve|seguida)\\b.*")) lugarDito = lugar.group(1);
        String viaPerguntada = FerramentasRota.viaPerguntada(t);
        if (!(rota || pontoExplicito != null || linhaExplicita != null || contrario || destino && (c.linha() != null || seguimento)
                || tempo || linhasPonto || pontoNome || respostaPendente || embarque)) return Optional.empty();

        Long ponto = pontoExplicito != null ? pontoExplicito : c.ponto();
        String linha = linhaExplicita != null ? linhaExplicita : c.linha();
        Integer sentido = linhaExplicita != null && !linhaExplicita.equals(c.linha()) ? null : c.sentido();
        var sentidoExplicito = Pattern.compile("\\b(?:no )?sentido ([12])\\b").matcher(t);
        if (sentidoExplicito.find()) sentido = Integer.parseInt(sentidoExplicito.group(1));
        // Consultar a previsão num novo ponto continua a linha/direção escolhida.
        // Só uma consulta geral ao ponto inicia outro contexto de transporte.
        if (linhasPonto || pontoExplicito != null && !tempo && !respostaPendente && !seguimento && linhaExplicita == null) { linha = null; sentido = null; }
        String tarefa = tempo ? "PONTO_PREVISAO" : linhasPonto ? "PONTO_LINHAS" : respostaPendente ? c.pendencia() : "PONTO";
        Contexto atual = new Contexto(ponto, linha, sentido, null, null);
        try {
            if (embarque || "PONTO_EMBARQUE".equals(c.pendencia()) && (respostaPendente || t.matches("^sentido [12](?: da linha .+)?$"))) {
                String referencia = respostaPendente && linhaExplicita == null ? t : "";
                var localEmbarque = Pattern.compile("\\b(?:na|no|em|perto d[aeo])\\s+(.+?)[?!.]*$").matcher(t);
                if (embarque && localEmbarque.find()) referencia = localEmbarque.group(1);
                return Optional.of(embarque(new Contexto(ponto, linha, sentido, "PONTO_EMBARQUE", null), referencia));
            }
            if (rota && viaPerguntada == null && linhaExplicita == null) {
                var direta = FerramentasRota.linhaDireta(transporte, t, c);
                if (direta.isPresent()) return Optional.of(resposta(direta.get().texto(), direta.get().contexto(), direta.get().acoes()));
            }
            if (viaPerguntada != null && linha == null) {
                return Optional.of(resposta("De qual linha você está falando? Diga o número que aparece no letreiro, como 875A-10.",
                        new Contexto(ponto, null, null, "LINHA", null), List.of()));
            }
            var destinoBusca = Pattern.compile("(?:vao|vai|vou|ir) (?:para|pra|pro|ao|a) (.+?)[?!.]*$").matcher(t);
            if (linha == null && destinoBusca.find()) {
                String termo = destinoBusca.group(1).replaceFirst("^(o |a |os |as )", "");
                var encontradas = transporte.buscarLinhas(termo, null).linhas();
                if (encontradas.isEmpty()) return Optional.of(resposta("Não encontrei linha com esse destino no cadastro. Diga o nome de um terminal, rua ou ponto de referência.", Contexto.vazio(), List.of()));
                return Optional.of(resposta("Encontrei linhas com esse destino. Escolha uma para conferir as paradas e onde embarcar.", Contexto.vazio(),
                        encontradas.stream().limit(6).map(l -> new Acao(l.letreiro() + " · " + l.destino(), "sentido " + l.sentido() + " da linha " + l.letreiro(), null)).toList()));
            }
            var via = Pattern.compile("(?:passa (?:na|no|pela|pelo|em)|vai (?:para|pra|pro)) (.+?)[?!.]*$").matcher(t);
            if (linha != null && via.find() && transporte.usaCadastro(null)) {
                String termo = via.group(1).replaceFirst("^(o |a )", "");
                var it = transporte.itinerario(linha, null);
                var encontrados = new ArrayList<Acao>();
                var direcoes = new LinkedHashSet<String>();
                for (var s : it.sentidos()) {
                    if (sentido != null && s.sentido() != sentido) continue;
                    for (var p : s.paradas()) {
                        if (FerramentasRota.lugarCasa(p, termo)) {
                            direcoes.add(s.destino());
                            if (encontrados.size() < 6) encontrados.add(new Acao(p.nome() + " · " + s.destino(),
                                    "previsão da linha " + linha + " no ponto " + p.codigo() + " no sentido " + s.sentido(), null));
                        }
                    }
                    if (RedeGtfs.tokens(s.destino()).containsAll(RedeGtfs.tokens(termo)) && !RedeGtfs.tokens(termo).isEmpty()) direcoes.add(s.destino());
                }
                if (!direcoes.isEmpty()) return Optional.of(resposta("Sim. O cadastro da linha " + linha + " indica " + termo + " no sentido " + String.join("; ", direcoes) + ". Escolha a parada para consultar a previsão.", atual, encontrados));
                return Optional.of(resposta("Os destinos cadastrados da linha " + linha + " são " + String.join("; ", it.sentidos().stream().map(SentidoLinha::destino).toList())
                        + ". Não confirmei \"" + termo + "\" pelo nome das paradas. Diga uma rua ou referência mais específica, ou confira o itinerário.", atual,
                        List.of(new Acao("Conferir itinerário", null, "/linha/" + it.letreiro()))));
            }
            var escolha = Pattern.compile("^sentido ([12])(?: da linha .+)?$").matcher(t);
            if (escolha.matches() && linha != null && transporte.usaCadastro(null)) {
                int numero = Integer.parseInt(escolha.group(1));
                var it = transporte.itinerario(linha, null);
                var s = it.sentidos().stream().filter(x -> x.sentido() == numero).findFirst();
                if (s.isPresent()) {
                    Long escolhido = ponto;
                    if (escolhido != null && s.get().paradas().stream().noneMatch(p -> p.codigo() == escolhido)) ponto = null;
                    return Optional.of(descrever(s.get(), new Contexto(ponto, linha, numero, null, null)));
                }
            }
            if (contrario || destino && !tempo || linhaExplicita != null && !tempo && !pontoNome && pontoExplicito == null) {
                if (linha == null) return Optional.of(resposta("Qual é o número da linha?", new Contexto(ponto, null, null, "LINHA", null), List.of()));
                if (!transporte.usaCadastro(null)) return Optional.empty();
                var it = transporte.itinerario(linha, null);
                if (contrario) {
                    if (sentido == null && ponto != null) sentido = FerramentasRota.sentidoNoPonto(transporte.rede(), it.letreiro(), ponto);
                    if (sentido != null && ponto != null) {
                        var oposto = FerramentasRota.pontoDoSentidoContrario(transporte.rede(), it.letreiro(), ponto, sentido);
                        if (oposto.isPresent()) {
                            var o = oposto.get();
                            var previsao = formatador.previsoes("ponto " + o.parada().codigo(), "ponto " + o.parada().codigo(), it.letreiro(), o.sentido());
                            String inicio = "No sentido contrário (" + o.destino() + "), o ponto mais próximo da linha " + it.letreiro()
                                    + " é " + o.parada().nome() + ", a " + o.metros() + " metros. ";
                            return Optional.of(new RespostaChat(inicio + previsao.resposta(), previsao.fontes(), previsao.confianca(),
                                    previsao.naoConsta(), previsao.disponivel(), previsao.latenciaMs(), previsao.origem(),
                                    previsao.contexto(), acoesPonto(o.parada().codigo())));
                        }
                    }
                    if (sentido == null) return Optional.of(escolherSentido(it, atual));
                    int outro = sentido == 1 ? 2 : 1;
                    var s = it.sentidos().stream().filter(x -> x.sentido() == outro).findFirst();
                    if (s.isEmpty()) return Optional.of(resposta("O cadastro não informa o sentido contrário desta linha.", atual, List.of()));
                    // O ponto da ida pode não atender a volta. Nunca reutilizá-lo para uma previsão.
                    atual = new Contexto(null, it.letreiro(), outro, null, null);
                    return Optional.of(descrever(s.get(), atual));
                }
                if (sentido == null && it.sentidos().size() > 1) return Optional.of(escolherSentido(it, new Contexto(ponto, it.letreiro(), null, null, null)));
                var selecionado = sentido;
                var s = it.sentidos().stream().filter(x -> selecionado == null || x.sentido() == selecionado).findFirst();
                if (s.isEmpty()) return Optional.of(escolherSentido(it, atual));
                return Optional.of(descrever(s.get(), new Contexto(ponto, it.letreiro(), s.get().sentido(), null, null)));
            }
            // Uma referência nova ao ponto deve ser pesquisada mesmo em perguntas de seguimento
            // ("e no ponto da Paulista?"). Referências sem nome ("e nesse ponto?") mantêm o contexto.
            String termoPonto = pontoNome ? AssistenteTempoReal.termoDeBusca(pergunta, linha) : "";
            boolean pontoNovoNomeado = pontoNome && !termoPonto.isBlank();
            if (pontoExplicito == null && (lugarDito != null || pontoNovoNomeado || respostaPendente && !"LINHA".equals(c.pendencia()))) {
                String termo = lugarDito != null ? lugarDito : pontoNovoNomeado ? termoPonto : AssistenteTempoReal.termoDeBusca(pergunta, linha);
                if (!termo.isBlank()) {
                    var busca = transporte.buscarPontos(termo, null);
                    if (busca.pontos().isEmpty()) busca = new RespostaPontos(busca.fonte(), formatador.buscarPontos(transporte.escolher(null), termo));
                    // Endereço com número que existe exatamente: é esse ponto, sem pedir para escolher.
                    var numeroDito = Pattern.compile("\\b(\\d{1,6})\\b").matcher(termo);
                    boolean enderecoExato = busca.pontos().size() > 1 && busca.aviso() == null && numeroDito.find()
                            && busca.pontos().getFirst().nome().matches(".*\\b" + numeroDito.group(1) + "\\b.*");
                    if (busca.pontos().size() > 1 && !enderecoExato) {
                        var acoes = busca.pontos().stream().limit(6).map(p -> new Acao(p.nome() + " · " + p.codigo(),
                                "ponto " + p.codigo(), null)).toList();
                        return Optional.of(resposta("Encontrei mais de um ponto. Em qual você está?" + (busca.aviso() == null ? "" : " " + busca.aviso()),
                                new Contexto(null, linha, sentido, tarefa, null), acoes));
                    }
                    if (busca.pontos().isEmpty()) return Optional.of(resposta("Não encontrei um ponto chamado " + termo + ". Diga o código da placa ou outro nome de rua.",
                            new Contexto(null, linha, sentido, tarefa, null), List.of()));
                    ponto = busca.pontos().getFirst().codigo();
                }
            }
            if (linha != null && ponto != null && sentido == null && transporte.usaCadastro(null)) {
                sentido = FerramentasRota.sentidoNoPonto(transporte.rede(), linha, ponto);
            }
            atual = new Contexto(ponto, linha, sentido, null, null);
            if (ponto == null) return Optional.of(resposta(linha == null
                    ? "Para consultar, diga o nome ou o código do ponto."
                    : "Para consultar a linha " + linha + ", preciso do ponto. Qual é o nome ou código?",
                    new Contexto(null, linha, sentido, tarefa, null), List.of()));
            if ("PONTO_PREVISAO".equals(tarefa)) {
                if (linha != null && transporte.usaCadastro(null) && transporte.rede().parada(ponto) != null) {
                    String filtroLinha = linha;
                    Integer filtroSentido = sentido;
                    boolean atende = transporte.linhasDoPonto(ponto, null).linhas().stream().anyMatch(l ->
                            AssistenteTempoReal.mesmaLinha(l.letreiro(), filtroLinha) && (filtroSentido == null || l.sentido() == filtroSentido));
                    if (!atende) return Optional.of(resposta("A linha " + linha + " não aparece neste ponto" + (sentido == null ? "" : " nesse sentido")
                                    + " no cadastro. Escolha uma parada do itinerário para consultar a previsão.",
                            new Contexto(null, linha, sentido, "PONTO_PREVISAO", null), List.of(new Acao("Ver paradas da linha", null, "/linha/" + linha + (sentido == null ? "" : "?sentido=" + sentido)))));
                }
                boolean seguinte = t.matches("^(?:e )?(?:o )?(?:proximo|seguinte)(?: onibus)?[?!.]*$")
                        && Objects.equals(ponto, c.ponto()) && Objects.equals(linha, c.linha()) && Objects.equals(sentido, c.sentido());
                String veiculoAnterior = seguinte ? c.veiculoAnterior() : null;
                atual = new Contexto(ponto, linha, sentido, null, null, null, null, veiculoAnterior);
                var r = formatador.previsoes("ponto " + ponto, "ponto " + ponto, linha, sentido, veiculoAnterior);
                return Optional.of(r.comContexto(r.contexto() == null ? atual : r.contexto(), acoesPonto(ponto)));
            }
            var dados = transporte.linhasDoPonto(ponto, null);
            StringBuilder texto = new StringBuilder();
            var busca = transporte.buscarPontos(String.valueOf(ponto), null);
            if (!busca.pontos().isEmpty()) texto.append(busca.pontos().getFirst().nome()).append(". ");
            if (dados.linhas().isEmpty()) texto.append(dados.aviso());
            else {
                texto.append("Linhas neste ponto (cadastro da SPTrans):\n");
                dados.linhas().stream().limit(12).forEach(l -> texto.append(l.letreiro()).append(" → ").append(l.destino()).append("\n"));
                if (dados.linhas().size() > 12) texto.append("Veja todas as linhas na página do ponto.\n");
            }
            var acoes = new ArrayList<>(acoesPonto(ponto));
            dados.linhas().stream().limit(3).forEach(l -> acoes.add(new Acao(l.letreiro() + " · " + l.destino(),
                    "sentido " + l.sentido() + " da linha " + l.letreiro(), null)));
            return Optional.of(resposta(texto.toString().strip(), atual, acoes));
        } catch (TransporteIndisponivelException e) {
            return Optional.of(new RespostaChat("Não consegui consultar a SPTrans agora. Tente novamente em instantes; não há previsão confirmada.",
                    List.of(), "baixa", false, false, null, "TEMPO_REAL", atual, List.of(new Acao("Tentar novamente", pergunta, null))));
        } catch (ErroApi e) {
            return Optional.of(resposta(e.getMessage(), atual, List.of()));
        }
    }

    private RespostaChat embarque(Contexto c, String referencia) {
        if (c.linha() == null) return resposta("Qual é o número da linha em que você quer embarcar?", c, List.of());
        if (!transporte.usaCadastro(null)) return resposta("Consulte as paradas na busca para escolher onde embarcar na demonstração.", c,
                List.of(new Acao("Buscar pontos", null, "/busca")));
        var it = transporte.itinerario(c.linha(), null);
        Long origem = c.ponto();
        if (!referencia.isBlank()) {
            String termo = referencia.replaceFirst("^(?:estou |fico )?(?:na |no |em )", "")
                    .replaceFirst("^(?:ponto|parada)\\s+", "");
            var busca = transporte.buscarPontos(termo, null);
            var numero = Pattern.compile("\\b\\d{1,10}\\b").matcher(termo);
            boolean exato = numero.find() && busca.aviso() == null && !busca.pontos().isEmpty()
                    && (busca.pontos().size() == 1 || busca.pontos().getFirst().nome().matches(".*\\b" + numero.group() + "\\b.*"));
            if (busca.pontos().size() != 1 && !exato) return resposta(busca.pontos().isEmpty()
                            ? "Não encontrei essa referência. Diga uma rua com número ou o código do ponto."
                            : "Encontrei mais de um ponto nessa região. Escolha sua referência para buscar o embarque.",
                    new Contexto(null, it.letreiro(), c.sentido(), "PONTO_EMBARQUE", null),
                    busca.pontos().stream().limit(6).map(p -> new Acao(p.nome(), "ponto " + p.codigo(), null)).toList());
            origem = busca.pontos().getFirst().codigo();
        }
        var memoria = new Contexto(origem, it.letreiro(), c.sentido(), "PONTO_EMBARQUE", null);
        if (c.sentido() == null && it.sentidos().size() > 1) return escolherSentido(it, memoria);
        if (origem == null) return resposta("Em qual rua, número ou ponto de referência você está? Vou procurar onde embarcar na linha " + it.letreiro() + ".", memoria,
                List.of(new Acao("Ver paradas da linha", null, "/linha/" + it.letreiro()), new Acao("Pontos perto de mim", null, "/busca?perto=1")));
        var local = transporte.rede().parada(origem);
        if (local == null) return resposta("Esse ponto não aparece no cadastro. Diga uma rua com número ou outro código.",
                new Contexto(null, it.letreiro(), c.sentido(), "PONTO_EMBARQUE", null), List.of());
        var sentido = it.sentidos().stream().filter(s -> c.sentido() == null || s.sentido() == c.sentido()).findFirst();
        if (sentido.isEmpty()) return escolherSentido(it, memoria);
        var s = sentido.get();
        var proximas = s.paradas().stream().filter(p -> p.latitude() != null && p.longitude() != null)
                .filter(p -> RedeGtfs.metros(local.latitude(), local.longitude(), p.latitude(), p.longitude()) <= 600)
                .sorted(Comparator.comparingInt(p -> RedeGtfs.metros(local.latitude(), local.longitude(), p.latitude(), p.longitude())))
                .limit(6).toList();
        if (proximas.isEmpty()) return resposta("Não encontrei parada dessa linha nesse sentido a até 600 metros da referência. Confira o itinerário ou diga outra rua.", memoria,
                List.of(new Acao("Ver paradas da linha", null, "/linha/" + it.letreiro() + "?sentido=" + s.sentido())));
        return resposta("Você pode embarcar na linha " + it.letreiro() + ", sentido " + s.destino() + ", nestas paradas próximas de " + local.nome()
                        + ": " + String.join("; ", proximas.stream().map(Ponto::nome).toList()) + ". Distância em linha reta; confira o acesso a pé. Escolha uma parada para consultar a previsão.",
                new Contexto(origem, it.letreiro(), s.sentido(), "PONTO_EMBARQUE", null), proximas.stream()
                        .map(p -> new Acao(p.nome(), "previsão da linha " + it.letreiro() + " no ponto " + p.codigo() + " no sentido " + s.sentido(), null)).toList());
    }

    private RespostaChat escolherSentido(RespostaItinerario it, Contexto c) {
        String destinos = String.join("; ", it.sentidos().stream().map(s -> "sentido " + s.destino()).toList());
        return resposta("A linha " + it.letreiro() + " tem estes destinos no cadastro: " + destinos
                        + ". Qual sentido você quer consultar? Para confirmar uma região como Centro, diga a rua ou parada de destino.", c,
                it.sentidos().stream().map(s -> new Acao(s.destino(), "sentido " + s.sentido() + " da linha " + it.letreiro(), null)).toList());
    }

    private RespostaChat descrever(SentidoLinha s, Contexto c) {
        return resposta("Linha " + s.letreiro() + ", sentido " + s.destino() + ": " + s.paradas().size()
                        + " paradas no cadastro oficial. Consulte as paradas para escolher onde embarcar.", c,
                List.of(new Acao("Ver paradas e previsões", null, "/linha/" + s.letreiro() + "?sentido=" + s.sentido()),
                        new Acao("Próximo ônibus", "e o próximo?", null), new Acao("Sentido contrário", "e no sentido contrário?", null)));
    }

    private List<Acao> acoesPonto(long ponto) {
        return List.of(new Acao("Ver ponto e previsões", null, "/ponto/" + ponto), new Acao("Próximos ônibus", "e o próximo?", null));
    }

    private RespostaChat resposta(String texto, Contexto c, List<Acao> acoes) {
        boolean demo = transporte.escolher(null).fonte() == Fonte.SIMULADO;
        return new RespostaChat((demo ? "Atenção: dados simulados. " : "") + texto,
                List.of(new FonteCitada(demo ? "Dados simulados" : "SPTrans — cadastro oficial GTFS", "",
                        demo ? null : "https://www.sptrans.com.br/desenvolvedores/")), "alta", false, true, null,
                "CADASTRO", c, acoes);
    }
}
