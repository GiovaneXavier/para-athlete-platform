# 19. Robustez e aprendizado profundo (depois da apresentação de 05/11/2026)

**Motivo:** na apresentação da matéria disseram que o projeto "é muito fácil", porque pode ser reduzido a uma árvore de decisão, e sugeriram anexar uma foto às respostas do formulário. O usuário pediu um plano para deixá-lo mais robusto e ideias de aprendizado profundo, e propôs usar um modelo de linguagem e imagem (CLIP) para conferir foto e currículo. **Decisão:** ADR 0022 (só o K34 entra; o resto fica como candidato).

## 1. A crítica: o que tem de razão

- O motor de regras **é** uma árvore de decisão, **de propósito**: reproduz o livreto do CPB e por isso é auditável. Isso é uma propriedade de segurança, não uma fraqueza.
- O ponto fraco é outro: os rótulos de treino do modelo vêm das **mesmas regras** (nível de evidência N1). **Por construção**, uma árvore reproduz esses rótulos tão bem quanto o modelo. Isto é um argumento pela construção, **não** uma medida (o experimento contra a árvore, abaixo, a mediria).
- Mais aprendizado profundo sobre o mesmo cenário **reforça** a crítica. A resposta forte tem três partes: admitir que as regras são uma árvore; mostrar onde uma árvore não chega (entradas que o atleta não consegue digitar, texto livre, medida com erro); e **medir** contra uma árvore de verdade.
- Arquitetura que responde à crítica: **percepção aprendida mais regras simbólicas.** O modelo aprende a ler imagem ou texto; as regras continuam decidindo.

## 2. K34: conferência imagem x laudo (decidido)

Detalhe e restrições: `adr/0022` e `briefs/onda2b-k34-conferencia-boneco-laudo.md`. Em uma frase: a partir de uma **imagem** (boneco, imagem sintética ou foto Creative Commons) e de um **laudo em texto**, um modelo aberto e local extrai atributos visíveis (lado, parte do corpo, nível, uso de cadeira ou prótese), o código os **compara** com os do laudo, e o resultado é um aviso "confere / não confere / não sei", **para revisão humana**.

**Por que não é "foto do atleta verificando deficiência":** deficiência visual, intelectual e ataxia não aparecem em foto; foto de rosto é dado biométrico e de saúde (LGPD, art. 11); o CLIP erra esquerda e direita e relações espaciais. A conferência vale só para o que é **visível e já declarado**.

**Três níveis de dificuldade, e como falar deles:** (1) boneco nosso, fácil; (2) imagens sintéticas mais difíceis; (3) poucas fotos reais Creative Commons. O aprendizado profundo tende a aparecer nos níveis 2 e 3, não no boneco. Os resultados saem **por nível** e **por tipo de erro plantado**, sempre com a nota de N1.

**Fontes de imagens, a conferir antes do uso (nenhuma licença foi confirmada):** WheelPose (cadeira de rodas sintética, esqueleto anotado, código aberto), biblioteca de imagens da Ottobock (#DearAI, perda de membro; não se sabe se são fotos ou imagens geradas), ProGait (4 pessoas com prótese acima do joelho, em vídeo), fotos do Wikimedia Commons em categorias de atletismo paralímpico (licença por arquivo). Conjuntos de detecção de cadeira de rodas do Roboflow ficam fora (licença sem clareza).

## 2b. Resultado do K34 e o K35 (decidido em 19/11/2026, ADR 0023)

**Resultado do K34 (N1, negativo):** modelos genéricos pequenos (SmolVLM2-2.2B, Qwen2.5-VL-7B, CLIP) não leram nível nem lado do boneco; a linha de base clássica lê o boneco limpo (99,8%) e cai a 7,3% na faixa mais difícil do nível 2. Relatório: `docs/consistencia-imagem-laudo-relatorio.md`.

**K35, sugestão do professor:** em vez de **adicionar** uma imagem ao formulário, **comparar um modelo que recebe só imagens com o preenchimento do formulário**, treinando uma **rede pequena** em milhares de imagens geradas, de rótulo certo por construção. Escopo **mínimo até 26/11**: níveis 1 e 2, rede em CPU, comparada com a linha de base clássica e com o formulário (completo, com campos faltando e com erros), com quatro hipóteses escritas antes de rodar. **O formulário é o teto** nos dados sintéticos; a imagem só pode igualá-lo, e a pergunta é quanto dele se recupera e se ajuda quando ele vem incompleto ou errado. Só vale para membros. Brief: `briefs/onda2b-k35-imagem-contra-formulario.md`. Fica como próximo passo: fusão aprendida, rede de ponta a ponta imagem para classe, nível 3.

## 3. Candidatos, sem decisão (descritos para o roadmap)

| Ideia | O que é | Por que não é uma árvore | Dependência |
|---|---|---|---|
| **Experimento contra a árvore** | Treinar uma árvore de decisão na mesma base e medir onde falha (dado faltante, medida com ruído, fora da distribuição) | Responde à crítica com dados | Nenhuma de pessoas |
| **Medidas por vídeo ou foto, com incerteza** | Estimativa de pose dá arco do tornozelo ou diferença de perna com margem de erro; o motor trata como limítrofe quando a margem cruza o limite | Entrada que o atleta não digita; perception + regras | Vídeos de pessoas: só com consentimento e entidade controladora |
| **Extração de campos de laudos e currículos** | OCR e modelo de linguagem preenchem o formulário; a pessoa confere | Texto livre | Laudos reais exigem entidade e CEP |
| **Casos parecidos por embeddings** | Mostrar ao classificador os casos anteriores mais próximos | Raciocínio por casos, explicável | Base de casos classificados (N3) |
| **Combinações implausíveis** | Sinal de revisão para respostas improváveis | Anomalia, não regra | Dados reais para calibrar |
| **Desacordo entre versões das regras** | Livreto 2024 contra WPA 2023 como medida de ambiguidade do caso | Usa o `diff` de variantes que já existe | Nenhuma de pessoas |
| **Testes de campo da peneira (K16)** | Velocidade e salto estimados por vídeo | Visão computacional | Consentimento, supervisão profissional |

**Regra para todas:** qualquer número de desempenho exige rótulos de classificadores (N2 ou N3) para valer como mais que N1; com sintéticos, o texto diz N1.

## 4. Linha do tempo-alvo (meta, não compromisso)

Nota de desenho do K34 em PR até cerca de 11/11; implementação e resultados até cerca de 19/11; relatório até cerca de 23/11; entrega da matéria em 26/11. Se o nível 3 atrasar, o K34 entrega os níveis 1 e 2.
