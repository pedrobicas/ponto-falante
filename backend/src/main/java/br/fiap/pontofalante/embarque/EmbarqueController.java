package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.assistente.LimiteTaxa;
import br.fiap.pontofalante.embarque.EmbarqueDtos.AlteracaoFavorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Conferencia;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Encerramento;
import br.fiap.pontofalante.embarque.EmbarqueDtos.EstadoVisao;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Favorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Indicadores;
import br.fiap.pontofalante.embarque.EmbarqueDtos.NovaSessao;
import br.fiap.pontofalante.embarque.EmbarqueDtos.NovoFavorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Sessao;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Situacao;
import br.fiap.pontofalante.sistema.ErroApi;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

/** API do Embarque Assistido. Contrato: contratos/openapi-mvp.yaml (seção Embarque Assistido). */
@RestController
@RequestMapping("/api/embarque")
public class EmbarqueController {
    private final EmbarqueService service;
    private final IdentificadorDispositivo dispositivos;
    /** Conferências pela câmera custam processamento no modelo: limite por IP, como no chat. */
    private final LimiteTaxa limiteVisao = new LimiteTaxa(12);
    /** Escritas (favoritos e acompanhamentos) também têm teto, para ninguém encher o banco gratuito. */
    private final LimiteTaxa limiteEscrita = new LimiteTaxa(40);

    public EmbarqueController(EmbarqueService service, IdentificadorDispositivo dispositivos) {
        this.service = service;
        this.dispositivos = dispositivos;
    }

    // ---------- trajetos favoritos ----------

    @GetMapping("/favoritos")
    public List<Favorito> favoritos(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo) {
        return service.favoritos(dispositivos.hash(dispositivo));
    }

    @PostMapping("/favoritos")
    @ResponseStatus(HttpStatus.CREATED)
    public Favorito salvar(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo,
                           @Valid @RequestBody NovoFavorito corpo, HttpServletRequest req) {
        limitar(limiteEscrita, req);
        return service.salvarFavorito(dispositivos.hash(dispositivo), corpo);
    }

    @PatchMapping("/favoritos/{id}")
    public Favorito alterar(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo, @PathVariable long id,
                            @Valid @RequestBody AlteracaoFavorito corpo, HttpServletRequest req) {
        limitar(limiteEscrita, req);
        return service.alterarFavorito(dispositivos.hash(dispositivo), id, corpo);
    }

    @DeleteMapping("/favoritos/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void remover(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo, @PathVariable long id) {
        service.removerFavorito(dispositivos.hash(dispositivo), id);
    }

    // ---------- acompanhamento ----------

    @PostMapping("/sessoes")
    @ResponseStatus(HttpStatus.CREATED)
    public Sessao iniciar(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo,
                          @Valid @RequestBody NovaSessao corpo, HttpServletRequest req) {
        limitar(limiteEscrita, req);
        return service.iniciar(dispositivos.hash(dispositivo), corpo);
    }

    @GetMapping("/sessoes/atual")
    public ResponseEntity<Sessao> atual(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo) {
        return service.atual(dispositivos.hash(dispositivo)).map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @GetMapping("/sessoes/{id}/situacao")
    public Situacao situacao(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo, @PathVariable UUID id) {
        return service.situacao(dispositivos.hash(dispositivo), id);
    }

    @PostMapping("/sessoes/{id}/encerrar")
    public Sessao encerrar(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo, @PathVariable UUID id,
                           @Valid @RequestBody Encerramento corpo) {
        return service.encerrar(dispositivos.hash(dispositivo), id, corpo.desfecho());
    }

    /** Direito de eliminação (LGPD): apaga favoritos, acompanhamentos e conferências deste aparelho. */
    @DeleteMapping("/dados")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void apagarDados(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo) {
        service.apagarDados(dispositivos.hash(dispositivo));
    }

    /** Indicadores de impacto agregados (sem dados pessoais), para o pitch e o BI. */
    @GetMapping("/indicadores")
    public Indicadores indicadores() {
        return service.indicadores();
    }

    // ---------- visão computacional ----------

    @GetMapping("/visao")
    public EstadoVisao estadoVisao() {
        boolean conectada = service.visaoConectada();
        return new EstadoVisao(conectada, conectada
                ? "Aponte a câmera para o letreiro da frente do ônibus."
                : ReconhecedorLetreiro.MSG_NAO_CONECTADA);
    }

    @PostMapping(value = "/visao/conferir", consumes = "multipart/form-data")
    public Conferencia conferir(@RequestHeader(IdentificadorDispositivo.CABECALHO) String dispositivo,
                                @RequestPart("imagem") MultipartFile imagem,
                                @RequestParam("linha_esperada") String linhaEsperada,
                                @RequestParam(value = "sessao", required = false) UUID sessao,
                                HttpServletRequest req) throws IOException {
        limitar(limiteVisao, req);
        String hash = dispositivos.hash(dispositivo);
        if (!service.visaoConectada()) {
            throw new ErroApi(HttpStatus.SERVICE_UNAVAILABLE, "VISAO_NAO_CONECTADA", ReconhecedorLetreiro.MSG_NAO_CONECTADA);
        }
        byte[] bytes = imagem.getBytes();
        String tipo = tipoImagem(bytes);
        if (tipo == null) {
            throw new ErroApi(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "IMAGEM_INVALIDA", "Envie uma foto JPEG ou PNG.");
        }
        return service.conferir(hash, bytes, tipo, linhaEsperada, sessao);
    }

    /** Confere a assinatura do arquivo (não confia no Content-Type enviado). */
    static String tipoImagem(byte[] b) {
        if (b == null || b.length < 8) return null;
        if ((b[0] & 0xFF) == 0xFF && (b[1] & 0xFF) == 0xD8 && (b[2] & 0xFF) == 0xFF) return "image/jpeg";
        if ((b[0] & 0xFF) == 0x89 && b[1] == 'P' && b[2] == 'N' && b[3] == 'G') return "image/png";
        return null;
    }

    private static void limitar(LimiteTaxa limite, HttpServletRequest req) {
        if (!limite.permitir(req.getRemoteAddr())) {
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_ACOES",
                    "Você fez muitas ações seguidas. Espere um minuto e tente de novo.");
        }
    }
}
