# O que o backend Spring Boot precisa ter para integrar GenAI e RPA

Contrato completo: `openapi-integracao.yaml` (dá para gerar DTOs com o openapi-generator).

## 1. `/chat` → serviço GenAI

Variáveis de ambiente: `LLM_URL` (ex.: `http://localhost:8001`).

```java
@RestController
public class ChatController {
  private final RestClient http = RestClient.builder()
      .requestFactory(new SimpleClientHttpRequestFactory() {{ setConnectTimeout(3000); setReadTimeout(30000); }})
      .build();
  @Value("${LLM_URL:http://localhost:8001}") String llmUrl;

  @PostMapping("/chat")
  public Map<String, Object> chat(@RequestBody Map<String, String> corpo) {
    try {
      return http.post().uri(llmUrl + "/chat").body(Map.of("pergunta", corpo.get("pergunta")))
                 .retrieve().body(Map.class);
    } catch (Exception e) {   // degradar com elegância: nunca 500 para o passageiro
      return Map.of("resposta", "O assistente está indisponível agora. Tente de novo em instantes.",
                    "fontes", List.of(), "confianca", "baixa", "nao_consta", true);
    }
  }
}
```
Não registrar a pergunta em log com identificação do usuário (LGPD).

## 2. `GET /historico?data=` → robô RPA

Devolver a lista de passagens do dia no formato `Passagem`. Pedido: incluir o campo `veiculo` já anonimizado (ex.: SHA-256 truncado do prefixo do ônibus). Sem ele o robô ainda funciona, mas deduplica por linha + sentido + ponto + minuto.

## 3. `POST /boletim` e `GET /boletim`

Variável de ambiente: `RPA_API_KEY` (mesmo valor configurado no robô; nunca no código nem no Git).

```sql
CREATE TABLE boletim (
  data_referencia DATE PRIMARY KEY,
  conteudo        JSONB       NOT NULL,
  desatualizado   BOOLEAN     NOT NULL DEFAULT FALSE,
  recebido_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
- `POST /boletim`: valida `X-API-Key` (401 se diferente), faz upsert por `data_referencia`, responde 201.
- `GET /boletim`: devolve o `conteudo` com `recebido_em` mais recente (404 se vazio).
- Tela do Angular: ler `resumo_falado` com a Web Speech API, mostrar `linhas[].frase`, o selo de origem (`fonte_dados` / `dados_simulados`) e um aviso destacado quando `desatualizado=true`. O campo `html` já vem escapado e pode ser exibido com `[innerHTML]`.
