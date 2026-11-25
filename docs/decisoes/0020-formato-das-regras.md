# ADR 0020. Formato do livro de regras (ADR-1)

- **Data:** 25/10/2026
- **Decidido por:** Giovane (usuário), depois do experimento do K20 (PR #8, `docs/regras-como-codigo-experimento.md`).
- **Decisão (ADR-1):** **opção B**, um **livro de regras próprio em YAML** com um interpretador pequeno, **modelado nas ideias do OpenFisca** (parâmetros com vigência, variantes como reformas, testes como dados, rastro por critério).
- **Motivos (do experimento):** as duas opções reproduziram o motor atual **sem divergência em 4.357 perfis** (visual), então a escolha não depende de capacidade de reproduzir; em B as **regras são dado revisável** (fonte, status e revisor são campos do formato); **B não tem pendência de licença**, enquanto a **AGPL** do OpenFisca pode colidir com uso em serviço de rede e com um possível uso comercial (D18, D21).
- **Regra de parada de B:** se o interpretador passar de **cerca de 500 linhas** ou precisar de uma **linguagem de expressões geral** para os grupos de amputação e funcionais, **parar e reavaliar** (A, depois de uma consulta jurídica sobre a AGPL, ou C).
- **Riscos registrados:** o experimento cobriu **só o grupo visual** (o mais fácil); as estimativas para os outros sete são extrapolação (B: 10 a 15 dias úteis, faixa de 7 a 25); o crescimento da linguagem é o maior risco de B; `needs_review` e `not_implemented` não foram exercitados.
- **Não decidido:** **quando** adotar. A adoção **altera o núcleo** (`rules/`) na linha plataforma, que diverge da linha matéria; precisa de **decisão do usuário** antes de despachar. Ordem sugerida: **baixa estatura** primeiro (testa limite por sexo, soma e ordem), depois amputação, classe 20 (com `onset_age`, R12) e os provisórios.
- **Consulta sobre a AGPL:** opcional e **não decidida**; só interessa se a opção A voltar à mesa.
