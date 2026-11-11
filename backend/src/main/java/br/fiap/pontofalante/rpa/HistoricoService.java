package br.fiap.pontofalante.rpa;

import br.fiap.pontofalante.sistema.ErroApi;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.LocalDate;
import java.util.List;

/** Passagens de um dia. Sem registros guardados, gera e grava o histórico de demonstração (fonte "simulador"). */
@Service
public class HistoricoService {
    static final int DIAS_PASSADO = 400;
    static final int DIAS_FUTURO = 1;

    private final PassagemRepository repo;
    private final TransactionTemplate tx;
    private final Clock relogio;
    private final Object trava = new Object();

    public HistoricoService(PassagemRepository repo, PlatformTransactionManager tm, Clock relogio) {
        this.repo = repo;
        this.tx = new TransactionTemplate(tm);
        this.relogio = relogio;
    }

    public List<Passagem> passagensDoDia(LocalDate data) {
        LocalDate hoje = LocalDate.now(relogio);
        if (data.isBefore(hoje.minusDays(DIAS_PASSADO)) || data.isAfter(hoje.plusDays(DIAS_FUTURO))) {
            throw ErroApi.requisicaoInvalida("Escolha uma data entre " + hoje.minusDays(DIAS_PASSADO)
                    + " e " + hoje.plusDays(DIAS_FUTURO) + ".");
        }
        List<Passagem> existentes = repo.findByDataOrderByIdAsc(data);
        if (!existentes.isEmpty()) {
            return existentes;
        }
        synchronized (trava) {
            return tx.execute(status -> {
                List<Passagem> de = repo.findByDataOrderByIdAsc(data);
                if (!de.isEmpty()) {
                    return de;
                }
                return repo.saveAll(GeradorHistoricoDemo.gerar(data));
            });
        }
    }
}
