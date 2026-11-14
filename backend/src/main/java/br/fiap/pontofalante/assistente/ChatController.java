package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.PerguntaChat;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class ChatController {
    private final ChatService service;
    private final LimiteTaxa limite;

    public ChatController(ChatService service, PfProps props) {
        this.service = service;
        this.limite = new LimiteTaxa(props.chatLimitePorMinuto());
    }

    @PostMapping("/chat")
    public RespostaChat chat(@Valid @RequestBody PerguntaChat corpo, HttpServletRequest req) {
        if (!limite.permitir(ipDoCliente(req))) {
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_PERGUNTAS",
                    "Você fez muitas perguntas seguidas. Espere um minuto e tente de novo.");
        }
        return service.perguntar(corpo.pergunta(), service.idCliente(ipDoCliente(req)), corpo.contexto());
    }

    /**
     * IP do cliente resolvido pelo Tomcat (server.forward-headers-strategy=native): X-Forwarded-For só é
     * considerado quando a conexão vem de um proxy confiável (server.tomcat.remoteip.internal-proxies).
     * Ler o cabeçalho diretamente permitiria trocar de "IP" a cada pergunta e furar o limite.
     */
    static String ipDoCliente(HttpServletRequest req) {
        return req.getRemoteAddr();
    }
}
