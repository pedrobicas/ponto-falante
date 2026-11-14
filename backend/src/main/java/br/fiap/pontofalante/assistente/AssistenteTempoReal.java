package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.FonteCitada;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.FraseFalada;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Linha;
import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.ProvedorTransporte;
import br.fiap.pontofalante.transporte.TransporteIndisponivelException;
import br.fiap.pontofalante.transporte.TransporteService;
import org.springframework.stereotype.Component;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Responde perguntas de tempo real (próximos ônibus num ponto, dados de uma linha) com os serviços do backend,
 * sem LLM: horário e previsão nunca são gerados por modelo. Perguntas que não são de tempo real seguem para a GenAI.
 * Toda resposta diz a origem (SPTrans em tempo real ou dados simulados) e fala "previsto", nunca "chegou".
 */
@Component
public class AssistenteTempoReal {
    static final String ORIGEM = "TEMPO_REAL";
    private static final int MAX_ONIBUS = 4;

    private static final Pattern CODIGO_PONTO = Pattern.compile("\\b(\\d{6,10})\\b");
    private static final Pattern NUMERO_LINHA = Pattern.compile("\\b(\\d{3,4}[a-z]?)(?:-(\\d{1,2}))?\\b");
    private static final Pattern PONTO = Pattern.compile("\\b(ponto|parada|pto)\\b");
    private static final Pattern TEMPO = Pattern.compile(
            "\\b(quando|que horas|horario|horarios|proximo|proximos|proxima|passa|passam|passando|chega|chegam|chegar|demora|demoram|falta|faltam|previs[aã]o|previsto|vem|vai passar|tempo real|agora)\\b");
    private static final Pattern LINHA_PALAVRA = Pattern.compile("\\b(linha|onibus|busao|buzao)\\b");
    private static final Pattern LINHA_INFO = Pattern.compile(
            "\\b(itinerario|trajeto|vai para|vai pra|sentido|destino|terminal|terminais|onde vai|para onde|pra onde|faz|liga)\\b");
    /** Perguntas sobre regras e direitos vão para a GenAI mesmo citando ponto ou ônibus. */
    private static final Pattern REGRAS = Pattern.compile(
            "\\b(gratuidade|gratuito|gratis|idoso|idosos|idosa|direito|direitos|bilhete|tarifa|deficiencia|deficiente|"
            + "cartao|carteira|custa|preco|pagar|paga|acompanhante|assento|lei|regra|regras|integracao|estudante|"
            + "recarga|credito|reclamacao|denuncia|descer|desembarque|desembarcar|embarque|embarcar|sinal|"
            + "parar fora|fora do ponto|motorista|cobrador)\\b");
    private static final Set<String> VAZIAS = Set.of(
            "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "no", "na", "nos", "nas", "em", "para",
            "pra", "pro", "por", "que", "qual", "quais", "e", "eu", "me", "meu", "minha", "esta", "esse", "essa", "este",
            "ponto", "parada", "pto", "onibus", "busao", "buzao", "linha", "quando", "horas", "horario", "horarios",
            "proximo", "proximos", "proxima", "passa", "passam", "passando", "chega", "chegam", "chegar", "demora",
            "demoram", "falta", "faltam", "previsao", "previsto", "vem", "vai", "passar", "tempo", "real", "agora",
            "aqui", "ai", "la", "hoje", "por favor", "favor", "quero", "saber", "sabe", "dizer", "diga", "fala", "fale",
            "tem", "ha", "algum", "alguma", "com", "ao", "estou", "to", "tô", "ja", "ainda", "mais", "minutos",
            "onde", "fica", "ficam", "encontro", "encontrar", "linhas", "nesse", "nessa", "querover");

    private final TransporteService transporte;

    public AssistenteTempoReal(TransporteService transporte) {
        this.transporte = transporte;
    }

    /** Pergunta de tempo real respondida pelo backend; vazio quando a pergunta deve ir para a GenAI. */
    public Optional<RespostaChat> responder(String pergunta) {
        return responder(pergunta, null);
    }

    public Optional<RespostaChat> responder(String pergunta, Chat.Contexto contexto) {
        var conversa = new ConversaTransporte(transporte, this).responder(pergunta, contexto);
        return conversa.isPresent() ? conversa : responderLegado(pergunta);
    }

    private Optional<RespostaChat> responderLegado(String pergunta) {
        if (pergunta == null || pergunta.isBlank()) {
            return Optional.empty();
        }
        String t = normalizar(pergunta);
        if (REGRAS.matcher(t).find()) {
            return Optional.empty();
        }
        boolean falaDePonto = PONTO.matcher(t).find();
        boolean falaDeTempo = TEMPO.matcher(t).find();
        Matcher numLinha = NUMERO_LINHA.matcher(t);
        String linha = null;
        while (numLinha.find()) {
            if (numLinha.group(1).length() <= 5) {
                // Código completo quando há sufixo ("8000-21"); só o prefixo é ambíguo e mostra as variantes.
                linha = (numLinha.group(2) == null ? numLinha.group(1) : numLinha.group(1) + "-" + numLinha.group(2))
                        .toUpperCase(Locale.ROOT);
                break;
            }
        }
        boolean falaDeLinha = LINHA_PALAVRA.matcher(t).find() && linha != null;
        try {
            if (falaDePonto && falaDeTempo) {
                return Optional.of(previsoes(pergunta, t, falaDeLinha ? linha : null));
            }
            if (falaDeLinha && LINHA_INFO.matcher(t).find()) {
                return Optional.of(dadosDaLinha(linha));
            }
            if (falaDeLinha && falaDeTempo) {
                return Optional.of(resposta("Para dizer quando a linha " + linha + " passa, preciso do ponto. "
                        + "Pergunte, por exemplo: quando passa a linha " + linha + " no ponto Paulista?",
                        transporte.escolher(null).fonte(), false));
            }
        } catch (TransporteIndisponivelException e) {
            return Optional.of(new RespostaChat("Não consegui consultar a SPTrans agora, então não sei os horários. "
                    + "Tente de novo em alguns instantes.", List.of(), "baixa", false, false, null, ORIGEM));
        }
        return Optional.empty();
    }

    RespostaChat previsoes(String original, String t, String filtroLinha) {
        return previsoes(original, t, filtroLinha, null);
    }

    RespostaChat previsoes(String original, String t, String filtroLinha, Integer sentido) {
        return previsoes(original, t, filtroLinha, sentido, null);
    }

    RespostaChat previsoes(String original, String t, String filtroLinha, Integer sentido, String veiculoAnterior) {
        ProvedorTransporte provedor = transporte.escolher(null);
        Ponto ponto;
        List<Ponto> alternativas = List.of();
        Matcher cod = CODIGO_PONTO.matcher(t);
        if (cod.find()) {
            ponto = new Ponto(Long.parseLong(cod.group(1)), "", null, null, null, provedor.fonte());
        } else {
            String termo = termoDeBusca(original, filtroLinha);
            if (termo.length() < 2) {
                return resposta("Para ver os próximos ônibus, diga o nome ou o código do ponto. "
                        + "Por exemplo: quando passa o ônibus no ponto Paulista?", provedor.fonte(), false);
            }
            List<Ponto> pontos = buscarPontos(provedor, termo);
            if (pontos.isEmpty()) {
                return resposta("Não encontrei um ponto chamado " + termo + ". Tente outro nome de rua, avenida "
                        + "ou o código do ponto.", provedor.fonte(), false);
            }
            ponto = pontos.getFirst();
            alternativas = pontos.subList(1, Math.min(pontos.size(), 3));
        }
        PrevisoesPonto p;
        try {
            p = transporte.previsoes(ponto.codigo(), null);
        } catch (TransporteIndisponivelException e) {
            throw e;
        } catch (ErroApi e) {
            return resposta("Não encontrei esse ponto na SPTrans.", provedor.fonte(), false);
        }
        List<OnibusPrevisto> onibus = new ArrayList<>(p.onibus());
        if (filtroLinha != null) {
            onibus.removeIf(o -> !mesmaLinha(o.letreiro(), filtroLinha));
        }
        if (sentido != null) onibus.removeIf(o -> !sentido.equals(o.sentido()));
        onibus.sort(java.util.Comparator.comparingInt(OnibusPrevisto::minutos));
        // O cursor identifica apenas o ônibus; horários são sempre consultados novamente.
        boolean referenciaEncontrada = false;
        if (veiculoAnterior != null) {
            for (int i = 0; i < onibus.size(); i++) {
                if (veiculoAnterior.equals(onibus.get(i).veiculo())) {
                    onibus.subList(0, i + 1).clear();
                    referenciaEncontrada = true;
                    break;
                }
            }
        }
        boolean simulado = p.fonte() == Fonte.SIMULADO;
        StringBuilder sb = new StringBuilder();
        if (simulado) {
            sb.append("Atenção: dados simulados, não são horários reais. ");
        }
        String nome = p.ponto().nome() == null || p.ponto().nome().isBlank() ? "informado" : legivel(p.ponto().nome());
        sb.append("Ponto ").append(nome);
        if (p.ponto().endereco() != null && !p.ponto().endereco().isBlank()) {
            sb.append(", ").append(legivel(p.ponto().endereco()));
        }
        sb.append(". ");
        if (veiculoAnterior != null && !referenciaEncontrada && !onibus.isEmpty()) {
            sb.append("A previsão anterior não aparece mais na consulta atual. Mostro os próximos disponíveis. ");
        }
        if (onibus.isEmpty()) {
            sb.append(veiculoAnterior != null ? "Não há outra previsão disponível depois do ônibus consultado. Isso não confirma que não haverá outro ônibus. "
                    : filtroLinha == null ? "Não há ônibus previstos agora. "
                    : "Não há previsão para a linha " + filtroLinha + " neste ponto agora. ");
        } else {
            int n = Math.min(MAX_ONIBUS, onibus.size());
            for (int i = 0; i < n; i++) {
                OnibusPrevisto o = onibus.get(i);
                sb.append("Linha ").append(o.letreiro());
                if (o.destino() != null && !o.destino().isBlank()) {
                    sb.append(", sentido ").append(legivel(o.destino()));
                }
                sb.append(", previsto em ").append(o.minutos() == 1 ? "1 minuto" : o.minutos() + " minutos");
                if (o.acessivel()) {
                    sb.append(", acessível para cadeira de rodas");
                }
                sb.append(". ");
            }
            if (onibus.size() > n) {
                sb.append("Há mais ").append(onibus.size() - n).append(" previstos na tela do ponto. ");
            }
            if (p.horarioReferencia() != null && !p.horarioReferencia().isBlank()) {
                sb.append("Previsão da SPTrans calculada às ").append(p.horarioReferencia()).append(". ");
            }
        }
        if (!alternativas.isEmpty()) {
            sb.append("Encontrei também: ");
            List<String> nomes = new ArrayList<>();
            for (Ponto a : alternativas) {
                nomes.add(legivel(a.nome()) + " (código " + a.codigo() + ")");
            }
            sb.append(String.join("; ", nomes)).append(". ");
        }
        String referencia = onibus.isEmpty() ? veiculoAnterior : onibus.getFirst().veiculo();
        if (referencia != null && !referencia.matches("[a-f0-9]{10}")) referencia = null;
        return resposta(sb.toString().trim(), p.fonte(), false).comContexto(
                new Chat.Contexto(ponto.codigo(), filtroLinha, sentido, null, null, null, null, referencia), List.of());
    }

    /**
     * A busca da SPTrans é por trecho contínuo do nome; "paulista trianon" não acha "PAULISTA - TRIANON". Sem resultado,
     * busca pela palavra mais longa e ordena pelos pontos que contêm mais palavras da pergunta.
     */
    List<Ponto> buscarPontos(ProvedorTransporte provedor, String termo) {
        List<Ponto> pontos = transporte.buscarPontos(termo, null).pontos();
        String[] palavras = normalizar(termo).split(" ");
        if (!pontos.isEmpty() || palavras.length < 2) {
            return pontos;
        }
        String maior = "";
        for (String p : palavras) {
            if (p.length() > maior.length()) {
                maior = p;
            }
        }
        if (maior.length() < 3) {
            return pontos;
        }
        List<Ponto> candidatos = new ArrayList<>(transporte.buscarPontos(maior, null).pontos());
        candidatos.sort((a, b) -> Integer.compare(acertos(b, palavras), acertos(a, palavras)));
        int melhor = candidatos.isEmpty() ? 0 : acertos(candidatos.getFirst(), palavras);
        candidatos.removeIf(p -> acertos(p, palavras) < melhor || melhor < 2);
        return candidatos;
    }

    private static int acertos(Ponto p, String[] palavras) {
        String alvo = normalizar((p.nome() == null ? "" : p.nome()) + " " + (p.endereco() == null ? "" : p.endereco()));
        int n = 0;
        for (String w : palavras) {
            if (alvo.contains(w)) {
                n++;
            }
        }
        return n;
    }

    private RespostaChat dadosDaLinha(String linha) {
        ProvedorTransporte provedor = transporte.escolher(null);
        List<Linha> linhas = transporte.buscarLinhas(linha, null).linhas();
        if (linhas.isEmpty()) {
            return resposta("Não encontrei a linha " + linha + ".", provedor.fonte(), false);
        }
        StringBuilder sb = new StringBuilder();
        if (provedor.fonte() == Fonte.SIMULADO) {
            sb.append("Atenção: dados simulados. ");
        }
        List<String> vistos = new ArrayList<>();
        for (Linha l : linhas) {
            String chave = l.letreiro();
            if (!mesmaLinha(chave, linha)) {
                continue;
            }
            if (vistos.contains(chave) || vistos.size() >= 3) {
                continue;
            }
            vistos.add(chave);
            sb.append("Linha ").append(l.letreiro());
            if (l.circular()) {
                sb.append(", circular a partir de ").append(legivel(l.terminalPrincipal()));
            } else {
                sb.append(", entre ").append(legivel(l.terminalPrincipal())).append(" e ")
                        .append(legivel(l.terminalSecundario()));
            }
            sb.append(". ");
        }
        if (vistos.isEmpty()) {
            return resposta("Não encontrei a linha " + linha + ".", provedor.fonte(), false);
        }
        sb.append("Para saber quando ela passa, pergunte com o nome do ponto.");
        return resposta(sb.toString(), provedor.fonte(), false);
    }

    /** Com sufixo ("8000-21") exige igualdade; só o prefixo ("8000") aceita todas as variantes, que aparecem por extenso. */
    static boolean mesmaLinha(String letreiro, String pedido) {
        String l = letreiro == null ? "" : letreiro.toUpperCase(Locale.ROOT);
        return pedido.contains("-") ? l.equals(pedido) : l.startsWith(pedido + "-") || l.equals(pedido);
    }

    private static RespostaChat resposta(String texto, Fonte fonte, boolean falha) {
        List<FonteCitada> fontes = fonte == null ? List.of()
                : List.of(new FonteCitada(fonte == Fonte.SIMULADO ? "Dados simulados (demonstração)"
                : "SPTrans Olho Vivo, tempo real", "", fonte == Fonte.SIMULADO ? null : "https://www.sptrans.com.br/olho-vivo/"));
        return new RespostaChat(texto, fontes, falha ? "baixa" : "alta", false, true, null, ORIGEM);
    }

    /** Nome do ponto: palavras da pergunta original (com acentos), sem as palavras de ligação e de intenção. */
    static String termoDeBusca(String original, String linha) {
        String semPontuacao = original.toLowerCase(Locale.ROOT).replaceAll("[?!.,;:]", " ");
        List<String> palavras = new ArrayList<>();
        for (String p : semPontuacao.split("\\s+")) {
            String n = normalizar(p);
            if (p.isBlank() || VAZIAS.contains(n) || (linha != null && n.equalsIgnoreCase(linha))) {
                continue;
            }
            palavras.add(p);
        }
        return String.join(" ", palavras).trim();
    }

    static String normalizar(String s) {
        String n = Normalizer.normalize(s.toLowerCase(Locale.ROOT), Normalizer.Form.NFD).replaceAll("\\p{M}", "");
        return n.replaceAll("\\s+", " ").trim();
    }

    private static String legivel(String s) {
        return s == null ? "" : FraseFalada.legivelPublico(s);
    }
}
