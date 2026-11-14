import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

/** Ferramenta local: inicia PostgreSQL persistente e o JAR real, ambos em loopback. */
public final class DemoLocal {
    public static void main(String[] args) throws Exception {
        Path raiz = Path.of(args[0]).toAbsolutePath().normalize();
        int porta = Integer.parseInt(args[1]);
        try (EmbeddedPostgres pg = EmbeddedPostgres.builder()
                .setDataDirectory(raiz.resolve(".validation/local/pgdata"))
                .setCleanDataDirectory(false)
                // 10 s (padrão) não basta logo depois do build, com a máquina ocupada.
                .setPGStartupWait(java.time.Duration.ofSeconds(60))
                .setServerConfig("listen_addresses", "127.0.0.1")
                .setServerConfig("max_connections", "20").start()) {
            String java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
            ProcessBuilder builder = new ProcessBuilder(java, "-Xmx320m", "-XX:+UseSerialGC", // nosemgrep -- demo local, argumentos fixos
                    "-XX:TieredStopAtLevel=1", "-Xss512k", "-jar",
                    raiz.resolve("backend/target/pontofalante.jar").toString()).inheritIO();
            var env = builder.environment();
            env.put("SPRING_DATASOURCE_URL", pg.getJdbcUrl("postgres", "postgres"));
            env.put("SPRING_DATASOURCE_USERNAME", "postgres");
            env.put("SPRING_DATASOURCE_PASSWORD", "");
            env.put("SERVER_ADDRESS", "127.0.0.1");
            env.put("PORT", Integer.toString(porta));
            env.put("SPTRANS_TOKEN", "");
            // Demo por padrão; o launcher só passa "auto" com --sptrans-gateway (credenciais do gateway no ambiente).
            boolean real = "auto".equals(System.getenv("PF_SPTRANS_MODO"));
            env.put("PF_SPTRANS_MODO", real ? "auto" : "demo");
            if (!real) {
                env.put("SPTRANS_GATEWAY_CHAVE", "");
                env.put("SPTRANS_GATEWAY_SEGREDO", "");
            }
            Process app = builder.start();
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                app.destroy();
                try { app.waitFor(10, TimeUnit.SECONDS); } catch (InterruptedException ignored) {}
                try { pg.close(); } catch (Exception ignored) {}
            }));
            System.out.println("MVP local: http://127.0.0.1:" + porta + " — " + (real ? "SPTrans real via gateway" : "modo demonstrativo") + "; Ctrl+C encerra.");
            int resultado = app.waitFor();
            if (resultado != 0) throw new IllegalStateException("Aplicacao terminou com codigo " + resultado);
        }
    }
}
