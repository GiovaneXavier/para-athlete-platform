# Experimento imagem e laudo: relatório

**Estado:** **passo A e passo B concluídos.** Os downloads do passo A foram feitos depois do aval da equipe e conferidos por tamanho e SHA-256. **Evidência: N1 em tudo** (dado sintético nosso; a palavra "acurácia" só aparece ao lado de N1). Especificação: `docs/consistencia-imagem-laudo.md`.

**Resultado em uma frase (N1):** com estes modelos pequenos e quantizados, rodando em CPU, **nenhum extrator de imagem leu o nível do membro nem o lado** nos desenhos do nível 1 e do nível 2: o SmolVLM2 respondeu "completo" para todos os membros, o Qwen2.5-VL-7B quase sempre também, e o CLIP ficou no acaso e **não mudou de resposta com a imagem espelhada**. O extrator de laudo (Qwen2.5-1.5B) acertou 33% a 50% por membro. O pipeline completo dá "não confere" em 93% a 99,5% dos pares consistentes, ou seja, **não é melhor que o chute "sempre não confere"**. Isto é um resultado sobre **estes modelos e estes prompts**, não sobre modelos abertos em geral.

## Passo A: o nível 2 e a medida da dificuldade

### O que foi feito

`src/para_triage/consistency/level2.py` gera as **300 imagens do nível 2** (4 faixas de 75, mesma semente, sem biblioteca nova: tudo `numpy`; a compressão imita o JPEG com quantização de blocos 8x8 por DCT). Os 8 fatores da nota (aparência, pose, oclusão, iluminação, geometria, fundo, ruído e compressão, equipamento) têm intensidade de 0 a 3 por imagem, guardada com ela. Cada faixa usa **as mesmas 75 combinações de nível de membro**, então as faixas diferem na aparência e não no conteúdo. A faixa 0 não tem equipamento, oclusão nem pose nova (é o controle, parecido com o nível 1). `src/para_triage/consistency/difficulty.py` mede a dificuldade; `tests/test_consistency_level2.py` testa tudo.

**Rótulos exatos.** O rótulo de um membro é o nível verdadeiro **se a região que mostra onde o membro termina estiver visível** (no máximo 30% coberta por objeto na frente, por outro membro desenhado depois, por cadeira de corrida ou pelo corte do quadro); senão é `?`. `wheelchair` é `yes` se a cadeira aparece em pelo menos 35%, `?` se está quase toda escondida, `no` se não há. `prosthesis` é `yes` se uma prótese desenhada aparece em pelo menos 50%, `?` se está escondida, `no` se não há. A cadeira de corrida esconde as pernas (a de uso diário não), e isso é testado.

### A medida (critério escrito antes de rodar)

Critério: o acerto da **linha de base clássica** por atributo de membro (nos membros cujo rótulo é um nível, para que a queda seja de leitura e não só de membro coberto) deve cair **pelo menos 20 pontos** da faixa 0 para a faixa 3. Se não caísse, as intensidades subiriam, usando só a linha de base clássica, antes de qualquer modelo.

**Passou nas três versões do gerador.** As três tabelas abaixo são todas as rodadas que fiz; **a v3 é a congelada**.

| versão | o que mudou | faixa 0 | faixa 1 | faixa 2 | faixa 3 | queda 0 para 3 |
|---|---|---|---|---|---|---|
| v1 | primeira versão | 91,3% (274/300) | 79,9% (227/284) | 46,2% (109/236) | 9,4% (15/160) | 82,0 pontos |
| v2 | o ruído passou a ser sorteado entre 0 e o máximo da faixa, como no nível 1 (a v1 usava sempre o máximo) | 91,3% (274/300) | 79,9% (227/284) | 48,3% (114/236) | 8,1% (13/160) | 83,2 pontos |
| **v3 (congelada)** | as cores do corpo são sorteadas de novo junto com o fundo, para uma camisa branca não cair sobre fundo claro | **100,0% (300/300)** | **81,7% (232/284)** | **51,3% (122/238)** | **7,3% (12/165)** | **92,7 pontos** |

Intervalos da v3 (Wilson 95%, bootstrap por imagem 95%): faixa 0 98,7% a 100,0% (100,0% a 100,0%); faixa 1 76,8% a 85,8% (75,4% a 87,4%); faixa 2 44,9% a 57,5% (43,9% a 59,4%); faixa 3 4,2% a 12,3% (1,9% a 13,5%). Membros com rótulo `?` por faixa: 0, 16, 62 e 135 (de 300 cada). Contando `?` como um valor que o leitor teria de dar: 100,0%, 77,3%, 43,0% e 44,3%.

**Decisão sobre as intensidades: ficam como na v3 e estão congeladas** (`level2.TABLE`, `TABLE_VERSION = "2026-11-05.v3"`). O critério passou já na v1, então **nenhuma intensidade foi aumentada**. As mudanças v2 e v3 foram **consertos de defeito do gerador** que mostrei com a linha de base clássica (a faixa 0 devia ser parecida com o nível 1 e ficava 8 pontos abaixo; a causa era uma camisa branca sobre fundo claro, que não se via). **Nenhum modelo de aprendizado profundo rodou**, então nada foi ajustado a modelo. Daqui em diante os resultados dos modelos **não** mudam o gerador.

### O que a medida mostra e o que não mostra

- **A curva desce em todas as faixas** e a faixa 0 (controle) volta a ficar igual ao nível 1 (100%). O nível 2 **não é o boneco limpo**.
- **A faixa 3 fica abaixo do acaso** (7,3%; chutar um nível entre 3 ou 4 daria 25% a 33%): a linha de base clássica **é enganada sempre no mesmo sentido** (lê membros mais longos, por causa de fundo confuso, próteses e objetos), não erra ao acaso. Não é um resultado sobre modelos de aprendizado.
- **Na faixa 3, 45% dos membros viram `?`** (135 de 300): ela testa pouco a leitura do nível e muito a resposta "não sei". O relatório do passo B vai separar os dois.
- **Por fator** (bandas 1 a 3 juntas; acerto da linha de base clássica nos membros com nível conhecido, por intensidade 0, 1, 2 e 3 do fator): aparência 75% / 77% / 37% / 7%; pose 93% / 63% / 37% / 5%; oclusão 80% / 78% / 33% / 3%; iluminação 88% / 64% / 45% / 7%; geometria 80% / 74% / 37% / 5%; fundo 78% / 74% / 34% / 2%; ruído 80% / 70% / 36% / 8%; equipamento 85% / 69% / 38% / 8%. **Estes números NÃO isolam fatores**: cada imagem leva os oito fatores juntos (cada um na faixa ou um abaixo), então os fatores andam juntos. Servem para ver que **todos** acompanham a dificuldade, não para dizer qual pesa mais.
- **Não prova** que o nível 2 é difícil como uma foto, nem para um modelo de aprendizado profundo; prova só que **não é o boneco limpo** (seção 9 da nota).

## Passo A: a seção 6.4, os downloads para o aval da equipe

**Nada foi baixado.** Tamanhos, hashes SHA-256 e licenças abaixo foram lidos em 05/11/2026 nas **páginas e APIs públicas** (API de modelos do Hugging Face, API de releases do GitHub, API do PyPI), sem baixar nenhum arquivo. Nenhum item exige conta nem aceite de termos (`gated: False` nos quatro repositórios). Cada linha é **um download**; o aval é pedido **download por download**.

| # | Item | Para que serve | Fonte (endereço) | Versão ou hash | Tamanho exato | Licença |
|---|---|---|---|---|---|---|
| 1 | llama.cpp, binário de Windows, CPU | servir os modelos GGUF pelo HTTP local, com saída restrita ao esquema | `https://github.com/ggml-org/llama.cpp/releases/download/b12125/llama-b12125-bin-win-cpu-x64.zip` | release `b12125` (de 05/11/2026); sha256 `968091ccb8c230e0cf7e0eed386310703bebae4a4fd4375f0c57db53958307d8` | 24.730.921 bytes (24,7 MB) | MIT |
| 2 | SmolVLM2-2.2B-Instruct, `SmolVLM2-2.2B-Instruct-Q4_K_M.gguf` | extrator de imagem principal (rápido) | `https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF` | commit `1bc3c9f74ceafd4c8d4411cc9cf188bba3798f91`; sha256 `0cf76814555b8665149075b74ab6b5c1d428ea1d3d01c1918c12012e8d7c9f58` | 1.112.602.656 bytes (1.112,6 MB) | Apache-2.0 |
| 3 | SmolVLM2-2.2B-Instruct, `mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf` | projetor de visão do item 2 (obrigatório com ele) | mesmo repositório e commit | sha256 `ae07ea1facd07dd3230c4483b63e8cda96c6944ad2481f33d531f79e892dd024` | 592.523.200 bytes (592,5 MB) | Apache-2.0 |
| 4 | Qwen2.5-VL-7B-Instruct, `Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf` | extrator de imagem forte (só em subconjuntos) | `https://huggingface.co/ggml-org/Qwen2.5-VL-7B-Instruct-GGUF` | commit `508edd0afaa66bb9e9f40587acc2184f02daf1f6`; sha256 `9258bf05b12686d097ff3b6b18d968ab393649780aa2b3cd67fec43d50554392` | 4.683.072.032 bytes (4.683,1 MB) | Apache-2.0 |
| 5 | Qwen2.5-VL-7B-Instruct, `mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf` | projetor de visão do item 4 | mesmo repositório e commit | sha256 `2ddb555391bae966e412deab9e07b58afa18bcc06930ba0f1c78a3695ab9e506` | 853.119.712 bytes (853,1 MB) | Apache-2.0 |
| 6 | Qwen2.5-1.5B-Instruct, `qwen2.5-1.5b-instruct-q4_k_m.gguf` | extrator de laudo (texto) | `https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF` | commit `91cad51170dc346986eccefdc2dd33a9da36ead9`; sha256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` | 1.117.320.736 bytes (1.117,3 MB) | Apache-2.0 |
| 7 | OpenCLIP LAION ViT-B/32, `open_clip_model.safetensors` | linha de base CLIP zero-shot | `https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K` | commit `1a25a446712ba5ee05982a381eed697ef9b435cf`; sha256 `ac4f8c4b88af6d963118cbf40ad93176d092abbedfcb752601ae1866352656e6` | 605.143.316 bytes (605,1 MB) | MIT |
| 8 | Pacotes Python de um **ambiente virtual novo, fora do repositório** (nunca `<ambiente do projeto>`): `torch` (CPU), `open_clip_torch`, `numpy`, `pillow`, `httpx` e as dependências deles | rodar o CLIP e conversar com o servidor local | PyPI (`https://pypi.org`), versões fixadas num `requirements.txt` próprio em `spikes/imagem_laudo/` | versões atuais de hoje: `torch 2.15.0` (wheel de 126,7 MB, cp312 win_amd64), `open_clip_torch 3.3.0`, `pillow 13.0.0`, `numpy 2.5.4`, `httpx 0.28.1` | **cerca de 0,3 GB no total (estimativa)**; o pip resolve o número exato | Apache-2.0 (`torch`, conforme o PyPI), MIT (`open_clip_torch`), MIT-CMU (`pillow`), BSD-3-Clause (`numpy` e `httpx`) |

**Espaço total em disco:** os itens 1 a 7 somam **8.988.512.573 bytes (8,99 GB, 8,37 GiB)**; com o item 8 (estimado), **cerca de 9,3 GB**; o zip do item 1 descompactado ocupa um pouco mais que os 24,7 MB. Há **221,7 GB livres** no disco C:. Os pesos e o ambiente ficam **fora do repositório** (pasta de trabalho local, no `.gitignore`).

**Fora desta lista, de propósito:** as 30 fotos do nível 3 (cerca de 184 MB) **não** entram até a equipe aprovar o manifesto e rever as fotos em tamanho original; Qwen2.5-VL-3B (licença de pesquisa, inconsistente entre as páginas); Gemma, PaliGemma, Phi-3.5-vision, Moondream2, InternVL3 e Florence-2 (seção 6.3 da nota).

## Passo B: os modelos rodaram

Código em `spikes/imagem_laudo/` (só `.py`, `.md` e `.txt`; nenhum peso, binário, imagem ou resultado entra no repositório; o teste de isolamento confere). Ambiente virtual novo **fora** do repositório (`<venv-imagem-laudo>`, 813 MB; o `para-triage` não foi tocado); pesos e resultados em `<pasta IMAGEM_LAUDO_MODELOS>` (8,5 GB), fora do repositório. `pyproject.toml` não mudou.

### Downloads e o que roda

Os oito itens da tabela do passo A foram baixados **depois do aval da equipe, item a item**, e **os sete arquivos conferem em tamanho e SHA-256** com a tabela. O **llama.cpp `b12125` roda** SmolVLM2-2.2B, Qwen2.5-VL-7B (os dois com imagem) e Qwen2.5-1.5B (texto), **com saída restrita por esquema JSON**, nesta máquina (Core Ultra 5 125H, 15,6 GB de RAM, só CPU), ligado só em `127.0.0.1`. Não foi preciso parar e perguntar por causa de ferramenta. O CLIP roda em `torch` na CPU com o arquivo local (`HF_HUB_OFFLINE=1`).

### Tempo e memória medidos (rodadas finais)

| extrator | tempo por pedido (mediana; mín a máx) | pico de RAM do servidor | falhas |
|---|---|---|---|
| SmolVLM2-2.2B, imagem 280x400 | **22,5 s** (20,6 a 26,3 s no nível 1; 20,8 a 33,1 s no nível 2) | 3,1 GB | 0 de 294 pedidos |
| Qwen2.5-VL-7B, imagem | **49,8 s** (47,6 a 60,3 s) no nível 1; **49,7 s** no nível 2 | 6,8 GB (nível 1) e 7,5 GB (nível 2) | 0 de 44 |
| Qwen2.5-1.5B, laudo (com cache do prefixo) | **4,9 s** (3,3 a 9,6 s) no nível 1; **6,6 s** no nível 2 (média 6,1 s) | 1,8 GB | 0 no nível 1; **1 no nível 2** (lida como tudo `?`) |
| CLIP ViT-B/32, uma imagem | **0,11 s** | cabe no processo Python | 0 |

Um par imagem e laudo custa então cerca de **28 s** com o SmolVLM2 e **55 s** com o Qwen2.5-VL-7B. Contra a estimativa da seção 6.3 da nota: o SmolVLM2 ficou **acima** (estimado 8 a 20 s, medido 22,5 s, porque o prompt v2 pede uma frase livre antes das respostas), o Qwen 7B dentro (30 a 70 s), o texto dentro (2 a 8 s) e o CLIP **abaixo** (0,15 a 0,4 s estimado, 0,11 s medido). **Ressalvas honestas:** na primeira rodada (descartada, abaixo) o pico de RAM do SmolVLM2 apareceu como 7,5 a 8,2 GB, contra 3,1 GB nas rodadas limpas, e um pedido ficou parado 4.251 s quando o computador entrou em repouso. O usuário usa o PC ao mesmo tempo, então são tempos de uma **máquina compartilhada**, medidos uma vez, não repetidos.

### Como a avaliação foi montada

- **Subconjuntos sorteados com semente antes de ver resultado** (`subsets.py`): nível 1, 32 combinações de nível de membro (96 imagens, `eval`) e outras 8 (24 imagens, `dev`), disjuntas; nível 2, 100 imagens `eval` (25 por faixa) e 12 `dev`. O `dev` só serve para olhar o comportamento do prompt; **os números são do `eval`**.
- **Erro na primeira rodada:** usei uma imagem a cada 3 das 144 combinações, e como o último fator (`upper_right`, 3 valores) varia mais depressa, ele ficou **fixo em 0** no subconjunto. Descobri pelo acerto de 100% em `upper_right`, que era artefato. Refiz com sorteio e o `python subsets.py` passou a imprimir as contagens de cada fator. Os resultados dessa primeira rodada ficaram arquivados na pasta local de resultados (`v1`) e **não entram nas tabelas abaixo**.
- **Prompts.** v1 (primeira rodada, descartada): o SmolVLM2 respondeu "tudo 0" em 491 de 494 leituras, o Qwen 7B respondeu `?` e o extrator de laudo respondeu `?` quase sempre. v2 (imagem com campo livre `look` antes das respostas; laudo com dois exemplos escritos à mão) e v3 (imagem pedindo para comparar os dois braços e as duas pernas; laudo como lista de frases "qual membro, qual nível"). **No máximo três tentativas no `dev`; a terceira foi a última.** Decisão: imagens com o v2, laudos com o v3. No `dev`, **ambos os modelos de imagem disseram "membros completos"** em todas as figuras, mesmo pedindo para comparar. O Qwen 7B enxerga cores, mas diz que os comprimentos dos membros diferem "um pouco"; trato como **limite de capacidade e de resolução do modelo**, não de envio da imagem (a imagem chega: ele descreve a cor da camisa).
- Teste do espelho: cada imagem com exatamente um lado amputado é lida também espelhada (rótulo com os lados trocados). Se a leitura **não muda** com o espelho, o extrator **não sabe o lado**; se muda para o lado errado, é viés.
- Comparação: **linha de base clássica** (seção anterior; nível 1 99,8%; nível 2 por faixa 100,0% / 81,7% / 51,3% / 7,3%) e o **piso do veredito** ("sempre não confere").

### CLIP zero-shot (OpenCLIP ViT-B/32 LAION-2B; todas as 432 imagens do nível 1 e as 300 do nível 2; N1)

| teste | nível 1 | nível 2 |
|---|---|---|
| lado, pernas (imagens com exatamente um lado amputado) | 50,0% (81/162; 42,4 a 57,6) no original; 50,0% no espelhado; **mesma resposta nos dois 162/162**; escolheu a frase da esquerda 0/162 | 54,5% (42/77; 43,5 a 65,2) no original; 46,8% (36/77) no espelhado; mesma resposta 76/77 |
| lado, braços | 50,0% (96/192; 43,0 a 57,0); espelhado 50,5%; mesma resposta 191/192; esquerda 2/192 | 55,4% (51/92; 45,3 a 65,2); espelhado 45,7%; mesma resposta 89/92 |
| nível do membro (pior dos dois, 4 ou 3 frases) | 6,9% pernas, 11,1% braços | 13,2% a 15,9% |
| cadeira de rodas | n/a | 89,9% (266/296; 85,9 a 92,8) |
| prótese | n/a | 72,5% (206/284; 67,1 a 77,4) |

**Leitura:** o CLIP **não sabe esquerda de direita** (a resposta é a mesma na imagem e no espelho em quase todos os casos, e ele escolhe quase sempre a frase da direita) e **não lê o nível** (abaixo do acaso de 25% a 33%). Só acerta algo em cadeira de rodas (89,9%, contra 80,8% de quem sempre dissesse "não"). Confirma a expectativa escrita antes da rodada: acaso nos lados. (Estas rodadas do CLIP são da primeira rodada, mas o CLIP não usa prompt longo nem subconjunto: rodou as imagens inteiras, então valem como estão.)

### Extratores de imagem (subconjunto `eval`, prompt v2; acerto contra o rótulo, Wilson 95%; N1)

| atributo | SmolVLM2 nível 1 (96) | SmolVLM2 nível 2 (100) | Qwen2.5-VL-7B nível 1 (24) | Qwen2.5-VL-7B nível 2 (20, só faixa 0) |
|---|---|---|---|---|
| lower_left | 18,8% (12,2 a 27,7) | 26,6% (21/79) | 58,3% (14/24) | 15,0% (3/20) |
| lower_right | 25,0% (17,4 a 34,5) | 25,6% (20/78) | 50,0% (12/24) | 25,0% (5/20) |
| upper_left | 37,5% (28,5 a 47,5) | 39,0% (32/82) | 37,5% (9/24) | 35,0% (7/20) |
| upper_right | 25,0% (17,4 a 34,5) | 31,0% (27/87) | 25,0% (6/24) | 35,0% (7/20) |
| wheelchair | n/a | 82,8% (82/99) | n/a | 100% (20/20) |
| prosthesis | n/a | 67,4% (62/92) | n/a | 90,0% (18/20) |

**Estes números NÃO mostram leitura.** O SmolVLM2 respondeu **"0" (completo) em todas as 96 imagens e para todos os quatro membros no nível 1**, e "não" para cadeira e prótese em todas; o acerto dele é a **proporção de membros completos no subconjunto** (por exemplo, 18 de 96 em `lower_left`), não habilidade. No nível 2 ele deu 0 em 93 de 100 imagens, `?` em 6 e outro valor em 1; o acerto de cadeira (82,8%) e de prótese (67,4%) é **o mesmo que sempre responder "não"** (80,8% e 69,6%). O Qwen 7B respondeu 0 em 20 a 23 de 24 imagens do nível 1 e deu 2 em poucas pernas; ficou **igual ou abaixo de "sempre 0"** nos subconjuntos dele (por exemplo, `lower_left` 58% contra 75% de "sempre 0"). **No teste do espelho, o SmolVLM2 acertou o lado em 0 de 33 e 0 de 39 imagens no nível 1 (0 de 34 e 0 de 35 no nível 2), e deu a mesma leitura na imagem e no espelho em todas** (sempre "completo", então não há lado a trocar). **Ressalva do Qwen 7B:** só rodou **24 imagens no nível 1 e 20 no nível 2 (as 20 primeiras, todas da faixa 0, sem cadeira e sem prótese)**, por causa do tempo (cerca de 50 s por pedido); os 100% de cadeira de rodas dele são triviais (o rótulo é "não" nas 20), e os intervalos são largos. Nenhuma faixa mais difícil foi testada nele.

### Extrator de laudo (Qwen2.5-1.5B, prompt v3; todos os laudos do `eval`; acerto contra o rótulo do laudo, `?` incluído; N1)

| atributo | nível 1 (669 laudos) | nível 2 (689 laudos) |
|---|---|---|
| lower_left | 39,3% (35,7 a 43,1) | 33,1% (29,7 a 36,7) |
| lower_right | 42,2% (38,5 a 45,9) | 32,5% (29,1 a 36,1) |
| upper_left | 43,5% (39,8 a 47,3) | 43,7% (40,0 a 47,4) |
| upper_right | 49,6% (45,9 a 53,4) | 49,3% (45,6 a 53,1) |
| wheelchair | 100% (rótulo sempre `?`; não prova nada) | **18,3%** (15,6 a 21,3) |
| prosthesis | 97,0% (649/669; quase tudo `?`) | **41,9%** (38,3 a 45,7) |

**Achado sobre cadeira e prótese no laudo (nível 2):** o modelo quase **nunca responde "não"**. Nas frases do tipo "Não usa cadeira de rodas" o rótulo é `no` em 548 laudos e o modelo leu `no` em **1**, e `?` em 547. Ele lê bem o "sim" (107 de 123 com rótulo `yes`). A causa provável é o meu prompt (diz "yes ou no só se o laudo disser" e não traz exemplo com negação). Os 100% e 100% que vi no `dev` eram do **nível 1, onde o rótulo é sempre `?`**: não provavam nada, e só a rodada final mostrou o problema. **Não ajustei o prompt de novo**, porque as três tentativas já tinham sido usadas; ajustar agora com o `eval` à vista seria afinar no conjunto de teste. A correção foi feita na rodada seguinte (v4, seção abaixo).

O texto dos laudos tem erros de digitação plantados (ruído) e frases de várias formas; mesmo assim 33% a 50% por membro fica **bem abaixo** do que um leitor de regras faria. Um modelo de 1,5 B com quantização Q4 é pequeno.

### Correção do prompt do laudo (v4, rodada posterior; Qwen2.5-1.5B; N1)

**O que mudou.** Só a regra de cadeira de rodas e prótese e o exemplo: "yes" se o laudo diz que usa (usa, faz uso de), "no" se diz que não usa (não usa, sem uso de, sem prótese), `?` só se o laudo não diz nada; o exemplo ganhou "Não usa cadeira de rodas. Faz uso de prótese.". As regras de membro são as da v3 (`spikes/imagem_laudo/prompts.py`, `PROMPTS["v4"]`, só o laudo). Primeiro no `dev` do nível 2 (82 laudos, uma tentativa), depois nos laudos inteiros do `eval`.

**Ressalva de método.** A v4 foi escrita **depois** de termos visto os números do `eval` com a v3. Portanto os números da v4 no `eval` mostram que a **correção funciona**, mas **não são um teste limpo** de um prompt escolhido às cegas; o `dev` (82 laudos) foi olhado antes, sem ter sido a origem do defeito.

| atributo | nível 2, v3 (689 laudos) | nível 2, v4 (689 laudos) | nível 1, v3 (669) | nível 1, v4 (669) |
|---|---|---|---|---|
| wheelchair | 18,3% (15,6 a 21,3) | **95,9%** (661/689; 94,2 a 97,2) | 100% | **62,6%** (419/669; 58,9 a 66,2) |
| prosthesis | 41,9% (38,3 a 45,7) | **76,5%** (527/689; 73,2 a 79,5) | 97,0% | **4,3%** (29/669; 3,0 a 6,2) |
| lower_left | 33,1% | 37,7% (260/689; 34,2 a 41,4) | 39,3% | 41,4% (277/669) |
| lower_right | 32,5% | 34,1% (235/689; 30,7 a 37,7) | 42,2% | 40,5% (271/669) |
| upper_left | 43,7% | 45,0% (310/689; 41,3 a 48,7) | 43,5% | 45,0% (301/669) |
| upper_right | 49,3% | 48,8% (336/689; 45,1 a 52,5) | 49,6% | 54,0% (361/669) |

No `dev`, a v4 deu wheelchair 96,3% (79/82) e prosthesis 76,8% (63/82).

**Leitura.**
- **No nível 2 a negação foi corrigida**: cadeira de rodas foi de 18,3% a 95,9%, prótese de 41,9% a 76,5%. Os membros ficaram onde estavam (as diferenças ficam dentro dos intervalos).
- **No nível 1 a v4 piorou, e o motivo é o mesmo ao contrário.** Lá o laudo **não fala** de cadeira nem de prótese e o rótulo é `?`; a v4 passou a responder "yes" ou "no" em quase todos (prótese: só 29 de 669 respostas `?`). A v3 acertava essas porque respondia `?` para tudo, **o que era o defeito do outro lado**. Nenhum prompt desta família resolveu os dois casos (negação dita e silêncio); um terceiro tipo de exemplo ("o laudo não diz nada: `?`") não foi tentado.
- **Prótese ficou em 76,5%, não perto de 100%**: o acerto do erro restante não foi examinado caso a caso; não sei se é "sem prótese" lido como "yes", ou `?` não emitido.
- O **pipeline completo** quase não mudou: falso alarme 97,9% (188/192) no nível 1 e 97,5% (195/200) no nível 2 (antes 99,5% e 93,0%); taxa de aviso correto em todos os erros plantados 79,5% e 74,6% (antes 79,5% e 73,1%); "não sei" 1,5% e 1,9%. Continua **no nível do chute "sempre não confere"**, porque o gargalo é a leitura dos membros (o SmolVLM2 responde "completo" quase sempre), não a cadeira e a prótese.

### O pipeline completo (SmolVLM2 lê a imagem, Qwen2.5-1.5B lê o laudo, o comparador decide; subconjunto `eval`; N1)

| | nível 1 (96 imagens, 661 pares) | nível 2 (100 imagens, 680 pares) |
|---|---|---|
| "não confere" nos pares consistentes e com ruído (falso alarme) | **99,5%** (191/192; Wilson 97,1 a 99,9) | **93,0%** (186/200; 88,6 a 95,8) |
| "não sei" | 0,3% (2/661) | 6,2% (42/680) |
| piso: sempre "não confere" | 56,4% (373/661; 52,6 a 60,2) | 52,8% (359/680; 49,0 a 56,5) |
| taxa de aviso correto em todos os erros plantados | 79,5% (75,6 a 82,9) | 73,1% (69,0 a 76,9) |
| `a_side_swap` / `b_level` / `c_region` / `e_other_person` | 100% / 100% / 100% / 97,9% | 80,2% / 94,9% / 94,6% / 90,0% |
| `d_omission` (o esperado é "não sei") | 2,1% | 8,1% |

**Como ler.** As taxas altas de aviso correto são **enganosas**: o pipeline diz "não confere" quase sempre, e então acerta todo erro plantado de graça e erra quase todo par consistente. A linha que importa é o falso alarme (99,5% e 93,0%); com ela, o pipeline **não passa do chute "sempre não confere"**. Na omissão, o esperado era "não sei", e o pipeline deu "não confere" em 94 de 96 pares no nível 1 (a matriz de confusão mostra o mesmo: 191 de 192 pares que deviam dar "confere" deram "não confere"). O comparador está correto (testes unitários e a linha de base clássica, 99,8% no nível 1); **o defeito está nas leituras**: no nível 1, a maior parte dos vereditos errados vem de imagem e laudo juntos (266 de 287).

### O que isto significa (e o que não)

- **Para o objetivo do experimento imagem e laudo (conferir imagem e laudo com modelos abertos locais):** com **esta classe de modelo** (VLM de 2 a 7 B quantizado em Q4, CPU, 280x400) e **estes prompts**, a leitura da imagem **não** funciona; o pipeline fica no nível do acaso. A linha de base clássica do nível 1 (99,8%) mostra que o desenho permite ler o nível, só que **um modelo de visão genérico não o lê**.
- **Não significa** que nenhum modelo aberto serve: não testei modelos maiores, nem float16, nem GPU, nem ajuste fino (a seção 6.3 da nota deixou isso fora de propósito). O limite que vi parece de **capacidade e de resolução** (o Qwen vê cores e diz que os braços diferem "um pouco").
- **Não é sobre fotografia.** Tudo é N1: desenho sintético, rótulos nossos. O nível 3 (30 fotos) segue **fora** até a equipe aprovar o manifesto e rever as fotos.
- O extrator de laudo **melhorou na negação** com a v4 (nível 2), mas **piorou no silêncio** (nível 1); com um modelo maior, ou com exemplo dos dois casos, **não** foi tentado.

## O que NÃO foi verificado

1. **Que os resultados valem para outros modelos.** Só testei SmolVLM2-2.2B Q4_K_M, Qwen2.5-VL-7B Q4_K_M e Qwen2.5-1.5B Q4_K_M. Modelos maiores, outras quantizações e GPU **não foram testados**.
2. **O Qwen2.5-VL-7B ficou com amostra muito pequena** (24 imagens no nível 1; 20 no nível 2, todas da faixa 0). Os intervalos são largos e **não há leitura dele nas faixas 1 a 3**.
3. **Prompts.** Foram três versões e, no máximo, três tentativas no `dev`. Um prompt diferente, ou a imagem em maior resolução, poderia render mais; **não foi tentado** (e afinar com o `eval` à vista seria enganar a medida). O prompt do laudo tinha um defeito que vi só na rodada final (negação lida como `?`); a **v4 o corrigiu no nível 2**, mas foi escrita **com o `eval` à vista** (não é teste limpo) e **piorou o nível 1** (silêncio do laudo lido como sim ou não).
4. **Os tempos** são de um PC compartilhado com outras tarefas, medidos uma vez, sem repetição em máquina ociosa.
5. **O nível 3** (fotos reais) **não rodou**: segue fora até o aval da equipe ao manifesto e a revisão das fotos em tamanho original.
6. **A licença de cada peso além do que a página do repositório declara**, o conjunto de treino do OpenCLIP (LAION-2B) e o **binário do llama.cpp** (nem antivírus, nem assinatura; só o SHA-256 do release) **não foram avaliados**.
7. **O teste do espelho** usa só imagens com exatamente um lado amputado; os outros casos não dizem nada sobre o lado.
8. **A primeira rodada** (subconjunto com `upper_right` fixo, prompts v1) está arquivada fora do repositório e **não entra nas tabelas**.
