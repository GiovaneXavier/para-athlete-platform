# Guia de classes: lista de verificação de acessibilidade

O que o axe (`web/scripts/a11y.mjs`, job `a11y` do CI) não cobre fica nesta lista, para ser feito por uma pessoa. Marque a data e quem fez. **Nada abaixo foi feito ainda**, salvo onde estiver dito.

## Feito de forma automática (a cada PR)

- axe-core com as regras WCAG 2.0 A/AA, 2.1 A/AA, 2.2 AA e boas práticas, em 23 rotas (as 21 páginas do guia, a home e `/transparencia`), a 320 px e a 1280 px, no tema claro. Falha se houver qualquer violação, rolagem horizontal ou mais de um `main#conteudo`.
- Testes em Python: texto alternativo e descrição longa de toda figura, números desenhados repetidos na descrição, figuras só com a cor do texto, glossário e links resolvidos.

## A fazer por uma pessoa

| # | Verificação | Como | Feito |
|---|---|---|---|
| 1 | **Leitor de tela** (NVDA no Windows e VoiceOver no iPhone ou Mac) em uma página de cada tipo: início, grupo, classe, glossário | Seguir o roteiro `docs/teste-leitor-de-tela.md` (NVDA e VoiceOver, 11 páginas, folha de registro). Por enquanto **só o usuário testa**, o que é indicativo e não substitui uma pessoa que usa leitor de tela no dia a dia | **Não** (ninguém identificado; pendência explícita) |
| 2 | Só teclado, em todas as páginas | Tab e Shift+Tab: o link "Pular para o conteúdo" é o primeiro; foco sempre visível; nenhuma armadilha; ordem igual à visual | Parcial (feito pelo autor no navegador em algumas páginas) |
| 3 | Zoom de 200% e 400% | Sem perda de conteúdo nem rolagem em duas direções (exceto tabelas largas, que rolam dentro de uma região com foco) | Não |
| 4 | Espaçamento de texto aumentado | Aplicar o favorito de espaçamento de texto da WCAG 1.4.12 | Não |
| 5 | Modo de cores forçadas (alto contraste do Windows) | As figuras usam `currentColor`: os traços devem continuar visíveis | Não |
| 6 | **Tema escuro** | Hoje o app **não tem alternância de tema**; o tema escuro só existe nos tokens. O axe com `A11Y_DARK=1` acusa falhas de contraste em botões e selos do tema escuro, em componentes que já existiam; ninguém chega a esse tema hoje | Informativo |
| 7 | **Tom e desenho** (neutros e respeitosos) | A especialista avalia a folha de revisão (gerada por `python -m para_triage.guide.review_sheet`); o ideal é também uma pessoa com deficiência (atleta), **ainda não identificada** | Não |
| 8 | Leitura fácil, Libras, outros idiomas | Fora do K18 (K8) | n/a |

## Como rodar localmente

```bash
cd web
npm run build
npm install --no-save @playwright/test@1.55.0 @axe-core/playwright@4.10.2
npx playwright install chromium
npx next start -p 3000 &
BASE_URL=http://localhost:3000 node scripts/a11y.mjs        # código 0: sem violação; 1: violações; 2: problema de infraestrutura
A11Y_DARK=1 BASE_URL=http://localhost:3000 node scripts/a11y.mjs   # inclui o tema escuro (informativo)
```
