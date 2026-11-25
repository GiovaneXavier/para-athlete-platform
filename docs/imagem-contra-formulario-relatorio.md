# Experimento imagem contra formulário: uma rede treinada em imagens sintéticas, contra o formulário (relatório)

**Estado:** concluído para a PR. O desenho e as quatro hipóteses foram fixados **antes de qualquer treino ou medida** (seções 1 a 7); os resultados do teste, aberto uma só vez, estão na seção 8 e os limites na seção 9; a replicação com uma segunda semente está na seção 10. **Evidência: N1 em tudo** (desenho sintético, rótulos por construção; a palavra "acurácia" só aparece ao lado de N1). Decisão: `docs/decisoes/0023-imagem-contra-formulario.md`. Brief: o brief interno (não incluído neste repositório). Código: `spikes/imagem_formulario/`. Testes: `tests/test_imagem_formulario_*.py`.

> **Hipóteses fixadas em 19/11/2026**, na nota de desenho aprovada pela sessão de arquitetura, **antes** de gerar os dados, treinar ou rodar qualquer medida. Elas não mudam depois de ver resultado; todas são relatadas, também as que falharem.

## 1. O que se quer saber

O professor sugeriu **comparar um modelo que recebe só imagens com o preenchimento do formulário**, treinando o modelo com milhares de imagens geradas de rótulo certo. No experimento imagem e laudo, modelos genéricos pequenos não leram o boneco, e a regra clássica lê o boneco limpo mas cai nas faixas difíceis do nível 2. Aqui se mede (a) o quanto de informação do formulário uma **rede treinada por nós** recupera da imagem; (b) se a imagem **ajuda** quando o formulário vem com campos faltando ou com erros.

**O formulário é o teto nos dados sintéticos.** A classe vem dos mesmos atributos que geram a imagem e o formulário; sem erro e sem campo faltando, o formulário dá a classe certa por construção. A imagem só pode ajudar onde o formulário falha, e só vale para **membros** (a imagem não mostra acuidade, QI nem medidas). O modelo **sugere classes candidatas, sujeito à classificação oficial**; nunca "prescreve".

## 2. Dados

- Geração com as funções que já existem (nível 1: `appearance_for` e `render`; nível 2: `render_level2`, faixas 0 a 3), com **sementes novas** (treino 1000, desenvolvimento 2000, teste 3000; o experimento imagem e laudo usou 34). **Uso as 144 combinações de nível também no nível 2** (o experimento imagem e laudo usava 75).
- **Tamanhos por nível:** treino 6.000, desenvolvimento 1.000, teste 2.000 (1.500 de combinações vistas e 500 de combinações **seguradas**). No nível 2 cada combinação passa pelas quatro faixas.
- Imagem reduzida 2x2 por média (de 400x280 para 200x140, `uint8`), guardada **fora do repositório** (`<pasta IMAGEM_FORMULARIO_HOME>\data`). O teste também guarda os PNG originais, que a linha de base clássica lê.
- **Rótulo da imagem:** o que a figura mostra (`?` onde o fim do membro está escondido ou cortado, e onde a cadeira ou a prótese está quase toda escondida). **Atributos verdadeiros:** o que o gerador construiu (o nível real de cada membro, escondido ou não). A rede é medida contra o rótulo da imagem; o **formulário e a classe** são medidos contra os atributos verdadeiros.

## 3. Divisão

- **12 das 144 combinações ficam fora do treino e do desenvolvimento** (sorteio com semente, conferindo que cada valor de cada membro continua no treino). Elas aparecem só no teste, medidas à parte.
- Treino, desenvolvimento e teste usam **sementes disjuntas**. O teste unitário confere que nenhuma combinação segurada entra no treino ou no desenvolvimento e que nenhuma imagem se repete entre os conjuntos.
- **O que isto testa de fato (H4):** como cada valor de cada membro continua no treino, a medida nas combinações seguradas mostra se as cabeças **confundem os membros entre si** (atalhos por correlação), **não** se a rede generaliza para um valor que nunca viu.
- **Tudo o que se ajusta, ajusta-se no desenvolvimento.** O teste é aberto **uma vez** (`spikes/imagem_formulario/final.py` recusa a segunda rodada; se um erro de **código**, não de ajuste, obrigar a repetir, as duas rodadas serão relatadas com o que mudou).

## 4. A rede

Cinco blocos convolucionais (3x3, normalização em lote, ReLU, pooling 2x2; 16, 32, 64, 96 e 128 canais). O último mapa (6x4x128) é **achatado, não promediado**, para a posição na figura sobreviver e a esquerda se distinguir da direita. Uma camada comum e **seis cabeças**: os quatro membros (níveis e `?`) e cadeira de rodas e prótese (sim, não, `?`). Entropia cruzada; no nível 1 as duas cabeças de cadeira e prótese não têm perda. Cerca de 1 milhão de parâmetros (o número exato está na seção de resultados). Uma só rede para os dois níveis. Adam com ciclo único de taxa de aprendizado, 20 épocas (a primeira tentativa, de 30, foi interrompida: não cabia no tempo), melhor época pelo desenvolvimento, teto de cerca de 2 h, `torch` em CPU no ambiente `imagem-laudo-modelos`.

**Aumento:** espelhar a imagem na horizontal **trocando esquerda e direita no rótulo** (as cabeças de cadeira e prótese não mudam), com teste unitário, e uma variação de brilho de até 10%. A **consistência do espelho** é medida no teste: a leitura da imagem espelhada deve ser a original com os lados trocados (foi onde o CLIP e o SmolVLM2 falharam no experimento imagem e laudo).

## 5. A classe vem das regras, não da rede

A classe candidata é o conjunto das classes que o motor de regras dá como **atendidas** ou **limítrofes** a partir dos quatro níveis de membro e da **postura** (cadeira `yes`: sentado; prótese `yes`: com prótese; senão, em pé). O ambiente `imagem-laudo-modelos` não tem `pyyaml` (o motor carrega um catálogo em YAML), então a tabela atributos-classe foi **calculada uma vez** com o ambiente do projeto (só leitura) e gravada em `spikes/imagem_formulario/class_table.py`; um teste a compara com o motor em todas as combinações.

**Três fatos sobre a classe que mudam a leitura das métricas:**

1. **Só 27 das 432 combinações decididas (144 por postura) dão classe não vazia**: 19 de 144 em pé, 8 de 144 com prótese, e **nenhuma** sentado. A maior parte das imagens tem como classe verdadeira o **conjunto vazio** ("a deficiência de membro sozinha não dá classe"). Por isso a classe correta é reportada **de duas formas**: em **todas** as imagens (o conjunto vazio vale como resposta) e **só onde a classe verdadeira é não vazia** (fatia pequena, com o tamanho e o intervalo informados).
2. **"Não decidiu" não é o conjunto vazio.** Com um `?` num membro (ou numa das duas flags), o motor não tem dado e a lista de candidatas sai vazia, o que se confundiria com "nenhuma classe". Por isso, se a leitura de um atributo de que a classe precisa é `?`, a resposta é **"não decidiu"**, e **nunca** conta como correta. A taxa de "não decidiu" é reportada **à parte**.
3. **Limite do desenho, não erro da rede:** onde a imagem **esconde** o nível verdadeiro (`?` no rótulo), a imagem não pode dar a classe certa por construção. Só o formulário (ou a fusão) alcança esses casos.

## 6. Os três braços e a linha de base

| Braço | O que recebe | Como decide a classe |
|---|---|---|
| **Formulário** | Os atributos como o atleta preencheria: 12 células, **campos faltando** (0, 10, 30 e 50% por campo) e **erros** (0, 5 e 10% por campo de membro; metade lado trocado, metade nível errado, sempre mudando o valor) | As regras |
| **Imagem** | Só a imagem | Rede para os atributos, regras para a classe |
| **Fusão simples, sem aprendizado** | Os dois | Onde o formulário tem o campo, vale o formulário; onde falta, vale o valor da rede se ela tiver confiança de pelo menos um **limiar fixado no desenvolvimento** e não for `?`; **se os dois têm valor e diferem, o veredito é "revisar"** |
| **Linha de base clássica** | Só a imagem (os mesmos PNG do teste) | As regras (a clássica lê só os membros; para a classe usa a postura **verdadeira**, o que a favorece, e o relatório diz) |

**Classe automática correta** = decidiu, não foi para revisão, e o conjunto é igual ao verdadeiro. O limiar da fusão é escolhido no desenvolvimento, com 30% de campos faltando e 5% de erros, pelo maior número de **bons resultados**: o formulário tem erro de membro e o veredito é "revisar", ou não tem erro e a classe automática está certa.

## 7. As quatro hipóteses (fixadas em 19/11/2026, antes de qualquer rodada)

- **H1.** Nas faixas fáceis (0 e 1 do nível 2), o acerto por atributo da rede **não fica abaixo** do limite inferior do Wilson 95% da linha de base clássica, nos quatro membros (8 comparações).
- **H2.** Nas faixas difíceis (2 e 3 do nível 2), a rede **supera** a linha de base clássica: o limite inferior do Wilson da rede fica acima do acerto da clássica, nos quatro membros (8 comparações).
- **H3.** Com campos faltando (10, 30 e 50%) e 0% de erros, no nível 2, a **classe automática da fusão** é correta mais vezes que a do formulário sozinho (limite inferior do intervalo bootstrap, pareado por imagem, da diferença acima de 0, nas três taxas).
- **H4.** Nas **combinações seguradas** (nível 1 e nível 2, quatro membros: 8 comparações), o acerto por atributo da rede fica **acima do melhor chute constante** (limite inferior do Wilson maior que ele) **e conserva mais da metade da vantagem que tem sobre o acaso nas combinações vistas**. Mede se as cabeças confundem os membros entre si, não generalização a um valor novo.

"Confirmada" exige **todas** as comparações da hipótese; se só parte vale, a hipótese é **não confirmada** e o número de comparações que valeu é informado.

## 8. Resultados

**Evidência: N1 em tudo** (desenho sintético, rótulos por construção). Onde aparece "acerto" ou "acurácia" é N1. Os números abaixo são os do **conjunto de teste, aberto uma única vez** (`final_run1.md`, na pasta de resultados fora do repositório; a saída completa está no Apêndice A). Onde um número saiu do desenvolvimento, está dito.

### 8.1 Como correu, o que se ajustou e o que não

| passo | o que foi | tempo medido |
|---|---|---|
| geração dos dados | 18.000 imagens (nível 1: 6.000 treino, 1.000 desenvolvimento, 2.000 teste; nível 2: o mesmo), 8 processos | cerca de 19 min no total (nível 1: 33, 68 e 196 s; nível 2: 97, 199 e 531 s) |
| treino | 982.888 parâmetros, CPU, 10 threads, lote 64, Adam com ciclo único, **20 épocas** (a parada por paciência não disparou); melhor época a **16**, acerto de membros no desenvolvimento 91,2% (N1) | **108,9 min** (330 s por época no começo, 207 s no fim, quando a outra rodada que dividia a máquina acabou); **pico de RAM 4.030 MB** |
| relatório do desenvolvimento | todas as tabelas abaixo, no desenvolvimento; fixa o limiar da fusão | não medido (poucos minutos) |
| linha de base clássica nas 4.000 imagens do teste | lê só pixels, sem rótulo, 8 processos | 403 s (nível 1) e 356 s (nível 2) |
| leitura da rede no teste | 4.000 imagens, mais as espelhadas | 70 s (9 ms por leitura) |
| rodada única do teste | tabelas, hipóteses | 75 s |

**O que foi ajustado, e em que conjunto.** Só no **desenvolvimento**: a escolha da melhor época (a 16, pelo acerto de membros) e o **limiar da fusão, 0,5**, escolhido entre 0,5; 0,6; 0,7; 0,8; 0,9; 0,95 e 0,99 pelo maior número de bons resultados com 30% de campos faltando e 5% de erros (0,809 em 0,5, descendo até 0,737 em 0,99; **0,5 é o menor candidato, então um limiar menor nunca foi testado**). A taxa de aprendizado, o lote, o tamanho da rede e a semente (0) **não foram ajustados**: uma só configuração, um só treino. Nada disso olhou o teste.

**O que deu errado no caminho e foi corrigido (nada de ajuste):** (1) a primeira tentativa de treino, com 30 épocas, foi **interrompida depois de 1 época**: o ciclo de taxa de aprendizado não cabia no teto de tempo (339 s por época, com a máquina dividida) e a leitura de memória estava quebrada (devolvia 0); ajustei a leitura de memória e passei para 20 épocas **sem ter visto nada além do resultado da época 1**; (2) o primeiro relatório do desenvolvimento falhou com `KeyError` por uma **chave que faltava** no dicionário devolvido por `form_grid` (`clean_correct_auto`, que `choose_tau` lia): **erro de código**, corrigido acrescentando a chave ao dicionário, com teste de regressão (`test_choose_tau_runs_on_a_small_split...`). **Nenhum dado, peso da rede ou limiar foi tocado** (o limiar saiu da rodada seguinte do mesmo relatório do desenvolvimento, e o treino já estava concluído); (3) antes da rodada do teste, **ensaiei o `final.py` inteiro com o desenvolvimento no lugar do teste** (e leituras clássicas falsas), para não ter de repetir a rodada por erro de código; o marcador de "teste usado" mostra **uma rodada só**, sem `--bugfix`.

### 8.2 Tamanhos (teste)

| nível | conjunto | faixa | imagens | de combinações seguradas | de combinações vistas | membros `?` no rótulo da imagem |
|---|---|---|---|---|---|---|
| nível 1 | test | nível 1 | 2000 | 500 | 1500 | 0 |
| nível 2 | test | faixa 0 | 500 | 125 | 375 | 0 |
| nível 2 | test | faixa 1 | 500 | 125 | 375 | 119 |
| nível 2 | test | faixa 2 | 500 | 125 | 375 | 421 |
| nível 2 | test | faixa 3 | 500 | 125 | 375 | 983 |

Cada combinação de nível aparece nas quatro faixas do nível 2. As **combinações seguradas** são 500 das 2.000 imagens de cada nível (12 das 144 combinações); nas faixas 2 e 3 do nível 2 a maior parte dos membros está com `?` no rótulo (421 e 983 dos 2.000 rótulos de membro de cada faixa), porque a imagem esconde o fim do membro.

### 8.3 Acerto por atributo, contra o rótulo da imagem (N1)

Cada célula: **rede** / clássica / melhor chute constante (a classe mais comum no treino), em %. O rótulo com `?` conta como uma resposta (a rede aprende a dizer `?`). Os intervalos de Wilson 95% estão no Apêndice A; os da rede ficam a até cerca de 4 pontos de cada lado.

| conjunto | lower_left | lower_right | upper_left | upper_right |
|---|---|---|---|---|
| nível 1 (n=2000) | **100,0** / 99,3 / 23,1 | **100,0** / 99,5 / 22,2 | **100,0** / 100,0 / 33,5 | **100,0** / 100,0 / 30,2 |
| faixa 0 (n=500) | **100,0** / 100,0 / 23,2 | **100,0** / 99,8 / 23,2 | **100,0** / 100,0 / 33,6 | **100,0** / 100,0 / 32,0 |
| faixa 1 (n=500) | **97,6** / 70,0 / 21,0 | **96,2** / 68,4 / 21,0 | **95,4** / 80,4 / 32,4 | **89,2** / 83,0 / 31,4 |
| faixa 2 (n=500) | **85,4** / 34,0 / 16,8 | **85,2** / 33,2 / 16,8 | **73,6** / 45,0 / 28,0 | **70,0** / 40,0 / 28,2 |
| faixa 3 (n=500) | **64,0** / 46,8 / 11,6 | **67,4** / 49,4 / 12,8 | **57,4** / 48,6 / 16,4 | **50,4** / 40,4 / 18,6 |

Cadeira de rodas e prótese (só a rede lê; a clássica não os lê; o nível 1 não tem as duas cabeças):

| conjunto | cadeira de rodas: rede / chute | prótese: rede / chute |
|---|---|---|
| faixa 0 | **100,0** / 100,0 | **100,0** / 100,0 |
| faixa 1 | **100,0** / 88,0 | **88,0** / 80,8 |
| faixa 2 | **99,8** / 69,4 | **64,6** / 57,8 |
| faixa 3 | **90,2** / 54,0 | **52,8** / 47,8 |

**Leitura.**
- **Nível 1 e faixa 0:** a rede acerta 100% nos quatro membros (limite inferior de Wilson 99,8% e 99,2%); a clássica fica em 99,3% a 100%. Aqui o desenho é limpo e o problema é fácil para as duas.
- **Faixas 1 a 3:** a rede fica bem acima da clássica e do chute em todos os membros. Cai conforme a faixa sobe (na faixa 3, 50% a 67%), e **a queda vem sobretudo do quanto a imagem esconde**: na faixa 3 os rótulos `?` são 983 de 2.000, e **boa parte do acerto da rede ali é dizer `?` onde o fim do membro está escondido** (em `lower_left`, a rede acerta 100 de 242 membros visíveis e 220 de 258 escondidos). **Só no recorte de membro visível, na faixa 3, a rede lê o nível em 26% a 45%** (Apêndice A).
- **Prótese:** na faixa 3, 52,8% contra 47,8% do chute (limites 48,4 a 57,1 contra 43,5 a 52,2): **não se separa do chute**; nas faixas 1 e 2 a vantagem é pequena (88,0 contra 80,8; 64,6 contra 57,8). A rede **não lê bem a prótese** quando ela é parcialmente escondida; cadeira de rodas vai bem (90% a 100%).

### 8.4 Consistência do espelho e calibração (teste)

A leitura da imagem espelhada (com os lados trocados de volta) é igual à leitura original, por membro e nos quatro membros juntos:

| conjunto | lower_left | lower_right | upper_left | upper_right | os quatro juntos |
|---|---|---|---|---|---|
| nível 1 | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| faixa 0 | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| faixa 1 | 98,0% | 98,4% | 96,8% | 93,6% | 87,4% |
| faixa 2 | 90,0% | 89,2% | 79,2% | 76,8% | 50,8% |
| faixa 3 | 75,6% | 77,0% | 73,0% | 73,0% | 37,0% |

Calibração da rede (confiança contra acerto de membros, ECE em 10 faixas):

| conjunto | ECE (10 faixas) | confiança média | acerto dos membros |
|---|---|---|---|
| nível 1 | 0,000 | 1,000 | 1,000 |
| faixa 0 | 0,000 | 1,000 | 1,000 |
| faixa 1 | 0,026 | 0,972 | 0,946 |
| faixa 2 | 0,042 | 0,827 | 0,785 |
| faixa 3 | 0,044 | 0,636 | 0,598 |

**Leitura.** Nos casos limpos o espelho é perfeito (o experimento imagem e laudo mostrou que o CLIP e o SmolVLM2 não sabiam esquerda de direita; esta rede, treinada com o espelho e a troca de rótulo, sabe). Nas faixas difíceis o espelho **falha mais**: nas faixas 2 e 3, os quatro membros juntos coincidem em só **50,8% e 37,0%** das imagens, embora cada membro sozinho coincida em 73% a 90%: a imagem espelhada muda a leitura em pelo menos um membro na maior parte das imagens. Cada membro sozinho coincide bem mais do que os quatro juntos, o que aponta para incerteza da rede no limite entre `?` e nível, e não para uma troca de lado; **não examinei caso a caso**. A rede é **bem calibrada** (ECE de 0 a 0,044), isto é, a confiança acompanha o acerto, o que torna o limiar da fusão significativo.

### 8.5 A classe, pelas regras, a partir da leitura da imagem

**Antes de ler:** só 27 das 432 combinações decididas têm classe não vazia, então a maior parte da classe verdadeira é o **conjunto vazio**. Por isso há duas colunas. Quando a leitura de um atributo de que a classe precisa é `?`, a classe fica como **"não decidiu"** (não é o conjunto vazio, nunca conta como correta); a taxa de "não decidiu" está à parte.

| conjunto | leitor | classe correta, todas as imagens | não decidiu | classe correta, só classe verdadeira não vazia |
|---|---|---|---|---|
| nível 1 | rede | 100,0% (2000/2000; 99,8 a 100,0) | 0,0% (0/2000) | 100,0% (252/252; 98,5 a 100,0) |
| nível 1 | clássica (postura verdadeira) | 99,7% (1993/2000; 99,3 a 99,8) | 0,0% (0/2000) | 97,2% (245/252; 94,4 a 98,6) |
| faixa 0 | rede | 100,0% (500/500; 99,2 a 100,0) | 0,0% (0/500) | 100,0% (65/65; 94,4 a 100,0) |
| faixa 0 | clássica (postura verdadeira) | 100,0% (500/500; 99,2 a 100,0) | 0,0% (0/500) | 100,0% (65/65; 94,4 a 100,0) |
| faixa 1 | rede | 84,2% (421/500; 80,7 a 87,1) | 12,8% (64/500) | 78,6% (44/56; 66,2 a 87,3) |
| faixa 1 | clássica (postura verdadeira) | 93,2% (466/500; 90,6 a 95,1) | 0,0% (0/500) | 62,5% (35/56; 49,4 a 74,0) |
| faixa 2 | rede | 41,4% (207/500; 37,2 a 45,8) | 54,6% (273/500) | 31,2% (10/32; 18,0 a 48,6) |
| faixa 2 | clássica (postura verdadeira) | 78,0% (390/500; 74,2 a 81,4) | 12,2% (61/500) | 18,8% (6/32; 8,9 a 35,3) |
| faixa 3 | rede | 7,6% (38/500; 5,6 a 10,3) | 91,8% (459/500) | 0,0% (0/22; 0,0 a 14,9) |
| faixa 3 | clássica (postura verdadeira) | 16,6% (83/500; 13,6 a 20,1) | 80,0% (400/500) | 4,5% (1/22; 0,8 a 21,8) |

**Leitura.**
- **Nível 1 e faixa 0:** a rede dá a classe certa em 100% (nível 1: 252 de 252 com classe não vazia); a clássica, com a postura verdadeira, em 99,7% e 97,2%.
- **Em todas as imagens, a clássica ganha da rede nas faixas 1 a 3** (93,2% contra 84,2%; 78,0% contra 41,4%; 16,6% contra 7,6%). Não é leitura melhor: a rede responde "não decidiu" quando o membro está escondido (12,8%, 54,6% e 91,8% das imagens) e **isso conta como errado**; a clássica decide mais vezes e acerta muitas vezes o conjunto vazio, que é a classe verdadeira da maior parte das imagens (o experimento imagem e laudo já tinha visto que ela lê membros mais longos do que são; é uma explicação provável, não verificada caso a caso).
- **No recorte de classe verdadeira não vazia, a rede ganha na faixa 1 (78,6%, 44 de 56, contra 62,5%) e na faixa 2 (31,2%, 10 de 32, contra 18,8%)**; na faixa 3, 0 de 22 contra 1 de 22. Os **n são pequenos (56, 32 e 22) e os intervalos largos** (faixa 2: 18 a 49% contra 9 a 35%, que se sobrepõem): não há aqui uma vantagem firme da rede na classe.
- **Limite do desenho, não erro da rede:** onde a imagem esconde o nível, a imagem não dá a classe certa por construção. A diferença vem do formulário (ou da fusão), seção seguinte.

### 8.6 O formulário e a fusão

O formulário é o **teto** nestes dados: sem campo faltando e sem erro dá a classe certa por construção (100,0%, nos dois níveis). A fusão usa o limiar 0,5. Cada linha: 2.000 imagens do nível. "Revisar" é o veredito da fusão quando o formulário e a rede (com confiança de pelo menos 0,5, e não `?`) discordam; **classe automática correta** = decidiu, não foi para revisão e o conjunto é o verdadeiro.

**Nível 2** (as imagens com as quatro faixas):

| faltando | errados | formulário: classe correta | fusão: classe automática correta | fusão: revisar | revisar (formulário com erro) | revisar (formulário sem erro) | não decidiu: formulário / fusão |
|---|---|---|---|---|---|---|---|
| 0% | 0% | 100,0% | 74,1% | 25,9% | n/a | 25,9% | 0,0% / 0,0% |
| 0% | 5% | 96,2% | 62,8% | 36,8% | 77,7% | 26,0% | 0,0% / 0,0% |
| 0% | 10% | 94,1% | 55,1% | 43,9% | 77,7% | 27,0% | 0,0% / 0,0% |
| 10% | 0% | 56,4% | 68,6% | 23,6% | n/a | 23,6% | 43,6% / 11,0% |
| 10% | 5% | 52,9% | 58,3% | 33,1% | 77,2% | 24,4% | 45,8% / 11,2% |
| 10% | 10% | 50,1% | 50,0% | 41,8% | 77,9% | 25,1% | 45,9% / 11,2% |
| 30% | 0% | 12,9% | 60,9% | 19,4% | n/a | 19,4% | 87,0% / 25,9% |
| 30% | 5% | 11,8% | 53,8% | 26,6% | 80,2% | 18,9% | 87,8% / 25,8% |
| 30% | 10% | 11,6% | 46,3% | 33,6% | 77,1% | 19,4% | 87,7% / 27,2% |
| 50% | 0% | 2,0% | 56,8% | 13,8% | n/a | 13,8% | 98,0% / 34,6% |
| 50% | 5% | 2,1% | 51,1% | 20,1% | 75,6% | 14,2% | 97,8% / 35,0% |
| 50% | 10% | 1,5% | 44,9% | 24,9% | 76,1% | 13,9% | 98,2% / 37,4% |

**Nível 1** (o desenho é limpo, a rede lê 100%):

| faltando | errados | formulário: classe correta | fusão: classe automática correta | fusão: revisar | revisar (formulário com erro) | revisar (formulário sem erro) | não decidiu: formulário / fusão |
|---|---|---|---|---|---|---|---|
| 0% | 0% | 100,0% | 100,0% | 0,0% | n/a | 0,0% | 0,0% / 0,0% |
| 0% | 5% | 95,8% | 82,0% | 17,9% | 100,0% | 0,0% | 0,0% / 0,0% |
| 0% | 10% | 92,0% | 66,4% | 33,6% | 100,0% | 0,0% | 0,0% / 0,0% |
| 10% | 0% | 64,7% | 100,0% | 0,0% | n/a | 0,0% | 35,4% / 0,0% |
| 10% | 5% | 62,8% | 81,5% | 18,5% | 100,0% | 0,0% | 33,6% / 0,0% |
| 10% | 10% | 60,0% | 69,5% | 30,4% | 100,0% | 0,0% | 34,5% / 0,0% |
| 30% | 0% | 25,4% | 100,0% | 0,0% | n/a | 0,0% | 74,7% / 0,0% |
| 30% | 5% | 23,3% | 86,8% | 13,2% | 100,0% | 0,0% | 75,8% / 0,0% |
| 30% | 10% | 21,1% | 75,0% | 25,0% | 100,0% | 0,0% | 76,8% / 0,0% |
| 50% | 0% | 6,5% | 100,0% | 0,0% | n/a | 0,0% | 93,5% / 0,0% |
| 50% | 5% | 5,5% | 90,5% | 9,4% | 100,0% | 0,0% | 94,2% / 0,0% |
| 50% | 10% | 6,1% | 80,8% | 19,2% | 100,0% | 0,0% | 93,3% / 0,0% |

**Leitura.**
- **Campos faltando (H3):** a fusão preenche os campos em branco com o que a rede lê e a classe automática passa de 56,4%, 12,9% e 2,0% (formulário, com 10%, 30% e 50% faltando) para **68,6%, 60,9% e 56,8%** no nível 2. No nível 1, a rede lê tudo e a fusão chega a 100% sem erros.
- **Erros no formulário:** com 5% e 10% de erros por campo, a fusão manda para revisão **cerca de 77% a 80% dos formulários com erro** no nível 2 e **100%** no nível 1 (359 de 359, 672 de 672). A rede só confirma ou contraria o que o formulário diz, e só onde enxerga.
- **O custo que a tabela mostra e que a hipótese H3 não cobre:** no nível 2, com **0% de campos faltando e 0% de erros**, a fusão manda para revisão **25,9% dos formulários certos** (a rede discorda do formulário por ler errado, ou por responder com confiança onde a imagem engana) e a classe automática correta cai de 100% para 74,1%. Com erros, a classe automática correta da fusão (62,8% e 55,1%) fica **abaixo** da do formulário sozinho (96,2% e 94,1%), porque muito caso vai para revisão (36,8% e 43,9%). **Isto não é só perda:** o formulário sozinho entrega uma **classe errada sem aviso em 3,8% e 5,9%** das imagens (100 menos a coluna "formulário"), enquanto a fusão entrega classe errada sem aviso em cerca de **0,4% e 1,0%** (conta feita: 100 menos classe automática correta, menos revisar, sem "não decidiu" nestas linhas). A troca é: **menos erro silencioso, mais trabalho de revisão.** Quanto isso vale é decisão de quem usaria, não um resultado deste teste.
- **No nível 1** a fusão não tem esse custo (revisar quando o formulário não tem erro: 0 em todas as linhas): a rede lê tudo e só discorda de um formulário errado.

### 8.7 As quatro hipóteses (todas relatadas)

| hipótese | o que mede | resultado | veredito |
|---|---|---|---|
| H1 | rede >= limite inferior do Wilson da clássica; nível 2, faixas 0 e 1, 4 membros | 8 de 8 comparações | **confirmada** |
| H2 | limite inferior do Wilson da rede > acerto da clássica; nível 2, faixas 2 e 3, 4 membros | 8 de 8 comparações | **confirmada** |
| H3 | classe automática da fusão contra a do formulário, nível 2, 0% de erros, 10/30/50% faltando | 3 de 3 | **confirmada** |
| H4 | combinações seguradas: acima do melhor chute constante e mais da metade da vantagem das vistas; 2 níveis x 4 membros | 8 de 8 | **confirmada** |

"Confirmada" aqui quer dizer **todas as comparações da hipótese valeram**, como escrito antes. O que cada confirmação **não** diz:

- **H1 (8 de 8).** Vale, mas a condição era frouxa: na faixa 0 a rede e a clássica estão ambas em 100%; na faixa 1 a rede está **bem acima** (por exemplo 97,6% contra 70,0% em `lower_left`), então a confirmação está longe da borda.
- **H2 (8 de 8).** Vale contra o rótulo inteiro, **com `?`**, como escrito. Como a seção 8.3 mostra, **parte da vantagem é saber dizer `?`**; a clássica **no recorte de membro visível não foi calculada** na rodada única do teste; ela foi calculada depois, como análise posterior ao teste, na seção 10.4 (a rede também ganha ali). A folga é menor onde a rede é mais fraca: na faixa 3, `upper_right` (50,4% contra 40,4%) passa pelo critério, mas com pouca margem.
- **H3 (3 de 3).** Vale: +12,2, +47,9 e +54,7 pontos (bootstrap por imagem: +9,7 a +14,8; +45,5 a +50,3; +52,5 a +57,0). **Mede só a classe automática correta, com 0% de erros**; a seção 8.6 mostra o custo de revisões a mais quando o formulário está certo.
- **H4 (8 de 8).** Vale: as combinações seguradas ficam **iguais** às vistas (por exemplo, nível 2 `lower_left`: 86,7% nas vistas, 86,8% nas seguradas; limite inferior de Wilson 83,6%, contra 7,6% do chute nas seguradas). **O que isto prova é pouco:** como cada valor de cada membro continua no treino, **só mostra que as cabeças não confundem os membros entre si**; **não** prova generalização a um valor ou a uma combinação de valores que a rede nunca viu. O "acaso" das seguradas (7% a 34%) é calculado sobre poucas combinações e muda de membro a membro.

Os valores completos, linha por linha, estão no Apêndice A.

## 9. O que não foi verificado e limites

1. **Sintético para real.** Tudo é N1: o gerador que fez o treino fez o teste; a rede pode usar **marcas do gerador** (cor, pose, fundo) que não existem em fotografia. **Não há nenhum resultado sobre fotos** (o nível 3 segue fora; não houve nenhum download novo). Os números aqui **não** dizem quanto a rede acertaria em imagens reais.
2. **Duas sementes de treino (0 e 1), uma configuração.** A seção 10 repete o treino com a semente 1: nas 28 células de acerto por atributo a diferença entre as sementes é de 0,6 ponto em média (máxima 3,4) e os vereditos de H1 a H4 não mudam. **Duas sementes não dão intervalo de variação**, e só a semente de treino mudou (mesmos dados, mesmas divisões); a variação por dados novos ou por outra configuração **não foi medida**.
3. **Rede pequena, CPU.** Cerca de 1 milhão de parâmetros, 20 épocas, máquina dividida com outra rodada (os tempos de época variam por isso: 207 a 374 s). A queda nas faixas 2 e 3 pode ser limite de **capacidade e resolução** (imagem reduzida a 200x140), não do método.
4. **A H4 não mede o que o nome sugere.** Ver 8.7: só mostra que as cabeças não confundem os membros; **generalização a valor novo não foi testada**. E são só 12 de 144 combinações.
5. **O formulário é simulado.** Faltas **ao acaso** e erros só de dois tipos (lado trocado ou nível errado), metade e metade. Formulários reais têm faltas e erros **que não são ao acaso**. As taxas (0 a 50%, 0 a 10%) são **escolhas minhas**, não medidas em formulários de atletas.
6. **A fusão é a mais simples (sem aprendizado), e o limiar 0,5 é o extremo da grade** (0,5 a 0,99): um limiar menor nunca foi tentado. A regra "se os dois têm valor e discordam, revisar" gera 14% a 27% de revisões em formulário certo no nível 2 (8.6); **outra regra, ou outro limiar, poderia custar menos revisões**: não foi explorado.
7. **A classe vem das regras do projeto, e só 27 de 432 combinações decididas dão classe não vazia.** A classe aqui é só a de **deficiência de membro**; não vê acuidade, QI, medidas. É uma **sugestão de classes candidatas, sujeita à classificação oficial**, nunca decisão. Em todas as imagens "classe correta" **mede mais o conjunto vazio** do que a leitura (8.5).
8. **Medidas que não calculei.** (a) ~~A linha de base clássica no recorte de membro visível~~ (calculada depois, como **análise posterior ao teste**, na seção 10.4: a rede ganha da clássica ali; nos braços da faixa 3 não se separa do chute); (b) a taxa de **classe errada sem aviso da fusão** por contagem direta (só a derivei das colunas da tabela, em 8.6); (c) a **ablação do espelho** (treinar sem o aumento: o programa tem a opção `--no-mirror`, mas eu não rodei); (d) acerto por **classe** (cada classe do catálogo); (e) o efeito do tamanho do treino.
9. **A linha de base clássica usa a postura verdadeira** para a classe (a clássica não lê cadeira nem prótese): isso a **favorece**. Mesmo assim, no recorte de classe verdadeira não vazia, a rede tem n de 22 a 56 e intervalos que se sobrepõem aos da clássica (8.5).
10. **Cadeira de rodas e prótese no nível 1.** O boneco do nível 1 não tem nenhuma das duas; as cabeças só treinaram no nível 2, e no nível 1 a fusão trata os dois campos como "não" (o formulário não os deixa em branco).
11. **Comparações múltiplas.** Cada hipótese exige todas as comparações (8, 8, 3 e 8) com intervalos de 95% sem correção; "confirmada" é **todas valeram**, não uma conta de erro conjunto. As hipóteses foram fixadas antes de qualquer rodada (19/11/2026).
12. **Reprodução.** Sementes e tamanhos estão no código; imagens, pesos e saídas ficam **fora do repositório** (`<pasta IMAGEM_FORMULARIO_HOME>`), por tamanho. Uma pessoa que clone o repositório precisa gerar os dados (`imagem_formulario.make_data`, cerca de 19 min) e treinar (cerca de 109 min na máquina usada).
13. **O que foi corrigido no processo e é visível acima:** um erro de código no relatório do desenvolvimento; uma tentativa de treino interrompida (nada visto no teste); um ensaio do script final com dados do desenvolvimento.


## 10. Replicação com uma segunda semente de treino (semente 1)

**Rótulo desta seção: replicação, semente 1, nenhum ajuste; o teste já tinha sido aberto antes (rodada 1, semente 0). Evidência N1** (desenho sintético, rótulos por construção). A subseção 10.4 é uma **análise posterior ao teste**, não prevista antes. As seções 1 a 9 não foram reescritas; só o item 2 e o item 8 da seção 9 foram atualizados, e uma frase da 8.7 aponta para a 10.4.

### 10.1 O que foi feito

- **Segundo treino da mesma rede** (`run2`), mesma configuração, **mesmos dados e mesmas divisões**; só a semente de treino muda (semente 1, que controla a inicialização da rede, a ordem dos lotes e o sorteio do espelhamento). 20 épocas, melhor época pelo desenvolvimento, **limiar da fusão fixo em 0,5** (não foi escolhido de novo; `replicate.py` exige o 0,5). **Nada foi ajustado e nada foi escolhido entre as duas sementes**: as duas aparecem lado a lado.
- **Avaliação no teste com um script à parte** (`spikes/imagem_formulario/replicate.py`); o `final.py`, que recusa a segunda rodada, **não foi alterado nem desligado**. Para conferir o script, rodei antes a semente 0 nas duas posições: reproduziu os números da rodada 1 (por exemplo, fusão 74,1% com 0% de faltas e 0% de erros).
- **Treino da semente 1:** 35,9 min (100 a 142 s por época), **máquina livre**, melhor época a **19** (acerto de membros no desenvolvimento 91,24%), pico de RAM 3.447 MB. A semente 0 levou 108,9 min (207 a 374 s por época) com a máquina dividida, melhor época a 16 (91,24%). **Os tempos das duas sementes não são comparáveis** (a primeira dividiu a máquina com outra rodada) e o acerto no desenvolvimento ficou igual até a quarta casa decimal nas duas, por coincidência.

### 10.2 As quatro hipóteses, nas duas sementes

| hipótese | semente 0 | semente 1 |
|---|---|---|
| H1 (rede contra clássica, faixas 0 e 1) | 8 de 8, confirmada | 8 de 8, confirmada |
| H2 (rede contra clássica, faixas 2 e 3) | 8 de 8, confirmada | 8 de 8, confirmada |
| H3 (classe da fusão contra o formulário, 10/30/50% faltando) | 3 de 3, confirmada; +12,2, +47,9 e +54,7 pontos | 3 de 3, confirmada; +10,7, +47,6 e +55,0 pontos (bootstrap +8,0 a +13,5; +45,1 a +50,1; +52,9 a +57,3) |
| H4 (combinações seguradas) | 8 de 8, confirmada | 8 de 8, confirmada |

Os mesmos critérios, escritos antes da rodada 1, valem nas duas sementes; **nenhuma hipótese mudou de veredito**. As ressalvas da seção 8.7 seguem valendo (H4 só mede confusão entre as cabeças, H3 não mostra o custo das revisões, e assim por diante). A saída completa está no Apêndice B.

### 10.3 Variação entre as sementes, por célula

Acerto contra o rótulo da imagem (N1). Cada célula: semente 0 / semente 1 (diferença em pontos, semente 1 menos semente 0).

| conjunto | lower_left | lower_right | upper_left | upper_right | wheelchair | prosthesis |
|---|---|---|---|---|---|---|
| nível 1 | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | n/a | n/a |
| faixa 0 | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) |
| faixa 1 | 97,6 / 97,4 (-0,2) | 96,2 / 95,6 (-0,6) | 95,4 / 95,8 (+0,4) | 89,2 / 89,8 (+0,6) | 100,0 / 100,0 (+0,0) | 88,0 / 86,0 (-2,0) |
| faixa 2 | 85,4 / 84,6 (-0,8) | 85,2 / 85,0 (-0,2) | 73,6 / 75,0 (+1,4) | 70,0 / 70,4 (+0,4) | 99,8 / 99,8 (+0,0) | 64,6 / 67,4 (+2,8) |
| faixa 3 | 64,0 / 65,2 (+1,2) | 67,4 / 64,0 (-3,4) | 57,4 / 57,4 (+0,0) | 50,4 / 51,4 (+1,0) | 90,2 / 91,6 (+1,4) | 52,8 / 53,2 (+0,4) |

**Nas 28 células de acerto por atributo, a diferença absoluta entre as sementes tem média de 0,6 ponto e máxima de 3,4 pontos** (faixa 3, `lower_right`: 67,4% contra 64,0%). Cada célula tem 500 imagens, e o intervalo de Wilson 95% de uma só semente é de cerca de 4 pontos para cada lado nas faixas difíceis: **a diferença entre sementes é menor do que o ruído da amostra do teste**. Não é um intervalo de variação do treino: **duas sementes dão duas medidas, não uma variância**.

Consistência do espelho (leitura da imagem espelhada igual à original, lados trocados de volta):

| conjunto | lower_left | lower_right | upper_left | upper_right | os quatro membros juntos |
|---|---|---|---|---|---|
| nível 1 | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) |
| faixa 0 | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) | 100,0 / 100,0 (+0,0) |
| faixa 1 | 98,0 / 98,4 (+0,4) | 98,4 / 98,6 (+0,2) | 96,8 / 97,6 (+0,8) | 93,6 / 94,2 (+0,6) | 87,4 / 89,2 (+1,8) |
| faixa 2 | 90,0 / 91,8 (+1,8) | 89,2 / 88,8 (-0,4) | 79,2 / 81,2 (+2,0) | 76,8 / 79,6 (+2,8) | 50,8 / 54,0 (+3,2) |
| faixa 3 | 75,6 / 79,0 (+3,4) | 77,0 / 79,4 (+2,4) | 73,0 / 73,6 (+0,6) | 73,0 / 73,2 (+0,2) | 37,0 / 39,0 (+2,0) |

A semente 1 é **um pouco mais consistente** (de 0,2 a 3,4 pontos, em 14 das 15 células em que há variação; a outra, `lower_right` da faixa 2, é −0,4), mas **o quadro é o mesmo**: nas faixas 2 e 3 os quatro membros juntos coincidem em só 54,0% e 39,0% (semente 0: 50,8% e 37,0%). A fragilidade do espelho nas faixas difíceis **não é um acidente de uma semente**.

Fusão no nível 2: classe automática correta e taxa de revisão (semente 0 / semente 1); o formulário sozinho é o mesmo nas duas sementes:

| nível | faltando | errados | classe automática correta (s0 / s1) | revisar (s0 / s1) | formulário (é o mesmo nas duas sementes) |
|---|---|---|---|---|---|
| nível 2 | 0% | 0% | 74,1 / 71,4 (-2,7) | 25,9 / 28,6 (+2,7) | 100,0 |
| nível 2 | 0% | 5% | 62,8 / 60,4 (-2,4) | 36,8 / 39,4 (+2,6) | 96,2 |
| nível 2 | 0% | 10% | 55,1 / 52,9 (-2,2) | 43,9 / 46,2 (+2,3) | 94,1 |
| nível 2 | 10% | 0% | 68,6 / 67,0 (-1,6) | 23,6 / 26,3 (+2,8) | 56,4 |
| nível 2 | 10% | 5% | 58,3 / 58,0 (-0,3) | 33,1 / 35,6 (+2,5) | 52,9 |
| nível 2 | 10% | 10% | 50,0 / 48,0 (-2,0) | 41,8 / 45,0 (+3,2) | 50,1 |
| nível 2 | 30% | 0% | 60,9 / 60,6 (-0,3) | 19,4 / 21,1 (+1,7) | 12,9 |
| nível 2 | 30% | 5% | 53,8 / 54,4 (+0,7) | 26,6 / 27,6 (+1,0) | 11,8 |
| nível 2 | 30% | 10% | 46,3 / 46,5 (+0,2) | 33,6 / 35,5 (+1,8) | 11,6 |
| nível 2 | 50% | 0% | 56,8 / 57,0 (+0,3) | 13,8 / 15,7 (+1,9) | 2,0 |
| nível 2 | 50% | 5% | 51,1 / 52,1 (+1,0) | 20,1 / 22,1 (+1,9) | 2,1 |
| nível 2 | 50% | 10% | 44,9 / 46,3 (+1,5) | 24,9 / 27,1 (+2,2) | 1,5 |

- **Com 10, 30 e 50% de faltas e 0% de erros**, a classe automática correta da semente 1 é 67,0%, 60,6% e 57,0%, contra 68,6%, 60,9% e 56,8% da semente 0 (diferenças de −1,6, −0,3 e +0,3).
- **A taxa de revisão da semente 1 é maior em todas as 12 linhas do nível 2** (de 1,0 a 3,2 pontos): **o custo da fusão (revisar formulários certos, com 0% de erros) é da ordem de 14% a 29% nas duas sementes**, e a semente 1 está no lado mais alto (28,6% com 0% de faltas e 0% de erros, contra 25,9%; a classe automática correta cai a 71,4%, contra 74,1%). No nível 1 as duas sementes dão os mesmos números (a rede lê 100%).
- **Cadeira de rodas** e **prótese** seguem como no 8.3: a prótese continua perto do chute na faixa 3 (53,2% na semente 1, contra 52,8%).

### 10.4 Análise posterior ao teste: o recorte de membro visível

**Rótulo: análise posterior ao teste (não prevista antes).** Fecha a dúvida deixada em 8.3 e 8.7 (H2): só as imagens em que o rótulo do membro **não** é `?`, nível 2. Cada célula: acerto % (k/n; Wilson 95%). A "clássica" é a linha de base do experimento imagem e laudo, lendo os mesmos PNG; o "chute" é a classe mais comum entre os rótulos visíveis do treino.

| faixa (nível 2) | membro | clássica | rede, semente 0 | rede, semente 1 | melhor chute constante (visíveis) |
|---|---|---|---|---|---|
| faixa 0 | lower_left | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 23,2% (116/500; 19,7 a 27,1) |
| faixa 0 | lower_right | 99,8% (499/500; 98,9 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 23,2% (116/500; 19,7 a 27,1) |
| faixa 0 | upper_left | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 33,6% (168/500; 29,6 a 37,9) |
| faixa 0 | upper_right | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 100,0% (500/500; 99,2 a 100,0) | 32,0% (160/500; 28,1 a 36,2) |
| faixa 1 | lower_left | 75,4% (350/464; 71,3 a 79,1) | 98,3% (456/464; 96,6 a 99,1) | 98,7% (458/464; 97,2 a 99,4) | 22,6% (105/464; 19,1 a 26,7) |
| faixa 1 | lower_right | 75,5% (342/453; 71,3 a 79,2) | 98,2% (445/453; 96,6 a 99,1) | 98,0% (444/453; 96,3 a 99,0) | 23,2% (105/453; 19,5 a 27,3) |
| faixa 1 | upper_left | 84,1% (402/478; 80,6 a 87,1) | 97,7% (467/478; 95,9 a 98,7) | 98,3% (470/478; 96,7 a 99,1) | 33,9% (162/478; 29,8 a 38,2) |
| faixa 1 | upper_right | 85,4% (415/486; 82,0 a 88,3) | 90,7% (441/486; 87,8 a 93,0) | 90,9% (442/486; 88,1 a 93,2) | 32,3% (157/486; 28,3 a 36,6) |
| faixa 2 | lower_left | 40,8% (152/373; 35,9 a 45,8) | 85,0% (317/373; 81,0 a 88,3) | 85,0% (317/373; 81,0 a 88,3) | 22,5% (84/373; 18,6 a 27,0) |
| faixa 2 | lower_right | 39,9% (148/371; 35,0 a 45,0) | 84,9% (315/371; 80,9 a 88,2) | 86,8% (322/371; 83,0 a 89,9) | 22,6% (84/371; 18,7 a 27,2) |
| faixa 2 | upper_left | 49,9% (206/413; 45,1 a 54,7) | 74,8% (309/413; 70,4 a 78,8) | 77,5% (320/413; 73,2 a 81,2) | 33,9% (140/413; 29,5 a 38,6) |
| faixa 2 | upper_right | 43,8% (185/422; 39,2 a 48,6) | 70,6% (298/422; 66,1 a 74,8) | 70,6% (298/422; 66,1 a 74,8) | 33,4% (141/422; 29,1 a 38,0) |
| faixa 3 | lower_left | 6,6% (16/242; 4,1 a 10,5) | 41,3% (100/242; 35,3 a 47,6) | 45,9% (111/242; 39,7 a 52,2) | 24,0% (58/242; 19,0 a 29,7) |
| faixa 3 | lower_right | 8,9% (21/236; 5,9 a 13,2) | 45,3% (107/236; 39,1 a 51,7) | 43,6% (103/236; 37,5 a 50,0) | 27,1% (64/236; 21,8 a 33,1) |
| faixa 3 | upper_left | 10,9% (27/248; 7,6 a 15,4) | 29,8% (74/248; 24,5 a 35,8) | 37,1% (92/248; 31,3 a 43,3) | 33,1% (82/248; 27,5 a 39,1) |
| faixa 3 | upper_right | 9,3% (27/291; 6,5 a 13,2) | 26,5% (77/291; 21,7 a 31,8) | 30,2% (88/291; 25,2 a 35,7) | 32,0% (93/291; 26,9 a 37,5) |

**Leitura.**
- **A rede ganha da clássica no recorte visível, nas duas sementes, em todas as faixas e membros** (faixa 1: 90,7% a 98,7% contra 75,4% a 85,4%; faixa 2: 70,6% a 86,8% contra 39,9% a 49,9%; faixa 3: 26,5% a 45,9% contra 6,6% a 10,9%). **A vantagem da rede sobre a clássica nas faixas 2 e 3 (H2) não vem só de saber dizer `?`.** A clássica, no recorte visível, **fica abaixo do chute constante na faixa 3, em todos os membros** (por exemplo, 6,6% contra 24,0% em `lower_left`; na faixa 2 ela ainda fica acima do chute, 39,9% a 49,9% contra 22,5% a 33,9%): é enganada sempre no mesmo sentido, como o experimento imagem e laudo já tinha medido.
- **Mas a rede também é fraca onde o fim do membro está visível e difícil (faixa 3).** Nos membros inferiores ela passa do chute nas duas sementes (41,3% e 45,9% contra 24,0%, `lower_left`; 45,3% e 43,6% contra 27,1%, `lower_right`). **Nos membros superiores da faixa 3 ela não se separa do chute**: `upper_left` 29,8% e 37,1% contra 33,1%; `upper_right` 26,5% e 30,2% contra 32,0% (os intervalos incluem o chute, salvo `upper_right` da semente 0, cujo limite superior, 31,8%, fica logo abaixo dele, 32,0%; a semente 0 fica abaixo do chute nos dois braços). A rede não "lê" o nível do braço visível na faixa 3 de forma comprovada por estes dados.
- **O que isto muda na conclusão:** a confirmação de H2 **se sustenta** (a rede supera a clássica também onde o membro está visível), e a rede é uma **leitora útil até a faixa 2**; **na faixa 3 o ganho útil sobre o chute é só nas pernas**.

### 10.5 O que a replicação não resolve

- **Duas sementes não dão intervalo de variação.** A estimativa de 0 a 3 pontos de diferença é uma ordem de grandeza, não uma medida com intervalo; uma terceira semente poderia mostrar uma diferença maior.
- **Só a semente de treino mudou.** Os dados, as divisões, as 12 combinações seguradas, o gerador e o formulário simulado são os mesmos. **A variação por dados novos, por outras combinações seguradas ou por outra configuração não foi medida.**
- Tudo continua **N1**; o que a seção 9 diz sobre fotos, formulário simulado e limite da H4 vale sem mudança.

## Apêndice A. Saída completa da rodada única do teste

É o arquivo `final_run1.md` (fora do repositório), sem edição, com os títulos rebaixados um nível. Os números têm ponto decimal; os intervalos são Wilson 95% (a clássica e o chute constante também).

## Rodada 1 no conjunto de teste (2026-11-19 13:27)

Evidência N1: desenho sintético, rótulos por construção. Aviso para revisão humana, não decisão.
Limiar da fusão (do desenvolvimento): 0.5.

### Tamanhos
| nível | conjunto | faixa | imagens | de combinações seguradas | de combinações vistas | membros `?` no rótulo da imagem |
|---|---|---|---|---|---|---|
| nível 1 | test | nível 1 | 2000 | 500 | 1500 | 0 |
| nível 2 | test | faixa 0 | 500 | 125 | 375 | 0 |
| nível 2 | test | faixa 1 | 500 | 125 | 375 | 119 |
| nível 2 | test | faixa 2 | 500 | 125 | 375 | 421 |
| nível 2 | test | faixa 3 | 500 | 125 | 375 | 983 |

### Acerto por atributo contra o rótulo da imagem
| conjunto | leitor | lower_left | lower_right | upper_left | upper_right | wheelchair | prosthesis |
|---|---|---|---|---|---|---|---|
| nível 1 (n=2000) | rede | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | n/a (n=0) | n/a (n=0) |
| nível 1 (n=2000) | rede (só onde a imagem mostra o atributo) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | n/a (n=0) | n/a (n=0) |
| nível 1 (n=2000) | clássica (só membros) | 99.3% (1987/2000; 98.9 a 99.6) | 99.5% (1990/2000; 99.1 a 99.7) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | n/a | n/a |
| nível 1 (n=2000) | melhor chute constante | 23.1% (462/2000; 21.3 a 25.0) | 22.2% (444/2000; 20.4 a 24.1) | 33.5% (670/2000; 31.5 a 35.6) | 30.2% (605/2000; 28.3 a 32.3) | n/a | n/a |
| faixa 0 (n=500) | rede | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) |
| faixa 0 (n=500) | rede (só onde a imagem mostra o atributo) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) |
| faixa 0 (n=500) | clássica (só membros) | 100.0% (500/500; 99.2 a 100.0) | 99.8% (499/500; 98.9 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | n/a | n/a |
| faixa 0 (n=500) | melhor chute constante | 23.2% (116/500; 19.7 a 27.1) | 23.2% (116/500; 19.7 a 27.1) | 33.6% (168/500; 29.6 a 37.9) | 32.0% (160/500; 28.1 a 36.2) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) |
| faixa 1 (n=500) | rede | 97.6% (488/500; 95.9 a 98.6) | 96.2% (481/500; 94.1 a 97.6) | 95.4% (477/500; 93.2 a 96.9) | 89.2% (446/500; 86.2 a 91.6) | 100.0% (500/500; 99.2 a 100.0) | 88.0% (440/500; 84.9 a 90.6) |
| faixa 1 (n=500) | rede (só onde a imagem mostra o atributo) | 98.3% (456/464; 96.6 a 99.1) | 98.2% (445/453; 96.6 a 99.1) | 97.7% (467/478; 95.9 a 98.7) | 90.7% (441/486; 87.8 a 93.0) | 100.0% (500/500; 99.2 a 100.0) | 88.7% (440/496; 85.6 a 91.2) |
| faixa 1 (n=500) | clássica (só membros) | 70.0% (350/500; 65.8 a 73.9) | 68.4% (342/500; 64.2 a 72.3) | 80.4% (402/500; 76.7 a 83.6) | 83.0% (415/500; 79.5 a 86.0) | n/a | n/a |
| faixa 1 (n=500) | melhor chute constante | 21.0% (105/500; 17.7 a 24.8) | 21.0% (105/500; 17.7 a 24.8) | 32.4% (162/500; 28.4 a 36.6) | 31.4% (157/500; 27.5 a 35.6) | 88.0% (440/500; 84.9 a 90.6) | 80.8% (404/500; 77.1 a 84.0) |
| faixa 2 (n=500) | rede | 85.4% (427/500; 82.0 a 88.2) | 85.2% (426/500; 81.8 a 88.0) | 73.6% (368/500; 69.6 a 77.3) | 70.0% (350/500; 65.8 a 73.9) | 99.8% (499/500; 98.9 a 100.0) | 64.6% (323/500; 60.3 a 68.7) |
| faixa 2 (n=500) | rede (só onde a imagem mostra o atributo) | 85.0% (317/373; 81.0 a 88.3) | 84.9% (315/371; 80.9 a 88.2) | 74.8% (309/413; 70.4 a 78.8) | 70.6% (298/422; 66.1 a 74.8) | 100.0% (499/499; 99.2 a 100.0) | 68.3% (319/467; 64.0 a 72.4) |
| faixa 2 (n=500) | clássica (só membros) | 34.0% (170/500; 30.0 a 38.3) | 33.2% (166/500; 29.2 a 37.4) | 45.0% (225/500; 40.7 a 49.4) | 40.0% (200/500; 35.8 a 44.4) | n/a | n/a |
| faixa 2 (n=500) | melhor chute constante | 16.8% (84/500; 13.8 a 20.3) | 16.8% (84/500; 13.8 a 20.3) | 28.0% (140/500; 24.2 a 32.1) | 28.2% (141/500; 24.4 a 32.3) | 69.4% (347/500; 65.2 a 73.3) | 57.8% (289/500; 53.4 a 62.1) |
| faixa 3 (n=500) | rede | 64.0% (320/500; 59.7 a 68.1) | 67.4% (337/500; 63.2 a 71.4) | 57.4% (287/500; 53.0 a 61.7) | 50.4% (252/500; 46.0 a 54.8) | 90.2% (451/500; 87.3 a 92.5) | 52.8% (264/500; 48.4 a 57.1) |
| faixa 3 (n=500) | rede (só onde a imagem mostra o atributo) | 41.3% (100/242; 35.3 a 47.6) | 45.3% (107/236; 39.1 a 51.7) | 29.8% (74/248; 24.5 a 35.8) | 26.5% (77/291; 21.7 a 31.8) | 94.3% (450/477; 91.9 a 96.1) | 57.6% (239/415; 52.8 a 62.3) |
| faixa 3 (n=500) | clássica (só membros) | 46.8% (234/500; 42.5 a 51.2) | 49.4% (247/500; 45.0 a 53.8) | 48.6% (243/500; 44.2 a 53.0) | 40.4% (202/500; 36.2 a 44.8) | n/a | n/a |
| faixa 3 (n=500) | melhor chute constante | 11.6% (58/500; 9.1 a 14.7) | 12.8% (64/500; 10.2 a 16.0) | 16.4% (82/500; 13.4 a 19.9) | 18.6% (93/500; 15.4 a 22.2) | 54.0% (270/500; 49.6 a 58.3) | 47.8% (239/500; 43.5 a 52.2) |

### Consistência do espelho (leitura da imagem espelhada igual à original com os lados trocados)
| conjunto | lower_left | lower_right | upper_left | upper_right | os quatro membros juntos |
|---|---|---|---|---|---|
| nível 1 | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) |
| faixa 0 | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) |
| faixa 1 | 98.0% (490/500; 96.4 a 98.9) | 98.4% (492/500; 96.9 a 99.2) | 96.8% (484/500; 94.9 a 98.0) | 93.6% (468/500; 91.1 a 95.4) | 87.4% (437/500; 84.2 a 90.0) |
| faixa 2 | 90.0% (450/500; 87.1 a 92.3) | 89.2% (446/500; 86.2 a 91.6) | 79.2% (396/500; 75.4 a 82.5) | 76.8% (384/500; 72.9 a 80.3) | 50.8% (254/500; 46.4 a 55.2) |
| faixa 3 | 75.6% (378/500; 71.6 a 79.2) | 77.0% (385/500; 73.1 a 80.5) | 73.0% (365/500; 68.9 a 76.7) | 73.0% (365/500; 68.9 a 76.7) | 37.0% (185/500; 32.9 a 41.3) |

### Calibração da rede
| conjunto | ECE (10 faixas) | confiança média | acerto dos membros | imagens |
|---|---|---|---|---|
| nível 1 | 0.000 | 1.000 | 1.000 | 2000 |
| faixa 0 | 0.000 | 1.000 | 1.000 | 500 |
| faixa 1 | 0.026 | 0.972 | 0.946 | 500 |
| faixa 2 | 0.042 | 0.827 | 0.785 | 500 |
| faixa 3 | 0.044 | 0.636 | 0.598 | 500 |

### Classe pelas regras, braço da imagem e linha de base clássica
| conjunto | leitor | classe correta (todas as imagens) | bootstrap 95% | não decidiu | classe correta só onde a classe verdadeira não é vazia |
|---|---|---|---|---|---|
| nível 1 | imagem (rede) | 100.0% (2000/2000; 99.8 a 100.0) | 100.0 a 100.0 | 0.0% (0/2000) | 100.0% (252/252; 98.5 a 100.0) |
| nível 1 | clássica, postura verdadeira | 99.7% (1993/2000; 99.3 a 99.8) | 99.4 a 99.9 | 0.0% (0/2000) | 97.2% (245/252; 94.4 a 98.6) |
| faixa 0 | imagem (rede) | 100.0% (500/500; 99.2 a 100.0) | 100.0 a 100.0 | 0.0% (0/500) | 100.0% (65/65; 94.4 a 100.0) |
| faixa 0 | imagem (rede), postura verdadeira | 100.0% (500/500; 99.2 a 100.0) | 100.0 a 100.0 | 0.0% (0/500) | 100.0% (65/65; 94.4 a 100.0) |
| faixa 0 | clássica, postura verdadeira | 100.0% (500/500; 99.2 a 100.0) | 100.0 a 100.0 | 0.0% (0/500) | 100.0% (65/65; 94.4 a 100.0) |
| faixa 1 | imagem (rede) | 84.2% (421/500; 80.7 a 87.1) | 80.6 a 87.4 | 12.8% (64/500) | 78.6% (44/56; 66.2 a 87.3) |
| faixa 1 | imagem (rede), postura verdadeira | 84.8% (424/500; 81.4 a 87.7) | 81.6 a 88.2 | 12.8% (64/500) | 80.4% (45/56; 68.2 a 88.7) |
| faixa 1 | clássica, postura verdadeira | 93.2% (466/500; 90.6 a 95.1) | 90.8 a 95.2 | 0.0% (0/500) | 62.5% (35/56; 49.4 a 74.0) |
| faixa 2 | imagem (rede) | 41.4% (207/500; 37.2 a 45.8) | 37.4 a 45.8 | 54.6% (273/500) | 31.2% (10/32; 18.0 a 48.6) |
| faixa 2 | imagem (rede), postura verdadeira | 41.8% (209/500; 37.6 a 46.2) | 37.8 a 46.2 | 54.6% (273/500) | 37.5% (12/32; 22.9 a 54.7) |
| faixa 2 | clássica, postura verdadeira | 78.0% (390/500; 74.2 a 81.4) | 74.4 a 81.2 | 12.2% (61/500) | 18.8% (6/32; 8.9 a 35.3) |
| faixa 3 | imagem (rede) | 7.6% (38/500; 5.6 a 10.3) | 5.2 a 10.2 | 91.8% (459/500) | 0.0% (0/22; 0.0 a 14.9) |
| faixa 3 | imagem (rede), postura verdadeira | 7.8% (39/500; 5.8 a 10.5) | 5.6 a 10.2 | 91.8% (459/500) | 0.0% (0/22; 0.0 a 14.9) |
| faixa 3 | clássica, postura verdadeira | 16.6% (83/500; 13.6 a 20.1) | 13.4 a 20.0 | 80.0% (400/500) | 4.5% (1/22; 0.8 a 21.8) |

### Formulário e fusão (curva do formulário)
| nível | campos faltando | campos errados | formulário: classe correta | fusão: classe automática correta | fusão: revisar | revisar quando o formulário tem erro | revisar quando o formulário não tem erro | não decidiu (formulário / fusão) |
|---|---|---|---|---|---|---|---|---|
| nível 1 | 0% | 0% | 100.0% (2000/2000; 99.8 a 100.0) | 100.0% (2000/2000; 99.8 a 100.0) | 0.0% | n/a (n=0) | 0.0% (0/2000; 0.0 a 0.2) | 0.0% / 0.0% |
| nível 1 | 0% | 5% | 95.8% (1915/2000; 94.8 a 96.5) | 82.0% (1641/2000; 80.3 a 83.7) | 17.9% | 100.0% (359/359; 98.9 a 100.0) | 0.0% (0/1641; 0.0 a 0.2) | 0.0% / 0.0% |
| nível 1 | 0% | 10% | 92.0% (1840/2000; 90.7 a 93.1) | 66.4% (1328/2000; 64.3 a 68.4) | 33.6% | 100.0% (672/672; 99.4 a 100.0) | 0.0% (0/1328; 0.0 a 0.3) | 0.0% / 0.0% |
| nível 1 | 10% | 0% | 64.7% (1293/2000; 62.5 a 66.7) | 100.0% (2000/2000; 99.8 a 100.0) | 0.0% | n/a (n=0) | 0.0% (0/2000; 0.0 a 0.2) | 35.4% / 0.0% |
| nível 1 | 10% | 5% | 62.8% (1255/2000; 60.6 a 64.8) | 81.5% (1630/2000; 79.7 a 83.1) | 18.5% | 100.0% (370/370; 99.0 a 100.0) | 0.0% (0/1630; 0.0 a 0.2) | 33.6% / 0.0% |
| nível 1 | 10% | 10% | 60.0% (1199/2000; 57.8 a 62.1) | 69.5% (1391/2000; 67.5 a 71.5) | 30.4% | 100.0% (609/609; 99.4 a 100.0) | 0.0% (0/1391; 0.0 a 0.3) | 34.5% / 0.0% |
| nível 1 | 30% | 0% | 25.4% (507/2000; 23.5 a 27.3) | 100.0% (2000/2000; 99.8 a 100.0) | 0.0% | n/a (n=0) | 0.0% (0/2000; 0.0 a 0.2) | 74.7% / 0.0% |
| nível 1 | 30% | 5% | 23.3% (466/2000; 21.5 a 25.2) | 86.8% (1737/2000; 85.3 a 88.3) | 13.2% | 100.0% (263/263; 98.6 a 100.0) | 0.0% (0/1737; 0.0 a 0.2) | 75.8% / 0.0% |
| nível 1 | 30% | 10% | 21.1% (421/2000; 19.3 a 22.9) | 75.0% (1500/2000; 73.1 a 76.8) | 25.0% | 100.0% (500/500; 99.2 a 100.0) | 0.0% (0/1500; 0.0 a 0.3) | 76.8% / 0.0% |
| nível 1 | 50% | 0% | 6.5% (129/2000; 5.5 a 7.6) | 100.0% (2000/2000; 99.8 a 100.0) | 0.0% | n/a (n=0) | 0.0% (0/2000; 0.0 a 0.2) | 93.5% / 0.0% |
| nível 1 | 50% | 5% | 5.5% (109/2000; 4.5 a 6.5) | 90.5% (1811/2000; 89.2 a 91.8) | 9.4% | 100.0% (189/189; 98.0 a 100.0) | 0.0% (0/1811; 0.0 a 0.2) | 94.2% / 0.0% |
| nível 1 | 50% | 10% | 6.1% (122/2000; 5.1 a 7.2) | 80.8% (1616/2000; 79.0 a 82.5) | 19.2% | 100.0% (384/384; 99.0 a 100.0) | 0.0% (0/1616; 0.0 a 0.2) | 93.3% / 0.0% |
| nível 2 | 0% | 0% | 100.0% (2000/2000; 99.8 a 100.0) | 74.1% (1482/2000; 72.1 a 76.0) | 25.9% | n/a (n=0) | 25.9% (518/2000; 24.0 a 27.9) | 0.0% / 0.0% |
| nível 2 | 0% | 5% | 96.2% (1924/2000; 95.3 a 97.0) | 62.8% (1256/2000; 60.7 a 64.9) | 36.8% | 77.7% (324/417; 73.5 a 81.4) | 26.0% (412/1583; 23.9 a 28.2) | 0.0% / 0.0% |
| nível 2 | 0% | 10% | 94.1% (1882/2000; 93.0 a 95.1) | 55.1% (1103/2000; 53.0 a 57.3) | 43.9% | 77.7% (519/668; 74.4 a 80.7) | 27.0% (359/1332; 24.6 a 29.4) | 0.0% / 0.0% |
| nível 2 | 10% | 0% | 56.4% (1127/2000; 54.2 a 58.5) | 68.6% (1372/2000; 66.5 a 70.6) | 23.6% | n/a (n=0) | 23.6% (471/2000; 21.7 a 25.5) | 43.6% / 11.0% |
| nível 2 | 10% | 5% | 52.9% (1057/2000; 50.7 a 55.0) | 58.3% (1166/2000; 56.1 a 60.4) | 33.1% | 77.2% (254/329; 72.4 a 81.4) | 24.4% (408/1671; 22.4 a 26.5) | 45.8% / 11.2% |
| nível 2 | 10% | 10% | 50.1% (1002/2000; 47.9 a 52.3) | 50.0% (1000/2000; 47.8 a 52.2) | 41.8% | 77.9% (491/630; 74.5 a 81.0) | 25.1% (344/1370; 22.9 a 27.5) | 45.9% / 11.2% |
| nível 2 | 30% | 0% | 12.9% (259/2000; 11.5 a 14.5) | 60.9% (1218/2000; 58.7 a 63.0) | 19.4% | n/a (n=0) | 19.4% (388/2000; 17.7 a 21.2) | 87.0% / 25.9% |
| nível 2 | 30% | 5% | 11.8% (235/2000; 10.4 a 13.2) | 53.8% (1075/2000; 51.6 a 55.9) | 26.6% | 80.2% (202/252; 74.8 a 84.6) | 18.9% (330/1748; 17.1 a 20.8) | 87.8% / 25.8% |
| nível 2 | 30% | 10% | 11.6% (231/2000; 10.2 a 13.0) | 46.3% (926/2000; 44.1 a 48.5) | 33.6% | 77.1% (380/493; 73.2 a 80.6) | 19.4% (293/1507; 17.5 a 21.5) | 87.7% / 27.2% |
| nível 2 | 50% | 0% | 2.0% (41/2000; 1.5 a 2.8) | 56.8% (1135/2000; 54.6 a 58.9) | 13.8% | n/a (n=0) | 13.8% (276/2000; 12.4 a 15.4) | 98.0% / 34.6% |
| nível 2 | 50% | 5% | 2.1% (43/2000; 1.6 a 2.9) | 51.1% (1022/2000; 48.9 a 53.3) | 20.1% | 75.6% (146/193; 69.1 a 81.2) | 14.2% (257/1807; 12.7 a 15.9) | 97.8% / 35.0% |
| nível 2 | 50% | 10% | 1.5% (30/2000; 1.1 a 2.1) | 44.9% (897/2000; 42.7 a 47.0) | 24.9% | 76.1% (270/355; 71.4 a 80.2) | 13.9% (229/1645; 12.3 a 15.7) | 98.2% / 37.4% |

### Hipóteses
| hipótese | o que mede | resultado | veredito |
|---|---|---|---|
| H1 | rede >= limite inferior do Wilson da clássica; nível 2, faixas 0 e 1, 4 membros | 8 de 8 comparações | **confirmada** |
| H2 | limite inferior do Wilson da rede > acerto da clássica; nível 2, faixas 2 e 3, 4 membros | 8 de 8 comparações | **confirmada** |
| H3 | classe automática da fusão contra a do formulário, nível 2, 0% de erros, 10/30/50% faltando | 3 de 3 | **confirmada** |
| H4 | combinações seguradas: acima do melhor chute constante e mais da metade da vantagem das vistas; 2 níveis x 4 membros | 8 de 8 | **confirmada** |

- H1: faixa 0 lower_left: rede 100.0% contra clássica 100.0% ok; faixa 0 lower_right: rede 100.0% contra clássica 99.8% ok; faixa 0 upper_left: rede 100.0% contra clássica 100.0% ok; faixa 0 upper_right: rede 100.0% contra clássica 100.0% ok; faixa 1 lower_left: rede 97.6% contra clássica 70.0% ok; faixa 1 lower_right: rede 96.2% contra clássica 68.4% ok; faixa 1 upper_left: rede 95.4% contra clássica 80.4% ok; faixa 1 upper_right: rede 89.2% contra clássica 83.0% ok
- H2: faixa 2 lower_left: rede 85.4% contra clássica 34.0% ok; faixa 2 lower_right: rede 85.2% contra clássica 33.2% ok; faixa 2 upper_left: rede 73.6% contra clássica 45.0% ok; faixa 2 upper_right: rede 70.0% contra clássica 40.0% ok; faixa 3 lower_left: rede 64.0% contra clássica 46.8% ok; faixa 3 lower_right: rede 67.4% contra clássica 49.4% ok; faixa 3 upper_left: rede 57.4% contra clássica 48.6% ok; faixa 3 upper_right: rede 50.4% contra clássica 40.4% ok
- H3 (nível 2): 10% faltando: fusão 68.6% contra formulário 56.4%, diferença +12.2 pontos (bootstrap +9.7 a +14.8) ok; 30% faltando: fusão 60.9% contra formulário 12.9%, diferença +47.9 pontos (bootstrap +45.5 a +50.3) ok; 50% faltando: fusão 56.8% contra formulário 2.0%, diferença +54.7 pontos (bootstrap +52.5 a +57.0) ok
- H3 (nível 1, só para informar): 10%: +35.4 pontos (bootstrap +33.3 a +37.5); 30%: +74.7 pontos (bootstrap +72.7 a +76.6); 50%: +93.5 pontos (bootstrap +92.4 a +94.7)
- H4: nível 1 lower_left: vistas 100.0% (acaso 28.0%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 lower_right: vistas 100.0% (acaso 26.8%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 upper_left: vistas 100.0% (acaso 33.5%), seguradas 100.0% (acaso 33.6%; limite inferior 99.2%) ok; nível 1 upper_right: vistas 100.0% (acaso 34.7%), seguradas 100.0% (acaso 16.8%; limite inferior 99.2%) ok; nível 2 lower_left: vistas 86.7% (acaso 21.7%), seguradas 86.8% (acaso 7.6%; limite inferior 83.6%) ok; nível 2 lower_right: vistas 87.3% (acaso 22.4%), seguradas 86.8% (acaso 6.6%; limite inferior 83.6%) ok; nível 2 upper_left: vistas 81.3% (acaso 27.5%), seguradas 82.6% (acaso 27.8%; limite inferior 79.0%) ok; nível 2 upper_right: vistas 77.5% (acaso 29.4%), seguradas 77.2% (acaso 22.0%; limite inferior 73.3%) ok

### Tempos desta rodada
- leitura da rede em 4000 imagens (e as espelhadas): 70 s (9 ms por leitura)
- linha de base clássica nas mesmas imagens: 0 s (em 8 processos; pode vir do cache de uma execução anterior)
- total: 75 s

## Apêndice B. Saída completa da replicação (semente 1)

É o arquivo `replication_run2.md` (fora do repositório), sem edição, com os títulos rebaixados um nível. Números com ponto decimal.

## Replicação no conjunto de teste (2026-11-23 10:48)

**Replicação, semente 1, nenhum ajuste; o teste já tinha sido aberto antes (rodada 1, semente 0). Evidência N1: desenho sintético, rótulos por construção.**
Limiar da fusão fixo em 0.5 (não reescolhido). Semente 0 = `run1`, semente 1 = `run2`.

### A. Hipóteses H1 a H4, cada semente com os mesmos critérios

#### semente 0 (`run1`)
| hipótese | o que mede | resultado | veredito |
|---|---|---|---|
| H1 | rede >= limite inferior do Wilson da clássica; nível 2, faixas 0 e 1, 4 membros | 8 de 8 comparações | **confirmada** |
| H2 | limite inferior do Wilson da rede > acerto da clássica; nível 2, faixas 2 e 3, 4 membros | 8 de 8 comparações | **confirmada** |
| H3 | classe automática da fusão contra a do formulário, nível 2, 0% de erros, 10/30/50% faltando | 3 de 3 | **confirmada** |
| H4 | combinações seguradas: acima do melhor chute constante e mais da metade da vantagem das vistas; 2 níveis x 4 membros | 8 de 8 | **confirmada** |

- H1: faixa 0 lower_left: rede 100.0% contra clássica 100.0% ok; faixa 0 lower_right: rede 100.0% contra clássica 99.8% ok; faixa 0 upper_left: rede 100.0% contra clássica 100.0% ok; faixa 0 upper_right: rede 100.0% contra clássica 100.0% ok; faixa 1 lower_left: rede 97.6% contra clássica 70.0% ok; faixa 1 lower_right: rede 96.2% contra clássica 68.4% ok; faixa 1 upper_left: rede 95.4% contra clássica 80.4% ok; faixa 1 upper_right: rede 89.2% contra clássica 83.0% ok
- H2: faixa 2 lower_left: rede 85.4% contra clássica 34.0% ok; faixa 2 lower_right: rede 85.2% contra clássica 33.2% ok; faixa 2 upper_left: rede 73.6% contra clássica 45.0% ok; faixa 2 upper_right: rede 70.0% contra clássica 40.0% ok; faixa 3 lower_left: rede 64.0% contra clássica 46.8% ok; faixa 3 lower_right: rede 67.4% contra clássica 49.4% ok; faixa 3 upper_left: rede 57.4% contra clássica 48.6% ok; faixa 3 upper_right: rede 50.4% contra clássica 40.4% ok
- H3 (nível 2): 10% faltando: fusão 68.6% contra formulário 56.4%, diferença +12.2 pontos (bootstrap +9.7 a +14.8) ok; 30% faltando: fusão 60.9% contra formulário 12.9%, diferença +47.9 pontos (bootstrap +45.5 a +50.3) ok; 50% faltando: fusão 56.8% contra formulário 2.0%, diferença +54.7 pontos (bootstrap +52.5 a +57.0) ok
- H3 (nível 1, só para informar): 10%: +35.4 pontos (bootstrap +33.3 a +37.5); 30%: +74.7 pontos (bootstrap +72.7 a +76.6); 50%: +93.5 pontos (bootstrap +92.4 a +94.7)
- H4: nível 1 lower_left: vistas 100.0% (acaso 28.0%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 lower_right: vistas 100.0% (acaso 26.8%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 upper_left: vistas 100.0% (acaso 33.5%), seguradas 100.0% (acaso 33.6%; limite inferior 99.2%) ok; nível 1 upper_right: vistas 100.0% (acaso 34.7%), seguradas 100.0% (acaso 16.8%; limite inferior 99.2%) ok; nível 2 lower_left: vistas 86.7% (acaso 21.7%), seguradas 86.8% (acaso 7.6%; limite inferior 83.6%) ok; nível 2 lower_right: vistas 87.3% (acaso 22.4%), seguradas 86.8% (acaso 6.6%; limite inferior 83.6%) ok; nível 2 upper_left: vistas 81.3% (acaso 27.5%), seguradas 82.6% (acaso 27.8%; limite inferior 79.0%) ok; nível 2 upper_right: vistas 77.5% (acaso 29.4%), seguradas 77.2% (acaso 22.0%; limite inferior 73.3%) ok

#### semente 1 (`run2`)
| hipótese | o que mede | resultado | veredito |
|---|---|---|---|
| H1 | rede >= limite inferior do Wilson da clássica; nível 2, faixas 0 e 1, 4 membros | 8 de 8 comparações | **confirmada** |
| H2 | limite inferior do Wilson da rede > acerto da clássica; nível 2, faixas 2 e 3, 4 membros | 8 de 8 comparações | **confirmada** |
| H3 | classe automática da fusão contra a do formulário, nível 2, 0% de erros, 10/30/50% faltando | 3 de 3 | **confirmada** |
| H4 | combinações seguradas: acima do melhor chute constante e mais da metade da vantagem das vistas; 2 níveis x 4 membros | 8 de 8 | **confirmada** |

- H1: faixa 0 lower_left: rede 100.0% contra clássica 100.0% ok; faixa 0 lower_right: rede 100.0% contra clássica 99.8% ok; faixa 0 upper_left: rede 100.0% contra clássica 100.0% ok; faixa 0 upper_right: rede 100.0% contra clássica 100.0% ok; faixa 1 lower_left: rede 97.4% contra clássica 70.0% ok; faixa 1 lower_right: rede 95.6% contra clássica 68.4% ok; faixa 1 upper_left: rede 95.8% contra clássica 80.4% ok; faixa 1 upper_right: rede 89.8% contra clássica 83.0% ok
- H2: faixa 2 lower_left: rede 84.6% contra clássica 34.0% ok; faixa 2 lower_right: rede 85.0% contra clássica 33.2% ok; faixa 2 upper_left: rede 75.0% contra clássica 45.0% ok; faixa 2 upper_right: rede 70.4% contra clássica 40.0% ok; faixa 3 lower_left: rede 65.2% contra clássica 46.8% ok; faixa 3 lower_right: rede 64.0% contra clássica 49.4% ok; faixa 3 upper_left: rede 57.4% contra clássica 48.6% ok; faixa 3 upper_right: rede 51.4% contra clássica 40.4% ok
- H3 (nível 2): 10% faltando: fusão 67.0% contra formulário 56.4%, diferença +10.7 pontos (bootstrap +8.0 a +13.5) ok; 30% faltando: fusão 60.6% contra formulário 12.9%, diferença +47.6 pontos (bootstrap +45.1 a +50.1) ok; 50% faltando: fusão 57.0% contra formulário 2.0%, diferença +55.0 pontos (bootstrap +52.9 a +57.3) ok
- H3 (nível 1, só para informar): 10%: +35.4 pontos (bootstrap +33.3 a +37.5); 30%: +74.7 pontos (bootstrap +72.7 a +76.6); 50%: +93.5 pontos (bootstrap +92.4 a +94.7)
- H4: nível 1 lower_left: vistas 100.0% (acaso 28.0%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 lower_right: vistas 100.0% (acaso 26.8%), seguradas 100.0% (acaso 8.4%; limite inferior 99.2%) ok; nível 1 upper_left: vistas 100.0% (acaso 33.5%), seguradas 100.0% (acaso 33.6%; limite inferior 99.2%) ok; nível 1 upper_right: vistas 100.0% (acaso 34.7%), seguradas 100.0% (acaso 16.8%; limite inferior 99.2%) ok; nível 2 lower_left: vistas 87.3% (acaso 21.7%), seguradas 85.4% (acaso 7.6%; limite inferior 82.0%) ok; nível 2 lower_right: vistas 86.4% (acaso 22.4%), seguradas 85.4% (acaso 6.6%; limite inferior 82.0%) ok; nível 2 upper_left: vistas 81.9% (acaso 27.5%), seguradas 82.6% (acaso 27.8%; limite inferior 79.0%) ok; nível 2 upper_right: vistas 78.4% (acaso 29.4%), seguradas 76.4% (acaso 22.0%; limite inferior 72.5%) ok

### B. Variação entre as sementes, por célula

Cada célula: semente 0 / semente 1 (diferença em pontos, semente 1 menos semente 0). Acerto contra o rótulo da imagem (N1).

| conjunto | lower_left | lower_right | upper_left | upper_right | wheelchair | prosthesis |
|---|---|---|---|---|---|---|
| nível 1 | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | n/a | n/a |
| faixa 0 | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) |
| faixa 1 | 97.6 / 97.4 (-0.2) | 96.2 / 95.6 (-0.6) | 95.4 / 95.8 (+0.4) | 89.2 / 89.8 (+0.6) | 100.0 / 100.0 (+0.0) | 88.0 / 86.0 (-2.0) |
| faixa 2 | 85.4 / 84.6 (-0.8) | 85.2 / 85.0 (-0.2) | 73.6 / 75.0 (+1.4) | 70.0 / 70.4 (+0.4) | 99.8 / 99.8 (+0.0) | 64.6 / 67.4 (+2.8) |
| faixa 3 | 64.0 / 65.2 (+1.2) | 67.4 / 64.0 (-3.4) | 57.4 / 57.4 (+0.0) | 50.4 / 51.4 (+1.0) | 90.2 / 91.6 (+1.4) | 52.8 / 53.2 (+0.4) |

Diferença absoluta entre as sementes, nas 28 células acima: média 0.6 pontos, máxima 3.4 pontos.

#### Consistência do espelho
| conjunto | lower_left | lower_right | upper_left | upper_right | os quatro membros juntos |
|---|---|---|---|---|---|
| nível 1 | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) |
| faixa 0 | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) | 100.0 / 100.0 (+0.0) |
| faixa 1 | 98.0 / 98.4 (+0.4) | 98.4 / 98.6 (+0.2) | 96.8 / 97.6 (+0.8) | 93.6 / 94.2 (+0.6) | 87.4 / 89.2 (+1.8) |
| faixa 2 | 90.0 / 91.8 (+1.8) | 89.2 / 88.8 (-0.4) | 79.2 / 81.2 (+2.0) | 76.8 / 79.6 (+2.8) | 50.8 / 54.0 (+3.2) |
| faixa 3 | 75.6 / 79.0 (+3.4) | 77.0 / 79.4 (+2.4) | 73.0 / 73.6 (+0.6) | 73.0 / 73.2 (+0.2) | 37.0 / 39.0 (+2.0) |

#### Fusão: classe automática correta e taxa de revisão
| nível | faltando | errados | classe automática correta (s0 / s1) | revisar (s0 / s1) | formulário (é o mesmo nas duas sementes) |
|---|---|---|---|---|---|
| nível 2 | 0% | 0% | 74.1 / 71.4 (-2.7) | 25.9 / 28.6 (+2.7) | 100.0 |
| nível 2 | 0% | 5% | 62.8 / 60.4 (-2.4) | 36.8 / 39.4 (+2.6) | 96.2 |
| nível 2 | 0% | 10% | 55.1 / 52.9 (-2.2) | 43.9 / 46.2 (+2.3) | 94.1 |
| nível 2 | 10% | 0% | 68.6 / 67.0 (-1.6) | 23.6 / 26.3 (+2.8) | 56.4 |
| nível 2 | 10% | 5% | 58.3 / 58.0 (-0.3) | 33.1 / 35.6 (+2.5) | 52.9 |
| nível 2 | 10% | 10% | 50.0 / 48.0 (-2.0) | 41.8 / 45.0 (+3.2) | 50.1 |
| nível 2 | 30% | 0% | 60.9 / 60.6 (-0.3) | 19.4 / 21.1 (+1.7) | 12.9 |
| nível 2 | 30% | 5% | 53.8 / 54.4 (+0.7) | 26.6 / 27.6 (+1.0) | 11.8 |
| nível 2 | 30% | 10% | 46.3 / 46.5 (+0.2) | 33.6 / 35.5 (+1.8) | 11.6 |
| nível 2 | 50% | 0% | 56.8 / 57.0 (+0.3) | 13.8 / 15.7 (+1.9) | 2.0 |
| nível 2 | 50% | 5% | 51.1 / 52.1 (+1.0) | 20.1 / 22.1 (+1.9) | 2.1 |
| nível 2 | 50% | 10% | 44.9 / 46.3 (+1.5) | 24.9 / 27.1 (+2.2) | 1.5 |
| nível 1 | 0% | 0% | 100.0 / 100.0 (+0.0) | 0.0 / 0.0 (+0.0) | 100.0 |
| nível 1 | 0% | 5% | 82.0 / 82.0 (+0.0) | 17.9 / 17.9 (+0.0) | 95.8 |
| nível 1 | 0% | 10% | 66.4 / 66.4 (+0.0) | 33.6 / 33.6 (+0.0) | 92.0 |
| nível 1 | 10% | 0% | 100.0 / 100.0 (+0.0) | 0.0 / 0.0 (+0.0) | 64.7 |
| nível 1 | 10% | 5% | 81.5 / 81.5 (+0.0) | 18.5 / 18.5 (+0.0) | 62.8 |
| nível 1 | 10% | 10% | 69.5 / 69.5 (+0.0) | 30.4 / 30.4 (+0.0) | 60.0 |
| nível 1 | 30% | 0% | 100.0 / 100.0 (+0.0) | 0.0 / 0.0 (+0.0) | 25.4 |
| nível 1 | 30% | 5% | 86.8 / 86.8 (+0.0) | 13.2 / 13.2 (+0.0) | 23.3 |
| nível 1 | 30% | 10% | 75.0 / 75.0 (+0.0) | 25.0 / 25.0 (+0.0) | 21.1 |
| nível 1 | 50% | 0% | 100.0 / 100.0 (+0.0) | 0.0 / 0.0 (+0.0) | 6.5 |
| nível 1 | 50% | 5% | 90.5 / 90.5 (+0.0) | 9.4 / 9.4 (+0.0) | 5.5 |
| nível 1 | 50% | 10% | 80.8 / 80.8 (+0.0) | 19.2 / 19.2 (+0.0) | 6.1 |

### C. Análise posterior ao teste (NÃO prevista antes): membro visível

**Rótulo desta seção: análise posterior ao teste.** Só as imagens em que o rótulo do membro não é `?`. Cada célula: acerto % (k/n). Compara a linha de base clássica, a rede de cada semente e o melhor chute constante entre os rótulos visíveis do treino.

| faixa (nível 2) | membro | clássica | rede, semente 0 | rede, semente 1 | melhor chute constante (visíveis) |
|---|---|---|---|---|---|
| faixa 0 | lower_left | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 23.2% (116/500; 19.7 a 27.1) |
| faixa 0 | lower_right | 99.8% (499/500; 98.9 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 23.2% (116/500; 19.7 a 27.1) |
| faixa 0 | upper_left | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 33.6% (168/500; 29.6 a 37.9) |
| faixa 0 | upper_right | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 100.0% (500/500; 99.2 a 100.0) | 32.0% (160/500; 28.1 a 36.2) |
| faixa 1 | lower_left | 75.4% (350/464; 71.3 a 79.1) | 98.3% (456/464; 96.6 a 99.1) | 98.7% (458/464; 97.2 a 99.4) | 22.6% (105/464; 19.1 a 26.7) |
| faixa 1 | lower_right | 75.5% (342/453; 71.3 a 79.2) | 98.2% (445/453; 96.6 a 99.1) | 98.0% (444/453; 96.3 a 99.0) | 23.2% (105/453; 19.5 a 27.3) |
| faixa 1 | upper_left | 84.1% (402/478; 80.6 a 87.1) | 97.7% (467/478; 95.9 a 98.7) | 98.3% (470/478; 96.7 a 99.1) | 33.9% (162/478; 29.8 a 38.2) |
| faixa 1 | upper_right | 85.4% (415/486; 82.0 a 88.3) | 90.7% (441/486; 87.8 a 93.0) | 90.9% (442/486; 88.1 a 93.2) | 32.3% (157/486; 28.3 a 36.6) |
| faixa 2 | lower_left | 40.8% (152/373; 35.9 a 45.8) | 85.0% (317/373; 81.0 a 88.3) | 85.0% (317/373; 81.0 a 88.3) | 22.5% (84/373; 18.6 a 27.0) |
| faixa 2 | lower_right | 39.9% (148/371; 35.0 a 45.0) | 84.9% (315/371; 80.9 a 88.2) | 86.8% (322/371; 83.0 a 89.9) | 22.6% (84/371; 18.7 a 27.2) |
| faixa 2 | upper_left | 49.9% (206/413; 45.1 a 54.7) | 74.8% (309/413; 70.4 a 78.8) | 77.5% (320/413; 73.2 a 81.2) | 33.9% (140/413; 29.5 a 38.6) |
| faixa 2 | upper_right | 43.8% (185/422; 39.2 a 48.6) | 70.6% (298/422; 66.1 a 74.8) | 70.6% (298/422; 66.1 a 74.8) | 33.4% (141/422; 29.1 a 38.0) |
| faixa 3 | lower_left | 6.6% (16/242; 4.1 a 10.5) | 41.3% (100/242; 35.3 a 47.6) | 45.9% (111/242; 39.7 a 52.2) | 24.0% (58/242; 19.0 a 29.7) |
| faixa 3 | lower_right | 8.9% (21/236; 5.9 a 13.2) | 45.3% (107/236; 39.1 a 51.7) | 43.6% (103/236; 37.5 a 50.0) | 27.1% (64/236; 21.8 a 33.1) |
| faixa 3 | upper_left | 10.9% (27/248; 7.6 a 15.4) | 29.8% (74/248; 24.5 a 35.8) | 37.1% (92/248; 31.3 a 43.3) | 33.1% (82/248; 27.5 a 39.1) |
| faixa 3 | upper_right | 9.3% (27/291; 6.5 a 13.2) | 26.5% (77/291; 21.7 a 31.8) | 30.2% (88/291; 25.2 a 35.7) | 32.0% (93/291; 26.9 a 37.5) |

Tempo desta análise: 68 s.
