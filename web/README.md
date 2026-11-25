# Frontend

Interface web da triagem: o profissional escolhe o tipo de comprometimento, preenche os dados do atleta e recebe as classes prováveis, as provas elegíveis, os equipamentos e um relatório (instantâneo e, em seguida, o do LLM).

**Stack:** Next.js 16 (App Router, Turbopack, Cache Components), React 19, TypeScript, Tailwind CSS 4, shadcn/ui (sobre Base UI), SWR e react-markdown.

## Rodar

Em dois terminais, a partir da raiz do repositório:

```bash
# 1. API (precisa do ambiente Python com os extras da API)
python -m uvicorn para_triage.api.app:app --port 8000

# 2. Frontend
cd web
npm install
npm run dev        # http://localhost:3000
```

O navegador só fala com o Next.js: `/api/*` é redirecionado para a API (`rewrites` em [next.config.ts](next.config.ts)). Para apontar para outro servidor, use `API_URL`:

```bash
API_URL=http://servidor:8000 npm run dev
```

A API usa o checkpoint do MLP em `runs/mlp_v1/model.pt` (veja o README da raiz) e o Ollama em `http://localhost:11434` com `qwen2.5:7b`. Sem o checkpoint, mostra só as regras; sem o Ollama, só o relatório de referência. O selo no topo da página mostra o que está disponível.

## Como está organizado

```
src/
  app/                    página e layout (Server Components)
  components/triage/      triage-app (estado), group-picker, profile-form, field-controls,
                          results-panel, report-panel, markdown, health-badges
  components/ui/          componentes do shadcn/ui
  lib/
    profile-schema.ts     formulários por tipo de comprometimento (campos, opções, regras de exibição)
    api-types.ts          tipos que espelham src/para_triage/api/schemas.py
    api.ts                cliente HTTP
```

### Fluxo

1. `buildProfile` converte as respostas do formulário no perfil da API (só campos visíveis e preenchidos).
2. Ao enviar, duas requisições independentes saem em paralelo: `POST /api/triage` (regras + MLP + relatório de referência, instantâneo) e `POST /api/report` (inicia o job do LLM).
3. O resultado aparece na hora. O `ReportPanel` consulta `GET /api/report/{id}` a cada 2 s (SWR) até o LLM terminar e troca o texto, com o selo "modelo · verificado".

### Adicionar ou alterar um campo

Edite `lib/profile-schema.ts`: cada campo é um objeto com `kind` (`number`, `select`, `tri`, `multi`), `label`, ajuda e, se for o caso, `when` para exibição condicional. O nome do campo deve existir em `ProfileIn` (`api-types.ts` e `api/schemas.py`).

## Boas práticas aplicadas

Seguem a skill [vercel-react-best-practices](https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices): requisições independentes em paralelo, `react-markdown` carregado sob demanda (`next/dynamic`), SWR para o polling, estado derivado durante a renderização (sem `useEffect`), `useTransition` para o estado de envio, imports diretos (sem barrel files) e componentes definidos fora de outros componentes.

## Próximos passos possíveis

- Traduzir para o português as razões das regras (hoje vêm em inglês do motor e só alimentam o LLM).
- Histórico de análises e autenticação.
- Exportar o relatório em PDF.
- Mais esportes além do atletismo.
