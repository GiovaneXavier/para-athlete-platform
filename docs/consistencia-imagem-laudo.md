# Experimento imagem e laudo: conferência entre uma imagem e um laudo (nota de desenho)

**Nível de evidência de tudo o que este documento prevê medir: N1.** Os níveis 1 e 2 usam dado sintético; o nível 3 usa rótulos **nossos** sobre fotos, não rótulos de classificador. Nenhum número destes experimentos é validade clínica, e a palavra "acurácia" só aparece aqui ao lado do aviso **N1**.

## 0. Resumo em dez linhas

1. **O que é:** um protótipo de pesquisa. Dados **uma imagem** e **um laudo em texto**, um **modelo aberto rodando local** lê cada um **separadamente** e devolve os mesmos atributos estruturados; **código determinístico** compara e emite **"confere", "não confere" ou "não sei"**, sempre como **aviso para revisão humana**.
2. **O que não é:** decisão de elegibilidade, rejeição, inferência de saúde ou de classe, reconhecimento facial, ferramenta de produção.
3. **Esquema fechado:** o nível de cada um dos quatro membros (os mesmos valores do perfil) e, nos níveis 2 e 3, "há cadeira de rodas" e "há prótese". Nada mais.
4. **Três níveis:** (1) boneco desenhado por nós; (2) imagens sintéticas **nossas**, com variação de pose, oclusão e ruído; (3) 30 a 50 fotos Creative Commons do Wikimedia Commons de **um só atleta**, **só em manifesto**.
5. **Seis erros plantados** (lado trocado, nível errado, região errada, laudo sem a informação, laudo de outra pessoa, ruído sem erro de fato), medidos por nível.
6. **Três linhas de base** obrigatórias: clássica (no boneco), CLIP zero-shot e chute.
7. **Modelos candidatos** (licença e tamanho conferidos nas páginas dos modelos, hoje): SmolVLM2-2.2B e Qwen2.5-VL-7B (Apache-2.0) para a imagem; Qwen2.5-1.5B-Instruct (Apache-2.0) para o texto; OpenCLIP LAION ViT-B/32 (MIT) como linha de base. A máquina tem **CPU de 14 núcleos, 15,6 GB de RAM e nenhuma GPU dedicada**: o tempo por imagem é de **segundos a dezenas de segundos** (estimativa, não medida).
8. **Manifesto candidato do nível 3:** **30 fotos de um só atleta, de 11 fotógrafos (nenhum com mais de 23%)**, licença conferida arquivo a arquivo, `docs/consistencia-imagem-laudo-manifesto-nivel3.csv`. **Os rótulos por lado e por nível ainda não existem:** só rótulos grossos, a partir de miniaturas; **as fotos de cadeira de corrida só servem para o atributo `wheelchair`**; **ainda não há foto confirmada com diferença de membro superior** (seção 4.3).
9. **Nível 2:** WheelPose (código MIT, mas precisa do Unity, e o conjunto de fotos dele sai de vídeos do YouTube) e a biblioteca da Ottobock (acesso fechado: a licença só se lê depois de aceitar termos numa conta) **não passam** na conferência. **Decidido: um nível 2 feito por nós**, com aparência aleatória e variação de pose, oclusão e ruído, e a dificuldade **medida** pela queda da linha de base clássica (seção 4.2).
10. **As quatro decisões estão registradas na seção 11.1.** **Nada foi baixado e nada será baixado sem o aval da equipe** (a lista, com nome, fonte e tamanho, está na seção 6.4).

## 1. Objetivo e limites

**Limites que valem em tudo:**

| Limite | Como o desenho o cumpre |
|---|---|
| O resultado é um aviso para revisão humana | Os três textos de saída pedem revisão; não há estado "rejeitado" nem "inelegível" (seção 3.3) |
| Nada de inferir saúde, classe ou elegibilidade pela imagem | O esquema só tem o que é **visível**; o modelo não recebe classe, diagnóstico nem pergunta de saúde; o laudo sintético só diz o que está nos rótulos visíveis |
| Nenhum reconhecimento facial | O modelo não é perguntado sobre pessoa; não há recorte de rosto guardado; os resultados usam só o identificador `K34-L3-nnn`, **nunca o nome** |
| Modelo local, nada sai da máquina | Runtime local (seção 6.2); sem API externa, sem Colab, sem telemetria |
| Imagens do nível 3 fora do repositório | Só o manifesto (CSV) entra; as fotos ficam numa pasta fora do repositório, com `.gitignore` |
| Não usar imagem da LEXI | Nenhuma imagem, nem como modelo de desenho: o boneco é desenhado por nós, de zero |
| Sem texto da cartilha do CPB | Os laudos sintéticos são escritos por nós, sem trecho da cartilha |

## 2. O esquema fechado de atributos

Os valores de nível são **os do perfil** (`src/para_triage/rules/schema.py`), para que o experimento imagem e laudo possa, no futuro, alimentar o mesmo formulário sem tradução.

| Atributo | Valores permitidos | Níveis do experimento imagem e laudo |
|---|---|---|
| `lower_left`, `lower_right` (membro inferior, lado **da pessoa**) | `0` nenhum · `1` parte do pé · `2` abaixo do joelho · `3` na altura do joelho ou acima · `?` não sei | 1, 2, 3 |
| `upper_left`, `upper_right` (membro superior, lado **da pessoa**) | `0` nenhum · `1` no punho ou abaixo do cotovelo · `2` no cotovelo ou acima · `?` não sei | 1, 2, 3 |
| `wheelchair` | `yes` · `no` · `?` | 2, 3 |
| `prosthesis` | `yes` · `no` · `?` | 2, 3 |

**Convenções que precisam estar escritas, porque são a fonte clássica de erro:**

- **Esquerda e direita são da pessoa, não de quem olha.** Numa figura de frente, a esquerda da pessoa aparece à **direita** da imagem. O prompt do extrator de imagem diz isto, e o gerador do boneco o respeita (e testa).
- **"Nenhum" é uma afirmação** (o membro aparece completo); **`?` é "não dá para saber"** (o membro está escondido, cortado, longe ou coberto). Um corredor numa cadeira de corrida tem as pernas **escondidas**: os níveis inferiores são `?`, **não** `3`.
- **O nível de uma foto só vale quando se vê onde o membro termina.** Prótese à vista não diz por si só o nível; se não se vê o joelho, o nível é `?` e `prosthesis` é `yes`.
- **Só a região "inferior" e a "superior" existem:** nada de dedos, quadril ou tronco.

## 3. Como funciona

### 3.1 As três peças

```
imagem ──► extrator de imagem ──► atributos da imagem ─┐
                                                       ├─► comparador (código) ──► confere / não confere / não sei
laudo  ──► extrator de laudo  ──► atributos do laudo  ─┘                              + os campos que divergem
```

**Não se pergunta ao modelo "bate?".** A separação é o que permite medir **onde** o erro está: na **percepção** da imagem, na **leitura** do laudo, ou na **comparação** (esta última é código, é testada com extratores falsos e tem de ser exata).

- **Extrator de imagem:** um modelo de visão e linguagem aberto e local. Recebe a imagem e as instruções do esquema; devolve **JSON** nos valores permitidos. A saída é **restrita por gramática** ao esquema (o runtime proposto na seção 6.2 faz isso), então não há JSON inválido nem valor fora do domínio; o que se mede é a **correção**, não a validade.
- **Extrator de laudo:** um modelo de texto aberto e local (ou o mesmo modelo, só com texto), com o mesmo esquema.
- **Comparador:** função pura, sem modelo.

### 3.2 O comparador

Para cada atributo `a`, com valor da imagem `i` e valor do laudo `l`:

| `i` | `l` | Resultado de `a` |
|---|---|---|
| conhecido | conhecido e **igual** | **ok** |
| conhecido | conhecido e **diferente** | **divergência** |
| conhecido | `?` | **lacuna** (o laudo é omisso sobre algo que a imagem mostra) |
| `?` | conhecido | **lacuna** (o laudo afirma algo que a imagem não permite conferir) |
| `?` | `?` | **ignorado** (nada a dizer) |

**Resultado geral:** qualquer **divergência** → **"não confere"**, listando os campos; senão, qualquer **lacuna** → **"não sei"**, listando os campos; senão, ao menos um **ok** → **"confere"**; senão (tudo `?`) → **"não sei"**.

Propriedades que viram teste: o resultado é **determinístico**; **uma divergência domina** qualquer número de lacunas e de oks; trocar imagem e laudo dá o mesmo resultado (simetria); acrescentar um atributo `?` nos dois lados não muda nada.

### 3.3 O que o usuário lê

Os três textos de saída, em português, **sempre com a ressalva da revisão humana**:

- **"Confere"**: "A imagem e o laudo concordam nos campos conferidos. Isto não substitui a revisão."
- **"Não confere"**: "A imagem e o laudo divergem em: [campos]. Peça revisão humana."
- **"Não sei"**: "Não foi possível conferir: [campos]. Peça revisão humana."

Nenhum texto fala em "elegível", "rejeitado" ou em classe.

## 4. Os três níveis

### 4.1 Nível 1: o boneco desenhado por nós

- **Imagem:** um boneco (tronco, cabeça, braços e pernas em segmentos) gerado **por código** a partir dos quatro níveis do perfil. Um segmento ausente **não é desenhado**; o coto termina onde o nível manda. Saída em **SVG** (texto) e **PNG** (rasterização própria em `numpy`, sem biblioteca de imagem nova, o que mantém o pacote sem dependência pesada).
- **Variações (para o nível 1 não ser só um quadrado fácil):** pose (de pé, braços levantados, sentado), cores e espessuras, escala, rotação de poucos graus, fundo, ruído leve. A vista é **de frente**; a vista de costas fica como variação opcional, justamente para medir esquerda e direita.
- **Rótulo verdadeiro:** os **quatro níveis exatos**; as 144 combinações possíveis (4 × 4 × 3 × 3) aparecem todas.
- **Tamanho proposto:** 144 combinações × 3 variações de aparência = **432 imagens**.
- **Dificuldade esperada:** **baixa**. Se a **linha de base clássica** (ler cores e formas por região) chegar a 100%, o relatório **diz** que o aprendizado profundo não ganha no boneco. O resultado do nível 1 **não vale** para fotos reais, e a apresentação deve dizer isso.

### 4.2 Nível 2: sintético NOSSO, com variação de pose, oclusão e ruído

**Decidido pela equipe em 05/11/2026** ("aceitar, com variação de pose, oclusão e ruído"). É o **gerador do nível 1 com muito mais variação**, de modo que o nível 2 seja **de fato mais difícil** que o 1, e **todo ele é nosso** (sem licença externa, rótulos **exatos**).

**O que varia (cada fator tem uma intensidade de 0 a 3):**

| Fator | O que muda |
|---|---|
| **Aparência** | cores, espessura dos segmentos, proporções do corpo, roupa (listras, números de peito), tom de pele (paleta ampla), adereços |
| **Pose** | figura **articulada** (ângulos de ombro, cotovelo, quadril, joelho): de pé, correndo, saltando, arremessando, sentada, braços cruzados; a pose **encurta ou esconde** membros de verdade |
| **Oclusão** | objeto na frente (barra, placar, banner, outro corpo), **corte do enquadramento** e membro atrás de outro; **um membro encoberto vale `?` no rótulo, não um nível**, porque a verdade é o que se vê |
| **Iluminação** | brilho, contraste, gradiente, sombra projetada, dominante de cor |
| **Geometria** | rotação, perspectiva, vista de frente, de três quartos e (opcionalmente) de costas, escala e distância |
| **Fundo** | liso, pista, arquibancada, campo, textura confusa com ruído visual |
| **Ruído e compressão** | ruído gaussiano, desfoque, redução de resolução e **compressão JPEG** (qualidade de 20 a 90) |
| **Equipamento** | **cadeira de rodas** (de uso diário e de corrida) e **prótese** (lâmina de corrida, encaixe de uso diário), **desenhadas por nós** |

**Cada imagem carrega o vetor de dificuldade** (que fatores foram aplicados e com que intensidade), o que permite medir **por fator**.

**Tamanho:** **300 imagens**, renderizadas uma vez, com semente fixa, em **quatro faixas de dificuldade de 75 imagens cada**: faixa 0 (parecida com o nível 1, como **controle dentro do próprio nível 2**), faixas 1, 2 e 3 (leve, média, forte). Os rótulos continuam **exatos** (quatro níveis, com `?` quando encoberto, mais cadeira e prótese).

**Como a dificuldade será medida (e não apenas afirmada):**

1. **A linha de base clássica cai do nível 1 para o nível 2.** Ela lê cores e formas por região e deve ir quase a 100% no nível 1. O nível 2 só **conta como mais difícil** se o desempenho dela **cair de forma clara** (critério escrito antes de rodar: **queda de pelo menos 20 pontos** no acerto por atributo, comparando a faixa 0 com a faixa 3). **Se não cair, o relatório diz que o nível 2 não é mais difícil e a intensidade dos fatores é aumentada** antes de qualquer modelo rodar.
2. **A curva por faixa:** o acerto de cada extrator e de cada linha de base nas faixas 0, 1, 2 e 3, com intervalo. **Uma curva que desce** com a faixa mostra que a dificuldade é real; uma curva plana, que não é.
3. **Por fator** (pelo vetor de dificuldade): qual fator derruba mais cada modelo (pose, oclusão, iluminação, ruído).
4. **Regra para não "ajustar o teste ao modelo":** os valores das intensidades são **fixados usando só a linha de base clássica e o acaso**, e **congelados antes** de os modelos de aprendizado profundo rodarem. Os resultados dos modelos **não** mudam o gerador.

**O que o nível 2 NÃO é:** não é foto, **não mede** a robustez a pessoas reais, e uma queda da linha de base clássica **não prova** que ele é difícil como uma foto; prova só que ele **não é o boneco limpo**. O relatório diz isso.

**Fontes externas conferidas em 05/11/2026** (só leitura de páginas e APIs públicas; nada baixado) **e por que ficam de fora:**

| Fonte | O que é | Licença encontrada | Veredito |
|---|---|---|---|
| **WheelPose** (`hilab-open-source/wheelpose`) | **Gerador** em Unity (domínio aleatório, usuários de cadeira de rodas), derivado do PeopleSansPeople | **Código MIT.** Mas precisa do **Unity 2021.3** e do pacote **SyntheticHumans** (termos próprios da Unity, não conferidos). O repositório **não traz imagens prontas**. O conjunto UIW que ele cita (2.464 quadros de 84 vídeos públicos) vem de **vídeos do YouTube**, com licença sem clareza | **Fora.** Só cobriria "cadeira de rodas: sim", não amputação |
| **Ottobock, "Dear AI" (LDPR)**, Hugging Face (`ottobock/dear-ai-ldpr-lower-limb` e `-upper-limb`) | Biblioteca de **imagens reais** (cerca de 400 por parte, mais vídeos) de pessoas com perda de membro, mais um conjunto de imagens geradas por IA; 2,6 GB e 3,9 GB | **Licença própria**, "limb-difference-and-prosthetic-representation-dataset-license". O acesso é **fechado** (`gated`): os termos só se leem depois de entrar numa conta e **aceitar condições** | **Fora.** Não li a licença, não me cadastrei e não aceitei termos em seu nome. **As imagens da biblioteca são fotos reais de pessoas**, o que não é "sintético" |
| **ProGait** | 4 pessoas com prótese acima do joelho, em vídeo | No Hugging Face é **CC BY-NC-SA 4.0** (uso não comercial, fora da nossa lista) | **Fora** |

### 4.3 Nível 3: fotos reais do Wikimedia Commons (só manifesto)

**O que existe nesta etapa:** `docs/consistencia-imagem-laudo-manifesto-nivel3.csv`, com **30 arquivos candidatos** (a primeira versão tinha 35; esta é a **segunda**, depois do pedido de "mais fotos e fotógrafos"). Nenhuma foto foi baixada para o disco nem entra no repositório; vi **miniaturas no navegador** para escolher e para os rótulos grossos.

**A regra do atleta único (decisão de desenho, porque o par imagem e laudo só vale para UM atleta):**

- O nível 3 fica **restrito a fotos de um só atleta**. **"Um só atleta"** quer dizer que **uma pessoa é o assunto da foto**: a **maior no quadro, em foco e mais ou menos central**. Outras pessoas só podem aparecer **pequenas, ao fundo e fora de foco**.
- Dois casos têm essa ambiguidade e **estão marcados** na coluna `subject` como **`single_with_background`** (`K34-L3-017` e `K34-L3-021`: um velocista com blades em primeiro plano e outros atletas ao fundo, fora de foco): o rótulo e o laudo **valem para o atleta em primeiro plano**, e a nota diz isso. **Os 28 restantes são `single`.**
- **Fotos de grupo saíram do manifesto.** As 16 da primeira versão que eram de dois ou mais atletas em primeiro plano foram **retiradas**, e mais 4 de um só atleta por estarem longe ou repetirem o mesmo atleta e o mesmo evento.
- **Qualquer foto em que a pessoa em primeiro plano seja duvidosa na revisão em tamanho original sai.**

**O que as fotos de cadeira de corrida servem para (e para que não servem):** nelas **o nível do membro inferior não é visível** (as pernas ficam dentro da cadeira). **As 13 fotos do grupo `wheelchair_racing` só servem para o atributo `wheelchair`** (a coluna `usable_attributes` diz `wheelchair`); **não entram** nos testes de nível do membro inferior, nem nos de lado, e o rótulo de nível delas é `?`.

**Como foi feito:**

1. **Fonte:** a API pública do Commons, **só metadados**: categorias de atletismo paralímpico (Mundial IPC 2013, Paralimpíadas 2012, 2016, 2020 e 2024, o Encontro de Paris de 2014, corridas de cadeira de rodas, atletas paralímpicos) e **19 categorias de atletas individuais** com membro amputado ou prótese (por exemplo, velocistas de classes de membro inferior e de membro superior), mais buscas por texto. Foram vistos **mais de 2.000** arquivos distintos; os que passam nos filtros mecânicos (JPEG, 1.000 a 1.200 px ou mais, licença aceita, sem restrição declarada) foram **centenas**, e deles foram **vistas em miniatura** **mais de 300**.
2. **Licença conferida arquivo a arquivo:** para cada um dos 30, uma consulta **por número de página**, **refeita depois de escrito o CSV**, trouxe `LicenseShortName`, `LicenseUrl`, restrições, `NonFree`, autoria, data, **SHA-1**, dimensões, tipo e título; **as 30 linhas batem** com o arquivo (SHA-1, licença, dimensões e título). Só entram **CC0, domínio público, CC BY e CC BY-SA** (as que aparecem: CC BY-SA 3.0, CC BY-SA 4.0, CC BY-SA 2.0 e CC BY 2.0). **Nenhum arquivo tem restrição declarada nem marca de uso não livre.**
3. **Seleção e rótulos grossos:** por **folhas de miniaturas**. **Os códigos de classe nos títulos dos arquivos só serviram para achar candidatos; nenhum rótulo é uma classe nem uma inferência da imagem.**
4. **Nenhuma conta criada, nenhum termo aceito, nenhum arquivo baixado.**

**Resumo do manifesto:**

| | |
|---|---|
| Arquivos | **30**, dos quais **28 `single`** e **2 `single_with_background`** |
| Licenças | CC BY-SA 3.0: 15 · CC BY 2.0: 8 · CC BY-SA 4.0: 6 · CC BY-SA 2.0: 1 (nenhum CC0 nem domínio público) |
| Fotógrafos | **11**; **nenhum passa de 23%** (o maior tem 7 das 30 fotos); o teto pedido era cerca de 30% |
| Anos | 2007 (1), 2008 (1), 2011 (2), 2012 (5), 2013 (11), 2014 (4), 2016 (4), 2019 (1), 2022 (1) |
| Grupos | corrida em cadeira: **13** (só `wheelchair`) · prótese à vista: **8** · arremesso sentado: **1** · **a confirmar em tamanho original**: **8** (inclui os de provas de classes de braço e um possível controle sem diferença visível) |
| Tamanho dos originais | cerca de **184 MB** no total (mediana de 3,8 MB, máximo de 21 MB) |

**O que o manifesto traz por foto:** identificador `K34-L3-nnn`, grupo, `subject` (`single` ou `single_with_background`), `usable_attributes`, endereço da página no Commons, número da página, SHA-1 do arquivo original, dimensões, autor, licença e endereço da licença, data, e rótulos **grossos e provisórios**: `wheelchair`, `prosthesis_visible`, `lower_limbs` (`visible`, `partly`, `hidden_by_chair`, `to_confirm`), `upper_limbs` (`visible`, `partly`, `to_confirm`) e uma nota.

**Limitações do manifesto, ditas com franqueza:**

- **Rótulos por lado e por nível não existem.** A partir de miniaturas só se vê o grosso. Os rótulos que o experimento imagem e laudo usa (os quatro níveis, `?` incluído) exigem **olhar cada foto em tamanho original**; é o **primeiro passo da etapa 3**, e o plano é **rever as fotos antes** (as 30 páginas estão no CSV) e **retirar as que não servirem**.
- **Ainda não há uma foto clara de um só atleta com diferença de membro superior confirmada.** Procurei em 19 categorias de atletas amputados e em buscas por texto. As **7 fotos com `upper_limbs: to_confirm`** são de provas de classes de braço ou de atletas que podem ter diferença de braço; **só a revisão em tamanho original diz se o braço aparece diferente**. **Se não aparecer em nenhuma, o nível 3 não testa o membro superior**, e o relatório **diz isso** (o nível 2, nosso, testa).
- **Pouca variedade, ainda:** 11 fotógrafos, mas **quase tudo é atletismo de elite**, adultos, de **2007 a 2022**, com 11 das 30 de **2013** (o Mundial e a Maratona de Londres, de **três** fotógrafos). Não representa treino, formulário de peneira, nem foto de celular.
- **Idade e evento:** todos os arquivos são de eventos de elite e, na aparência, de adultos; **a idade não foi conferida arquivo a arquivo**. Dois têm a data ou o evento a confirmar (`K34-L3-018`, de 2007, numa prova em Manchester; e `K34-L3-010`, cuja data nos dados do arquivo, 2008, não bate com o título, 2011). Podem ser retirados se a equipe preferir. **Havia crianças ao fundo em duas fotos candidatas; foram tiradas.**
- **Revisão de licença do Commons:** arquivos importados do Flickr (os da Agência Brasil e de Peter Wayne, em CC BY 2.0) dependem de a licença no Flickr ter sido a declarada; conferi o que o Commons declara, **não** a página original.

**Privacidade, nomes e atribuição (valem para tudo que sair do experimento imagem e laudo):**

- **O endereço de cada arquivo no Commons contém o nome do atleta** (o título do arquivo costuma citá-lo). **O manifesto fica só no repositório privado**; **o relatório, os resultados e os slides usam apenas os identificadores `K34-L3-nnn`** e **não repetem nomes**. O manifesto **não pode virar público** sem tirar os endereços.
- **Atribuição:** CC BY e CC BY-SA exigem **creditar autor e licença onde a imagem for exibida**, e a **CC BY-SA exige compartilhar igual as adaptações**: **qualquer imagem derivada (recorte, filtro, mosaico) que for mostrada ou distribuída precisa levar a mesma licença e a atribuição**. O manifesto tem os campos de autor, licença e endereço da licença. **Não há distribuição das fotos** neste projeto, e **o que for mostrado em slide é decisão da equipe**, com a atribuição.
- **Licença não é direito de imagem:** a licença cobre o **direito autoral**, não o direito de imagem nem a LGPD de uma pessoa identificável. O risco **foi aceito pela equipe**; o texto, o relatório e qualquer slide **repetem** a ressalva.

## 5. Erros plantados (a taxonomia)

Cada imagem gera, ao lado do par **consistente**, pares com **um erro por vez**. **O veredito esperado não é escrito à mão: é o comparador aplicado aos rótulos verdadeiros** (da imagem e do laudo), o que mantém a verdade igual ao que o código dirá com extratores perfeitos.

| Tipo | O que muda no laudo | Veredito esperado, em geral |
|---|---|---|
| **(a) lado trocado** | esquerda e direita trocadas | **não confere** |
| **(b) nível errado** | um nível **acima ou abaixo** (dentro do domínio) em um membro | **não confere** |
| **(c) região errada** | o que era do membro inferior vira do superior (ou o contrário) | **não confere** |
| **(d) sem a informação** | o laudo **omite** o lado, ou o nível | **não sei** |
| **(e) laudo de outra pessoa** | o laudo de **outra** imagem do conjunto, sem nada a ver | **não confere**, **salvo** quando os dois conjuntos de rótulos coincidem |
| **(f) ruído sem erro de fato** | abreviações, erros de digitação, informação irrelevante, parágrafo longo | **confere** |

**Casos em que o erro plantado não é distinguível, e por isso são contados à parte, não como falha:** (a) com os dois lados **iguais** (trocar o lado não muda o laudo); (e) com rótulos **idênticos** aos da imagem; (b) quando o nível "acima ou abaixo" sai do domínio e a regra manda o vizinho. Cada exclusão é **contada e relatada** no mesmo quadro.

**Laudos sintéticos:** gerados por **modelos de frase com variações** em português (ordem, vocabulário, "esquerda" ou "à esquerda", "transtibial" ou "abaixo do joelho", etc.); se um modelo local for usado para **parafrasear**, **a verdade continua sendo o rótulo**, não o texto. O gerador do ruído (f) é determinístico (semente fixa).

## 6. Modelos

### 6.1 A máquina

Verificado hoje: **Intel Core Ultra 5 125H** (14 núcleos, 18 threads), **15,6 GB de RAM**, **Intel Arc integrada** (memória compartilhada, cerca de 2 GB reportados), **sem GPU dedicada**, Python 3.12.10, 238 GB livres. **Consequência:** só cabem modelos de poucos bilhões de parâmetros, e os de 3 B para cima **só com quantização** (um 7 B em bf16 tem 16,6 GB e **não cabe** na RAM).

### 6.2 Runtime proposto

**llama.cpp** (licença MIT; há binário pronto para Windows em CPU, cerca de 25 MB) servindo modelos **GGUF**, chamado por **HTTP local**. Vantagens: **saída restrita ao esquema** (gramática ou JSON schema), quantização que **cabe** na RAM e CPU mais rápida do que `transformers` em CPU, e o código do experimento imagem e laudo **não importa `torch`** para isto. Alternativa, mais lenta e mais pesada: `transformers` com PyTorch em CPU. As versões do binário e dos modelos entram **fixadas por hash** no relatório.

### 6.3 Candidatos (licença e tamanho conferidos nas páginas dos modelos, em 05/11/2026)

**Tempo por imagem é ESTIMATIVA, não medida** (nada foi baixado). Cálculo: geração limitada pela memória (bytes do modelo contra cerca de 60 a 90 GB/s, a 30 a 50% de eficiência) e leitura do prompt limitada pelo cálculo (2 operações por parâmetro por token, em 0,2 a 0,4 TFLOPS úteis); prompt de cerca de 250 tokens, saída de cerca de 80 tokens. **Será medido na etapa 3** e substituirá estes números.

| Papel | Modelo (repositório) | Licença dos pesos | Tamanho a baixar | RAM em uso | Tempo estimado por imagem (CPU) | Observação |
|---|---|---|---|---|---|---|
| Imagem, **principal** | **SmolVLM2-2.2B-Instruct** (`ggml-org/SmolVLM2-2.2B-Instruct-GGUF`, Q4_K_M + `mmproj` Q8) | **Apache-2.0** | 1,11 GB + 0,59 GB | cerca de 3 GB | **8 a 20 s** (típico 13) | o mais rápido; modelo pequeno, **esperar erro** em esquerda e direita |
| Imagem, **forte** | **Qwen2.5-VL-7B-Instruct** (`ggml-org/Qwen2.5-VL-7B-Instruct-GGUF`, Q4_K_M + `mmproj` Q8) | **Apache-2.0** | 4,68 GB + 0,85 GB | cerca de 7 GB | **30 a 70 s** (típico 40) | o mais capaz do grupo; roda só em **subconjuntos** do nível 1 |
| Imagem, **opcional** | Qwen2.5-VL-3B-Instruct (`ggml-org/...-3B-...-GGUF`, Q4_K_M) | **Qwen Research License** (uso de pesquisa; o repositório GGUF se declara Apache-2.0, o que **não bate** com a licença do modelo de origem) | 1,93 GB + 0,84 GB | cerca de 4 GB | 15 a 30 s | **Fora por padrão**: licença menos aberta e inconsistente nas duas páginas |
| Texto (laudo) | **Qwen2.5-1.5B-Instruct** (`Qwen/Qwen2.5-1.5B-Instruct-GGUF`, Q4_K_M) | **Apache-2.0** | 1,12 GB | cerca de 2 GB | 2 a 8 s por laudo | modelo de texto pequeno |
| Linha de base | **OpenCLIP LAION ViT-B/32** (`laion/CLIP-ViT-B-32-laion2B-s34B-b79K`) | **MIT** (código e pesos) | 0,61 GB | menos de 1 GB | 0,15 a 0,4 s | `torch` em CPU; só em `spikes/imagem_laudo/` |

**Excluídos, com o motivo:** **Gemma 3 e PaliGemma** (licença Gemma, com acesso condicionado por aceite manual); **Phi-3.5-vision, Moondream2, InternVL3 e Florence-2** (licenças MIT ou Apache-2.0, mas as páginas deles estão marcadas `custom_code`: em `transformers` exigem `trust_remote_code`, ou seja, **executar código que vem do repositório do modelo**, o que não quero fazer sem ler esse código; o Florence-2 também não segue instrução em JSON, e não achei GGUF do Phi-3.5-vision). **SmolVLM2 e Qwen2.5-VL não têm esse marcador** (conferido na API de modelos hoje).

### 6.4 O que precisa de aval antes de baixar (para a etapa 3)

Nada abaixo foi baixado. Cada item tem **nome, fonte e tamanho**:

| Item | Fonte | Tamanho |
|---|---|---|
| Binário do llama.cpp para Windows (CPU), uma versão fixada | `github.com/ggml-org/llama.cpp` (releases) | cerca de 25 MB |
| SmolVLM2-2.2B-Instruct, GGUF Q4_K_M e `mmproj` Q8 | `huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF` | 1,11 GB + 0,59 GB |
| Qwen2.5-VL-7B-Instruct, GGUF Q4_K_M e `mmproj` Q8 | `huggingface.co/ggml-org/Qwen2.5-VL-7B-Instruct-GGUF` | 4,68 GB + 0,85 GB |
| Qwen2.5-1.5B-Instruct, GGUF Q4_K_M | `huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF` | 1,12 GB |
| OpenCLIP LAION ViT-B/32 (`open_clip_model.safetensors`) | `huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K` | 0,61 GB |
| Pacotes Python do ambiente novo (`torch` para CPU, `open_clip_torch`, `numpy`, `pillow`, `httpx`) | PyPI | cerca de 0,3 GB |
| As fotos do nível 3 que a equipe aprovar | Wikimedia Commons (pelos endereços do manifesto) | cerca de 184 MB (as 30) |
| **Total** | | **cerca de 9 GB** |

## 7. Linhas de base obrigatórias

| Linha de base | O que faz | O que mostra |
|---|---|---|
| **(a) Clássica, no nível 1** | Lê o PNG do boneco por região (cores e formas, sem aprendizado), usando o conhecimento da geometria | Se chegar a **100%**, o relatório **diz**: o aprendizado profundo **não ganha no boneco** |
| **(b) CLIP zero-shot** | Escolhe, por pares de frases ("uma pessoa com prótese na perna esquerda" contra "na perna direita"), a mais próxima da imagem | **Com dados**, que ele erra lado e relações espaciais: o esperado é perto de **50% em esquerda e direita**, que é o acaso. Também **na imagem espelhada**, para separar "não sabe o lado" de "viés" |
| **(c) Chute** | A classe mais comum de cada atributo | O piso, para que "70%" não pareça muito quando o chute já dá 60% |

**Extras baratos:** uma linha de base de **laudo por regras** (palavras-chave e expressões regulares), para ver se o modelo de texto traz algo que regra simples não traz; e o teste de **imagem espelhada** (a imagem refletida, com o rótulo de lado trocado) para o extrator de imagem.

## 8. Medidas, tamanhos e relatório

**Tamanho de cada conjunto (proposta):**

| Nível | Imagens | Pares (7 por imagem: 1 consistente, 1 com ruído, 5 erros) | Execução do extrator de imagem |
|---|---|---|---|
| 1 | 432 | 3.024 | SmolVLM2: 1,6 h (13 s) · Qwen2.5-VL-7B: **só em 144 imagens**, 1,6 h (40 s) |
| 2 | 300 | 2.100 | SmolVLM2: 1,1 h · Qwen2.5-VL-7B: em 100 imagens, 1,1 h |
| 3 | 30 a 50 (hoje, 30) | 210 a 350 | os dois modelos nas 30 a 50: cerca de 7 a 11 min (SmolVLM2) e 20 a 33 min (Qwen2.5-VL-7B) |

O extrator de laudo roda por **laudo** (3 a 6 s por laudo no modelo de texto): para o nível 1 isso seria **3.024 laudos**, de 2,5 a 5 h; **propõe-se uma amostra estratificada de 1.000 laudos** no nível 1 e as **regras** (linha de base) em todos; nos níveis 2 e 3 **todos** os laudos (cerca de 2.300, cerca de 3 h). Soma estimada: **cerca de 10 a 12 h de máquina**, em segundo plano, sem competir com outras execuções.

**Por nível e por tipo de erro plantado**, sempre com o **tamanho do conjunto** ao lado:

- **taxa de aviso correto** (veredito igual ao esperado);
- **falso alarme em pares consistentes** (a taxa de "não confere" no caso consistente e no com ruído);
- **taxa de "não sei"**;
- **matriz de confusão** dos três vereditos.

**Por componente** (para dizer **onde** está o erro): acerto do **extrator de imagem** por atributo contra o rótulo; acerto do **extrator de laudo** por atributo; o comparador, **exato** por teste.

**Intervalos de confiança:** **Wilson de 95%** para proporções; as 7 variações de **uma mesma imagem não são independentes**, então os agregados usam **bootstrap por imagem** (reamostrando imagens inteiras). **No nível 3, com 30 a 50 imagens, o intervalo é largo** (cerca de ±18 pontos para uma proporção de 50% com 30 imagens): o relatório mostra isso e **não conclui** onde o intervalo cobre o chute.

**Regra de linguagem:** "acurácia" só ao lado de **N1**, em todos os níveis (1 e 2: sintético; 3: rótulos nossos).

## 9. O que isto não prova

- **O boneco é fácil.** O resultado do nível 1 **não vale** para fotos reais, e a apresentação deve dizer isso. Se uma linha de base clássica o iguala, **será dito**.
- **O nível 2 é nosso e sintético:** mede a robustez a variação de **aparência, pose, oclusão e ruído desenhados por nós**, não a de pessoas; a queda da linha de base clássica mostra que ele **não é o boneco limpo**, não que é difícil como uma foto.
- **O nível 3 é pequeno** (30 a 50 fotos de **um só atleta**), de **elite, adultos, 2007 a 2022**, de 11 fotógrafos, rotulado por nós; as de cadeira de corrida **só testam a cadeira**. Ele **não representa** fotos de celular, treino, formulário de peneira, nem pessoas de outras idades e cenários, e **pode não testar o membro superior**.
- **A conferência não verifica deficiência invisível** (visual, intelectual, ataxia, hipertonia): só o que é **visível e já declarado**. Uma conferência que "confere" **não** diz que a pessoa tem ou não tem a deficiência.
- **Não mede classe nem elegibilidade**, e **não vai** ser usado para isso.
- **O CLIP erra esquerda e direita**; ele entra **só** como linha de base.
- **Os modelos são pequenos** porque a máquina é pequena: um resultado fraco **não** diz que um modelo maior falharia.
- **Tempos e tamanhos são estimativas** até a etapa 3.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| **Direito de imagem e LGPD** de pessoas identificáveis nas fotos (a licença não cobre isso) | Risco **aceito pela equipe**; fotos **só locais** e **fora do repositório**; **o manifesto fica só no repositório privado** (os endereços trazem nomes) e **o relatório não repete nomes**; resultados só com `K34-L3-nnn`; nenhum rosto, nenhuma inferência de saúde; o que for a slide é **sua** decisão |
| **CC BY-SA** (atribuição e compartilhamento igual) | O manifesto guarda autor, licença e endereço; **imagem derivada mostrada ou distribuída leva a mesma licença e a atribuição**; não há distribuição das fotos |
| **Par imagem e laudo com mais de um atleta** | Nível 3 restrito a **um só atleta** (o maior, em foco e central); as duas fotos com gente ao fundo estão marcadas `single_with_background`; foto de grupo saiu |
| **Cadeira de corrida esconde as pernas** | As 13 fotos desse grupo **só valem para `wheelchair`** (coluna `usable_attributes`); o nível do membro inferior nelas é `?` |
| **Esquerda e direita** (da pessoa, e não de quem olha) | Convenção escrita e testada; imagem espelhada nos testes; CLIP como baseline |
| **Rótulos nossos feitos à mão** com viés | Rótulo de **só o que é visível**, `?` quando duvidoso; revisão pela equipe antes da execução; as dúvidas viram `?`, não palpite |
| **Número pequeno no nível 3** | Intervalos mostrados; nenhuma conclusão onde o intervalo cobre o chute |
| **Laudo sintético fácil demais** (templates) | Variações e ruído (f); a verdade é o rótulo, não o texto; baseline por regras para ver o ganho do modelo |
| **O modelo pequeno não segue o esquema** | Saída restrita por gramática; relatar a taxa de "não sei" em vez de forçar |
| **Tempo de máquina** (10 a 12 h estimadas) | Amostras estratificadas para o modelo de 7 B e para o laudo; níveis 1 e 2 primeiro; se o nível 3 atrasar, **entrega-se 1 e 2 e diz-se** |
| **Dependência de modelos externos mudando** | Versões e **hashes** dos pesos e do binário registrados; os pesos **não entram** no repositório |
| **Licença de peso inconsistente** (Qwen 3B contra o GGUF) | O 3B **fora por padrão**; só entram os de licença limpa nas duas páginas |
| **Uso indevido** (alguém usar o aviso como decisão) | Textos de saída com revisão humana; documento e relatório dizem "não é decisão"; nada na API ou na web |

## 11. Decisões

### 11.1 Respostas da equipe, decididas em 05/11/2026

| # | Pergunta | Decisão |
|---|---|---|
| 1 | O manifesto do nível 3 | **"Pedir mais fotos e fotógrafos."** Feito nesta versão: 30 fotos de **um só atleta**, **11 fotógrafos**, nenhum com mais de 23% (seção 4.3). A busca por **membro superior** continua **sem foto confirmada** |
| 2 | O nível 2 | **"Aceitar, com variação de pose, oclusão e ruído."** Seção 4.2: sintético **nosso**, com aparência aleatória e variação de pose, oclusão, iluminação, geometria, fundo e ruído; a dificuldade é **medida** pela queda da linha de base clássica |
| 3 | Modelos e runtime | **"Aceitar a lista candidata"**: SmolVLM2-2.2B, Qwen2.5-VL-7B, Qwen2.5-1.5B, OpenCLIP e llama.cpp (seção 6.3). **O download real continua dependendo do aval da equipe na etapa 3, com nome, fonte e tamanho** (seção 6.4) |
| 4 | Tamanhos | **"Aceitar os tamanhos"**: 432 imagens no nível 1, 300 no nível 2 e 30 a 50 no nível 3; **10 a 12 h de máquina** em segundo plano (seção 8) |

### 11.2 O que continua aberto

1. **Revisão das 30 fotos em tamanho original**, que dá os rótulos por lado e por nível (primeiro passo da etapa 3). **Dá para abrir as 30 páginas antes** e retirar as que não servirem.
2. **O membro superior no nível 3.** Se a revisão não achar diferença de braço visível em nenhuma foto, o nível 3 **não testa** o membro superior (o nível 2 testa). Se houver outra fonte, ela entra.
3. **Os downloads da etapa 3**, um a um, com nome, fonte e tamanho (seção 6.4).
4. **O que mostrar em slide**, com a atribuição (seção 4.3), é decisão da equipe.

## 12. Plano de testes (para a etapa 2)

Todos **determinísticos**, **sem `torch` e sem `transformers`**, com **extratores falsos**:

- **Comparador:** a tabela da seção 3.2 inteira; **simetria**; **uma divergência domina**; atributo `?` nos dois lados é neutro; saída com os campos corretos.
- **Esquema:** os valores batem com `LowerLimbLevel` e `UpperLimbLevel`; valor fora do domínio é recusado.
- **Gerador do boneco:** **determinístico** (mesma semente, mesmo SVG e mesmo PNG); cada combinação das 144 gera um desenho em que **o segmento ausente não aparece**; **a esquerda da pessoa aparece à direita da imagem** (teste de espelho); as variações não mudam o rótulo.
- **Gerador de laudos e erros:** cada tipo de erro **muda exatamente o que diz mudar** e o **veredito esperado vem do comparador**; os casos indistinguíveis são **marcados**, não escondidos; o ruído (f) **não** muda os fatos.
- **Extrator falso perfeito:** 100% no pipeline (a comparação não erra); **extratores falsos com falhas plantadas** (inverte lado, erra um nível, devolve `?`) dão o veredito previsto; o pipeline **localiza o erro** (imagem, laudo ou comparação).
- **Métricas:** Wilson contra valores de referência; bootstrap por imagem **reproduzível** com semente; quadro por nível e por tipo.
- **Linha de base clássica:** lê o PNG e acerta o boneco limpo; o teste **afirma o resultado** (se for 100%, o documento diz).
- **Guarda de isolamento:** o pacote novo **não importa** `torch`, `transformers` nem rede; nada fora do pacote o importa até a etapa 3; **nenhum arquivo** de imagem de pessoa, nenhum peso e nenhum laudo real no repositório.
- **Texto de saída:** **não contém** "elegível", "rejeitado" nem "classe", e **sempre** pede revisão humana.

## 13. As três etapas

| Etapa | Conteúdo | Quando (meta, não compromisso) |
|---|---|---|---|
| **1** | Esta nota e o manifesto candidato. **Sem código** | cerca de 11/11 |
| **2** | `src/para_triage/consistency/` (esquema, gerador do boneco, geradores de laudo e de erros, comparador, métricas, baseline clássica) e os testes com extratores falsos. **Sem modelo, sem `pyproject.toml`, sem CI** | cerca de 15/11 |
| **3** | `spikes/imagem_laudo/` (`requirements.txt` próprio, **ambiente virtual novo fora do repositório e fora de `<ambiente do projeto>`**, que **não será alterado**), extratores, CLIP, os três níveis, os resultados e o relatório. **Os downloads só depois do aval da equipe** | cerca de 23/11, para a entrega de 26/11 |

Cada etapa **espera a revisão** antes da seguinte. Se o nível 3 atrasar, entregam-se os níveis 1 e 2 e **diz-se**.

## 14. Fontes e como foram conferidas (05/11/2026)

Tudo por **leitura de página e de API pública**; **nada** foi baixado para o disco além do que o navegador mostra, e **nenhuma conta foi criada ou usada**.

- **Wikimedia Commons**, API de metadados (`commons.wikimedia.org/w/api.php`): licença, autoria, restrições, SHA-1, dimensões e data, por número de página.
- **Hugging Face**, API pública de modelos e conjuntos (`huggingface.co/api/models/...`, `/api/datasets/...`): licença declarada, tamanho dos arquivos, acesso condicionado ou não. Para o **Qwen2.5-VL-3B**, li o arquivo `LICENSE` do repositório ("Qwen RESEARCH LICENSE AGREEMENT"). Para o **conjunto da Ottobock**, vi a **página pública** (descrição do conjunto e aviso de aceite de termos); **o texto da licença não se lê sem aceitar**.
- **GitHub**: `hilab-open-source/wheelpose` (licença MIT, `README`), `ggml-org/llama.cpp` (MIT; binário de Windows em CPU de cerca de 25 MB nas versões de 05/11/2026) e os arquivos `LICENSE` de `openai/CLIP` e de `mlfoundations/open_clip` (MIT).
- **Máquina:** consulta do sistema (processador, memória, vídeo, disco, Python).
- **Tempos por imagem:** **estimativas por cálculo**, não medições (seção 6.3).

## 15. Estado da implementação (etapa 2)

**Evidência: N1.** Lógica pura e nível 1. **Sem modelo, sem `torch`, sem `transformers`, sem download, sem biblioteca nova** (o PNG é escrito e lido com `zlib` e `struct`; o desenho é rasterizado com `numpy`). `pyproject.toml`, CI, API, web e as outras pastas não foram tocados.

**O que existe** (`src/para_triage/consistency/`): `schema` (esquema fechado), `compare` (comparador e os três textos), `mannequin` (boneco em SVG e PNG), `dataset` (as 432 imagens do nível 1), `reports` (laudos em português e leitor por regras), `errors` (os sete pares por imagem), `pipeline` (extrator de imagem, extrator de laudo, comparador; diz **onde** está o erro), `fakes` (extratores falsos), `metrics` (Wilson, bootstrap por imagem, quadros), `baselines` (clássica e chute). `python -m para_triage.consistency level1 [--every N]` reproduz as tabelas abaixo (cerca de 3 min para as 432 imagens). Testes: `tests/test_consistency_*.py`; `IMAGEM_LAUDO_COMPLETO=1` roda a linha de base clássica nas 432.

**Resultado medido no nível 1 (432 imagens, semente 34, N1):**

| | |
|---|---|
| Linha de base clássica, lendo só o PNG | **431 de 432 imagens inteiras certas (99,8%)**; `lower_left` e `lower_right` 431/432, `upper_left` e `upper_right` 432/432. **Não chegou a 100%**: um pé lido como parcial (`K34-L1-0002`, braços levantados). O relatório diz, portanto: **no boneco limpo, a leitura clássica quase empata com a perfeição; um modelo de aprendizado profundo não tem onde ganhar muito** |
| Pares (7 por imagem) | 3.024; 2.982 nas taxas; **39 indistinguíveis** (36 de lado trocado, 3 de laudo de outra pessoa com rótulo igual) e **3 não aplicáveis** (região errada na imagem toda zero), contados à parte |
| Taxa de aviso correto, linha de base clássica | consistente 99,8%, ruído 99,8%, lado 100%, nível 100%, região 100%, omissão 99,8%, outra pessoa 100% (n entre 396 e 432 por tipo; Wilson inferior de 98,7% a 99,1%) |
| Falso alarme em consistentes e com ruído | 2 de 864 (0,2%; Wilson 0,1% a 0,8%) |
| Piso: dar sempre o veredito mais comum ("não confere") | 56,5% (Wilson 54,8% a 58,3%) |
| Chute por atributo (valor mais comum, para os dois extratores) | acerta 25% a 33% dos níveis dos membros, e **nunca avisa** (sempre "confere"): 0% em todos os tipos de erro |
| Leitor de laudo por regras | 100% dos laudos (os de ruído incluídos): **isto é por construção** (os laudos são nossos, de modelos de frase) e **não** diz nada sobre laudos reais |

**Decisões de implementação que a revisão deve olhar:**

1. **Pose por variação:** a variação 0, 1 e 2 de toda combinação usa pose de pé, braços levantados e sentado. Cores, espessuras (membros de 0,9 a 1,15; tronco de 0,95 a 1,1), escala (0,92 a 1,08), rotação (±3°), deslocamento (±8 px), fundo (liso ou com gradiente) e ruído (σ de 0 a 8) são sorteados por semente. A vista de costas existe no gerador e na linha de base, mas **não entra** no conjunto padrão.
2. **Pés maiores:** o pé tem 18 px de largura e meia-largura de 18 px, **fixos** (não seguem a espessura do membro). Com pé pequeno (14 x 12) a linha de base errava 1 em 10 imagens, por erro de alinhamento de escala; o ajuste foi no desenho do boneco (não nos modelos, que ainda não existem).
3. **Linha de base clássica:** usa o **conhecimento da geometria** (as constantes do gerador), nunca o rótulo, a semente nem o vetor de aparência. Alinha a parte do corpo desenhada em **todos** os níveis (cabeça, tronco, coxas até 65%, braços) para achar pose, escala, rotação e deslocamento, e olha, por lado, um ponto de prova por segmento removível. Se o alinhamento é ruim, responde `?`.
4. **Erro (b):** quando "um nível acima ou abaixo" sai do domínio e a regra manda o vizinho, o par **continua nas taxas** (ainda é um erro de nível) e é **contado à parte** na coluna "redirecionados" (131 de 432). Se a leitura da nota era "excluir", é uma linha para mudar.
5. **Erro (d):** tem duas formas, sorteadas: **sem o nível** (um atributo sai do laudo) e **sem o lado** ("há amputação abaixo do joelho em um dos membros inferiores, lado não informado"; os dois lados daquela região valem `?`).
6. **Erro (c):** o nível de um membro vai para a outra região do **mesmo lado** e o membro de origem fica `0`; o nível é cortado ao máximo da região de destino.
7. **Chute:** o extrator constante sempre dá "confere", então a taxa do chute em erros é 0%. Por isso o quadro traz também o **chute do veredito** (56,5%), que é o piso honesto para os números por tipo.
8. **Componentes:** em nível 1 `wheelchair` e `prosthesis` são `?` dos dois lados, então "certos" nesses atributos é trivial (432/432) e não conta.