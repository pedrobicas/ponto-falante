-- A câmera fixa do ponto (visao/src/demo.py) também avisa "chegou um ônibus, mas não consegui ler a linha":
-- nesse caso linha_reconhecida fica vazia, em vez de o sistema inventar uma linha.
ALTER TABLE deteccao_visao ALTER COLUMN linha_reconhecida DROP NOT NULL;
