package br.fiap.pontofalante.transporte;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.GZIPInputStream;

/**
 * Índice em memória da rede de ônibus (GTFS oficial da SPTrans, compactado por scripts/dados/preparar_rede_gtfs.py).
 *
 * Existe porque a busca de paradas da Olho Vivo só encontra as cerca de 360 paradas com nome e, para qualquer
 * número, devolve todas elas. Aqui ficam todas as paradas atendidas por ônibus (nome, referência, coordenadas) e a
 * sequência de paradas de cada linha e sentido. Nada é inventado: o que não está no GTFS não aparece.
 */
@Component
public class RedeGtfs {
    private static final Logger log = LoggerFactory.getLogger(RedeGtfs.class);

    public record Parada(long codigo, String nome, String referencia, double latitude, double longitude) {
    }

    /** Uma linha em um sentido, com as paradas em ordem. */
    public record Viagem(String letreiro, int sentido, String destino, String nomeLinha, long[] paradas) {
    }

    public record ParadaEncontrada(Parada parada, int pontos, Integer distanciaMetros) {
    }

    private static final Map<String, String> ABREVIACOES = Map.ofEntries(
            Map.entry("r", "rua"), Map.entry("av", "avenida"), Map.entry("avda", "avenida"), Map.entry("aven", "avenida"),
            Map.entry("estr", "estrada"), Map.entry("est", "estrada"), Map.entry("pca", "praca"), Map.entry("pc", "praca"),
            Map.entry("al", "alameda"), Map.entry("tr", "travessa"), Map.entry("tv", "travessa"), Map.entry("trav", "travessa"),
            Map.entry("lgo", "largo"), Map.entry("lg", "largo"), Map.entry("rod", "rodovia"), Map.entry("viad", "viaduto"),
            Map.entry("vd", "viaduto"), Map.entry("term", "terminal"), Map.entry("pq", "parque"), Map.entry("pque", "parque"),
            Map.entry("jd", "jardim"), Map.entry("vl", "vila"), Map.entry("sta", "santa"), Map.entry("sto", "santo"),
            Map.entry("nsa", "nossa"), Map.entry("ns", "nossa"), Map.entry("sra", "senhora"), Map.entry("sr", "senhor"),
            Map.entry("dr", "doutor"), Map.entry("dra", "doutora"), Map.entry("prof", "professor"),
            Map.entry("profa", "professora"), Map.entry("eng", "engenheiro"), Map.entry("cel", "coronel"),
            Map.entry("cap", "capitao"), Map.entry("gal", "general"), Map.entry("gen", "general"),
            Map.entry("mal", "marechal"), Map.entry("pres", "presidente"), Map.entry("gov", "governador"),
            Map.entry("dep", "deputado"), Map.entry("ver", "vereador"), Map.entry("brig", "brigadeiro"),
            Map.entry("cons", "conselheiro"), Map.entry("des", "desembargador"), Map.entry("pe", "padre"),
            Map.entry("cb", "cabo"), Map.entry("sgt", "sargento"), Map.entry("ten", "tenente"),
            Map.entry("min", "ministro"), Map.entry("sen", "senador"), Map.entry("cde", "conde"),
            Map.entry("vsc", "visconde"), Map.entry("mq", "marques"), Map.entry("hosp", "hospital"),
            Map.entry("cptm", "cptm"), Map.entry("metro", "metro"));
    private static final Set<String> VAZIAS = Set.of("de", "da", "do", "das", "dos", "e", "a", "o", "na", "no", "nas",
            "nos", "em", "ref", "numero", "n", "nº", "com", "para", "ponto", "parada");

    private final String recursoBase;
    private volatile boolean carregada;
    private List<Parada> paradas = List.of();
    private List<String[]> tokensNome = List.of();
    private List<String[]> tokensRef = List.of();
    private Map<Long, Integer> indicePorCodigo = Map.of();
    private List<Viagem> viagens = List.of();
    private Map<Long, List<Viagem>> viagensPorParada = Map.of();
    private Map<String, List<Viagem>> viagensPorLetreiro = Map.of();
    private Set<String> vocabulario = Set.of();

    public RedeGtfs() {
        this("/rede/");
    }

    RedeGtfs(String recursoBase) {
        this.recursoBase = recursoBase;
    }

    // ---------- carga ----------

    private void garantirCarga() {
        if (carregada) {
            return;
        }
        synchronized (this) {
            if (carregada) {
                return;
            }
            try {
                carregar();
            } catch (IOException | RuntimeException e) {
                // Sem o índice, a busca segue só com a Olho Vivo; a falha fica registrada, sem derrubar o serviço.
                log.error("Índice da rede (GTFS) indisponível: {}", e.getClass().getSimpleName());
            }
            carregada = true;
        }
    }

    private void carregar() throws IOException {
        List<Parada> ps = new ArrayList<>();
        List<String[]> tn = new ArrayList<>();
        List<String[]> tr = new ArrayList<>();
        Map<Long, Integer> porCodigo = new HashMap<>();
        Set<String> vocab = new LinkedHashSet<>();
        try (BufferedReader r = abrir("paradas.tsv.gz")) {
            String linha;
            while ((linha = r.readLine()) != null) {
                String[] c = linha.split("\t", -1);
                if (c.length < 5) {
                    continue;
                }
                Parada p = new Parada(Long.parseLong(c[0]), c[1], c[2], Double.parseDouble(c[3]), Double.parseDouble(c[4]));
                porCodigo.put(p.codigo(), ps.size());
                ps.add(p);
                String[] nome = tokens(c[1]).toArray(String[]::new);
                String[] ref = tokens(c[2]).toArray(String[]::new);
                tn.add(nome);
                tr.add(ref);
                vocab.addAll(List.of(nome));
                vocab.addAll(List.of(ref));
            }
        }
        List<Viagem> vs = new ArrayList<>();
        Map<Long, List<Viagem>> porParada = new HashMap<>();
        Map<String, List<Viagem>> porLetreiro = new LinkedHashMap<>();
        try (BufferedReader r = abrir("viagens.tsv.gz")) {
            String linha;
            while ((linha = r.readLine()) != null) {
                String[] c = linha.split("\t", -1);
                if (c.length < 5) {
                    continue;
                }
                String[] ids = c[4].split(",");
                long[] seq = new long[ids.length];
                for (int i = 0; i < ids.length; i++) {
                    seq[i] = Long.parseLong(ids[i]);
                }
                Viagem v = new Viagem(c[0], Integer.parseInt(c[1]), c[2], c[3], seq);
                vs.add(v);
                porLetreiro.computeIfAbsent(chaveLetreiro(c[0]), k -> new ArrayList<>()).add(v);
                Set<Long> vistos = new LinkedHashSet<>();
                for (long id : seq) {
                    if (vistos.add(id)) {
                        porParada.computeIfAbsent(id, k -> new ArrayList<>()).add(v);
                    }
                }
            }
        }
        this.paradas = ps;
        this.tokensNome = tn;
        this.tokensRef = tr;
        this.indicePorCodigo = porCodigo;
        this.viagens = vs;
        this.viagensPorParada = porParada;
        this.viagensPorLetreiro = porLetreiro;
        this.vocabulario = vocab;
        log.info("Rede GTFS carregada: {} paradas, {} viagens", ps.size(), vs.size());
    }

    private BufferedReader abrir(String nome) throws IOException {
        InputStream in = RedeGtfs.class.getResourceAsStream(recursoBase + nome);
        if (in == null) {
            throw new IOException("recurso ausente: " + nome);
        }
        return new BufferedReader(new InputStreamReader(new GZIPInputStream(in), StandardCharsets.UTF_8));
    }

    public boolean disponivel() {
        garantirCarga();
        return !paradas.isEmpty();
    }

    // ---------- normalização ----------

    static String semAcento(String s) {
        return Normalizer.normalize(s == null ? "" : s, Normalizer.Form.NFD).replaceAll("\\p{M}+", "")
                .toLowerCase(Locale.ROOT);
    }

    /** Palavras comparáveis: sem acento, abreviações expandidas ("Av. Nsa. Sra." = "avenida nossa senhora"). */
    public static List<String> tokens(String texto) {
        List<String> saida = new ArrayList<>();
        for (String t : semAcento(texto).split("[^a-z0-9]+")) {
            if (t.isEmpty() || VAZIAS.contains(t)) {
                continue;
            }
            saida.add(ABREVIACOES.getOrDefault(t, t));
        }
        return saida;
    }

    private static final Set<String> TIPOS_DE_VIA = Set.of("avenida", "rua", "alameda", "praca", "travessa",
            "estrada", "largo", "viaduto", "rodovia", "ponte", "av", "r", "al", "pc", "tv", "estr", "lgo", "vd");

    /** Palavras do nome sem o tipo de via e sem números: "Av. Paulista, 1374" vira [paulista]. */
    static List<String> nucleo(String[] tokens) {
        List<String> saida = new ArrayList<>();
        for (String t : tokens) {
            if (!TIPOS_DE_VIA.contains(t) && !numero(t)) {
                saida.add(t);
            }
        }
        return saida;
    }

    /** 2 quando o nome da parada é exatamente o buscado, 1 quando começa por ele, 0 nos demais casos. */
    static int semelhancaDoNome(List<String> nome, List<String> busca) {
        if (busca.isEmpty() || nome.size() < busca.size() || !nome.subList(0, busca.size()).equals(busca)) {
            return 0;
        }
        return nome.size() == busca.size() ? 2 : 1;
    }

    static String chaveLetreiro(String letreiro) {
        return semAcento(letreiro).replaceAll("[^a-z0-9]", "");
    }

    private static boolean numero(String t) {
        return !t.isEmpty() && t.chars().allMatch(Character::isDigit);
    }

    /** Distância de edição limitada (para erros simples de digitação). */
    static int distancia(String a, String b, int limite) {
        if (Math.abs(a.length() - b.length()) > limite) {
            return limite + 1;
        }
        int[] ant = new int[b.length() + 1];
        int[] atual = new int[b.length() + 1];
        for (int j = 0; j <= b.length(); j++) {
            ant[j] = j;
        }
        for (int i = 1; i <= a.length(); i++) {
            atual[0] = i;
            int menor = atual[0];
            for (int j = 1; j <= b.length(); j++) {
                int custo = a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1;
                atual[j] = Math.min(Math.min(atual[j - 1] + 1, ant[j] + 1), ant[j - 1] + custo);
                menor = Math.min(menor, atual[j]);
            }
            if (menor > limite) {
                return limite + 1;
            }
            int[] troca = ant;
            ant = atual;
            atual = troca;
        }
        return ant[b.length()];
    }

    /** Para cada palavra do vocabulário que casa com a palavra buscada: 3 exata, 2 prefixo, 1 erro de digitação. */
    private Map<String, Integer> casamentos(String q) {
        Map<String, Integer> m = new HashMap<>();
        int tolerancia = q.length() >= 8 ? 2 : q.length() >= 5 ? 1 : 0;
        for (String v : vocabulario) {
            if (v.equals(q)) {
                m.put(v, 3);
            } else if (q.length() >= 3 && v.startsWith(q)) {
                m.put(v, 2);
            } else if (tolerancia > 0 && !numero(v) && distancia(q, v, tolerancia) <= tolerancia) {
                m.put(v, 1);
            }
        }
        return m;
    }

    // ---------- paradas ----------

    public Parada parada(long codigo) {
        garantirCarga();
        Integer i = indicePorCodigo.get(codigo);
        return i == null ? null : paradas.get(i);
    }

    /** Paradas cujo código começa com os dígitos informados (código incompleto lido da placa). */
    public List<Parada> paradasPorPrefixoDeCodigo(String digitos, int limite) {
        garantirCarga();
        List<Parada> saida = new ArrayList<>();
        for (Parada p : paradas) {
            if (String.valueOf(p.codigo()).startsWith(digitos)) {
                saida.add(p);
                if (saida.size() >= limite) {
                    break;
                }
            }
        }
        return saida;
    }

    /**
     * Busca por nome, endereço ou referência. Todas as palavras precisam casar (uma pode faltar quando há 4 ou
     * mais); o número do endereço não é exigido, só ordena pelas paradas de numeração mais próxima.
     */
    public List<ParadaEncontrada> buscarParadas(String termo, int limite) {
        garantirCarga();
        List<String> palavras = new ArrayList<>();
        List<Integer> numeros = new ArrayList<>();
        for (String t : tokens(termo)) {
            if (numero(t) && t.length() <= 6) {
                numeros.add(Integer.parseInt(t));
            } else if (!numero(t)) {
                palavras.add(t);
            }
        }
        if (palavras.isEmpty()) {
            return List.of();
        }
        List<Map<String, Integer>> casam = new ArrayList<>();
        for (String q : palavras) {
            casam.add(casamentos(q));
        }
        int faltasPermitidas = palavras.size() >= 4 ? 1 : 0;
        List<String> nucleoBusca = nucleo(palavras.toArray(String[]::new));
        record Candidata(int indice, int pontos, int diferencaNumero, int nomeIgual) {
        }
        List<Candidata> candidatas = new ArrayList<>();
        for (int i = 0; i < paradas.size(); i++) {
            String[] nome = tokensNome.get(i);
            String[] ref = tokensRef.get(i);
            int pontos = 0;
            int faltas = 0;
            for (Map<String, Integer> c : casam) {
                int melhor = 0;
                for (String t : nome) {
                    Integer s = c.get(t);
                    if (s != null) {
                        melhor = Math.max(melhor, s * 2);
                    }
                }
                if (melhor < 6) {
                    for (String t : ref) {
                        Integer s = c.get(t);
                        if (s != null) {
                            melhor = Math.max(melhor, s);
                        }
                    }
                }
                if (melhor == 0) {
                    faltas++;
                }
                pontos += melhor;
            }
            if (faltas > faltasPermitidas || pontos == 0) {
                continue;
            }
            pontos -= faltas * 4;
            int diferenca = Integer.MAX_VALUE;
            if (!numeros.isEmpty()) {
                for (String t : nome) {
                    if (numero(t) && t.length() <= 6) {
                        for (int n : numeros) {
                            diferenca = Math.min(diferenca, Math.abs(Integer.parseInt(t) - n));
                        }
                    }
                }
            }
            candidatas.add(new Candidata(i, pontos, diferenca, semelhancaDoNome(nucleo(nome), nucleoBusca)));
        }
        // Com a mesma pontuação, "Paulista" traz a Av. Paulista antes da Av. Lauzane Paulista ou do Atracadouro
        // Mar Paulista: primeiro o nome igual ao buscado, depois o nome que começa por ele.
        candidatas.sort(Comparator.comparingInt((Candidata c) -> -c.pontos())
                .thenComparingInt(c -> -c.nomeIgual())
                .thenComparingInt(Candidata::diferencaNumero)
                .thenComparing(c -> paradas.get(c.indice()).nome()));
        List<ParadaEncontrada> saida = new ArrayList<>();
        for (Candidata c : candidatas.subList(0, Math.min(limite, candidatas.size()))) {
            saida.add(new ParadaEncontrada(paradas.get(c.indice()), c.pontos(), null));
        }
        return saida;
    }

    public static int metros(double lat1, double lon1, double lat2, double lon2) {
        double r = 6_371_000;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(Math.toRadians(lat1))
                * Math.cos(Math.toRadians(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return (int) Math.round(2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
    }

    /** Paradas dentro do raio, da mais próxima para a mais distante. */
    public List<ParadaEncontrada> proximas(double lat, double lon, int raioMetros, int limite) {
        garantirCarga();
        List<ParadaEncontrada> saida = new ArrayList<>();
        for (Parada p : paradas) {
            if (Math.abs(p.latitude() - lat) > 0.02 || Math.abs(p.longitude() - lon) > 0.02) {
                continue;
            }
            int d = metros(lat, lon, p.latitude(), p.longitude());
            if (d <= raioMetros) {
                saida.add(new ParadaEncontrada(p, 0, d));
            }
        }
        saida.sort(Comparator.comparingInt(ParadaEncontrada::distanciaMetros));
        return saida.size() > limite ? new ArrayList<>(saida.subList(0, limite)) : saida;
    }

    // ---------- linhas ----------

    /** Linhas (em cada sentido) que param neste ponto, segundo o GTFS. */
    public List<Viagem> viagensDaParada(long codigo) {
        garantirCarga();
        return viagensPorParada.getOrDefault(codigo, List.of());
    }

    /** Letreiros que param no ponto, sem repetição, em ordem. */
    public List<String> letreirosDaParada(long codigo) {
        Set<String> s = new java.util.TreeSet<>();
        for (Viagem v : viagensDaParada(codigo)) {
            s.add(v.letreiro());
        }
        return new ArrayList<>(s);
    }

    /** Os sentidos de uma linha pelo letreiro completo ("875A-10") ou só pelo número, quando não há ambiguidade. */
    public List<Viagem> viagensDaLinha(String letreiro) {
        garantirCarga();
        String chave = chaveLetreiro(letreiro);
        List<Viagem> exata = viagensPorLetreiro.get(chave);
        if (exata != null) {
            return exata;
        }
        List<Viagem> saida = new ArrayList<>();
        String unico = null;
        for (Map.Entry<String, List<Viagem>> e : viagensPorLetreiro.entrySet()) {
            String base = chaveLetreiro(e.getValue().get(0).letreiro().split("-")[0]);
            if (base.equals(chave)) {
                if (unico != null && !unico.equals(e.getKey())) {
                    return List.of(); // "8000" pode ser 8000-10 ou 8000-21: quem chama pede o letreiro completo
                }
                unico = e.getKey();
                saida = e.getValue();
            }
        }
        return saida;
    }

    /** Letreiros completos que começam com o número informado ("8000" -> 8000-10, 8000-21). */
    public List<String> letreirosPorNumero(String numero) {
        garantirCarga();
        String chave = chaveLetreiro(numero);
        List<String> saida = new ArrayList<>();
        for (List<Viagem> vs : viagensPorLetreiro.values()) {
            String letreiro = vs.get(0).letreiro();
            if (chaveLetreiro(letreiro).startsWith(chave)) {
                saida.add(letreiro);
            }
        }
        return saida;
    }

    /** Busca de linhas por número, nome ou destino. */
    public List<Viagem> buscarLinhas(String termo, int limite) {
        garantirCarga();
        String compacto = chaveLetreiro(termo);
        List<String> qs = tokens(termo);
        record Achada(Viagem v, int pontos) {
        }
        List<Achada> achadas = new ArrayList<>();
        for (Viagem v : viagens) {
            int pontos = 0;
            String chave = chaveLetreiro(v.letreiro());
            if (!compacto.isEmpty() && Character.isDigit(compacto.charAt(0)) && chave.startsWith(compacto)) {
                pontos = chave.equals(compacto) ? 100 : 60;
            } else if (!qs.isEmpty()) {
                List<String> destino = tokens(v.destino());
                List<String> nome = tokens(v.nomeLinha());
                int soma = 0;
                boolean todas = true;
                for (String q : qs) {
                    int melhor = Math.max(casa(q, destino) * 2, casa(q, nome));
                    if (melhor == 0) {
                        todas = false;
                        break;
                    }
                    soma += melhor;
                }
                pontos = todas ? soma : 0;
            }
            if (pontos > 0) {
                achadas.add(new Achada(v, pontos));
            }
        }
        achadas.sort(Comparator.comparingInt((Achada a) -> -a.pontos()).thenComparing(a -> a.v().letreiro())
                .thenComparingInt(a -> a.v().sentido()));
        List<Viagem> saida = new ArrayList<>();
        for (Achada a : achadas.subList(0, Math.min(limite, achadas.size()))) {
            saida.add(a.v());
        }
        return saida;
    }

    private static int casa(String q, List<String> alvo) {
        int melhor = 0;
        int tolerancia = q.length() >= 8 ? 2 : q.length() >= 5 ? 1 : 0;
        for (String t : alvo) {
            if (t.equals(q)) {
                return 3;
            }
            if (q.length() >= 3 && t.startsWith(q)) {
                melhor = Math.max(melhor, 2);
            } else if (tolerancia > 0 && distancia(q, t, tolerancia) <= tolerancia) {
                melhor = Math.max(melhor, 1);
            }
        }
        return melhor;
    }

    /** Sentidos em que a linha vai de uma parada à outra, nesta ordem (viagem direta, sem baldeação). */
    public List<Viagem> viagensDiretas(Set<Long> origens, Set<Long> destinos) {
        garantirCarga();
        List<Viagem> saida = new ArrayList<>();
        for (Viagem v : viagens) {
            int primeiraOrigem = -1;
            for (int i = 0; i < v.paradas().length; i++) {
                if (primeiraOrigem < 0 && origens.contains(v.paradas()[i])) {
                    primeiraOrigem = i;
                } else if (primeiraOrigem >= 0 && destinos.contains(v.paradas()[i])) {
                    saida.add(v);
                    break;
                }
            }
        }
        return saida;
    }
}
