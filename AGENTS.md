# AGENTS.md — Regras do Projeto Importre

## Sonar / ESLint (OBRIGATORIO)

- **Rodar `npm run lint` antes de todo commit.** Zero erros e zero warnings.
- Regras SonarJS ativadas em `eslint.config.mjs` — todas as de bug/correcao como `error`.
- Complexidade cognitiva maxima: 25 por funcao. Se exceder, extrair sub-funcoes.
- Nunca ignorar warnings. Se uma regra for inadequada, desativa-la com justificativa no `eslint.config.mjs`.
- `npm run lint:fix` corrige problemas auto-corrigiveis (prefer-const, etc).
- `npm run sonar` executa sonar-scanner CLI (requer sonar-scanner instalado + `sonar-project.properties`).

## Workflow de Commit

1. `git status --short`
2. `npm run lint` (deve passar com 0 problemas)
3. `npm test` (deve passar com 0 falhas)
4. `git add -A`
5. Commit com assinatura Devin
6. Push apenas se solicitado

## Testes (OBRIGATORIO)

- **Rodar `npm test` antes de todo commit.** Zero falhas.
- Framework: mocha + chai (CommonJS).
- Suites em `tests/download/`:
  - `unit.test.js` — testes unitarios (67 testes): resolvers, slots, speedToMbps, sortSources, cooldown, tracking.
  - `stress.test.js` — testes de stress (18 testes): concorrencia, race conditions, FIFO de waiters, memoria.
  - `integration.test.js` — testes de integracao (10 testes): mock HTTP, queue mock, slots sob carga.
  - `resilience.test.js` — testes de resiliencia (21 testes): 404, 500, 429, URL invalida, arquivo corrompido, retry.
- Helper: `tests/download/_setup.js` — mocka config e cria tmpDir isolado.
- Scripts: `npm test`, `npm run test:unit`, `npm run test:stress`, `npm run test:integration`, `npm run test:resilience`.

### Testes E2E por Linha de Pipeline (OBRIGATORIO — REGRA GLOBAL)

**Toda linha de download e toda linha de search deve ter um teste E2E automatizado que verifica funcionamento de ponta a ponta.** "Linha" = cada plugin de fonte de search + cada fonte de download (rrSources).

- **`tests/e2e/search_lines.test.js`** — Para cada plugin em `services/search/plugins/`:
  - Carrega o plugin via `loader.js`
  - Verifica que exporta `name`, `matchType`, `search()` function
  - Chama `search(serial, title)` com seriais conhecidos
  - Verifica que retorna array de sources `{ site, url, title }`
  - Verifica que `url` e uma URL valida (http/https/magnet) ou string nao-vazia
  - Verifica que nao lanca exception (tratamento de erro graceful)
  - Reporta quais plugins estao broken/timeout/sem resultado

- **`tests/e2e/download_lines.test.js`** — Para cada fonte em `rrSources`:
  - Verifica que a fonte esta registrada no download service
  - Verifica que tem resolver correspondente (tryResolveUrl ou fallback)
  - Mocka HTTP e verifica que o download e submetido ao aria2
  - Verifica que cooldown/slots funcionam para aquela fonte
  - Verifica que erro 429 aciona cooldown da fonte

- **`tests/e2e/rpc_token.test.js`** — Para cada arquivo que faz chamadas aria2 RPC:
  - Verifica que todas chamadas incluem `token:devin` nos params
  - Cobre: `aria2_rpc.js`, `motrix_watchdog.js`, `ariang_watchdog.js`, `orchestrator/index.js`

- **`tests/e2e/orchestrator_api.test.js`** — Para cada rota do orchestrator:
  - Verifica que responde (status 200 ou erro estruturado, nao 404)
  - Verifica que `/api/status` retorna `globalSpeed` com `download`/`upload` numericos
  - Verifica que `/aria2` proxy funciona com token

### Regra: Bug -> Teste Unitario

**Todo bug encontrado deve virar um teste unitario autoaplicavel.** Antes de corrigir um bug:
1. Escrever um teste que reproduz o bug (deve falhar)
2. Corrigir o bug
3. Verificar que o teste agora passa
4. O teste permanece na suite permanentemente (regression guard)

### Reabsorcao Obrigatoria

ANTES de processar qualquer novo prompt, reabsorver OBRIGATORIAMENTE:
1. `AGENTS.md` (regras do projeto — NAO NEGOCIAVEIS)
2. `knowledge/lessons_learned.md` (licoes aprendidas)
3. Todos os workflows em `knowledge/workflows/`
4. Todas as skills em `.devin/skills/`
5. O HANDOVER mais recente em `knowledge/`

Esta reabsorcao e SILICIOSA: nao exibir o conteudo lido no chat, apenas absorver e aplicar.

## Caminhos e Shell

- Nunca usar `.` no inicio de caminhos absolutos ou comandos exec (ver skill `no-leading-dot`).
- Usar `cd "F:\importre" && ...` ou paths absolutos diretos.

## Arquitetura

- Microservicos Node.js: queue (9001), search (9002), download (9003), chd (9004), orchestrator (8767).
- Plugins de fontes em `services/search/plugins/` devem declarar: `name`, `matchType`, `needsMultiChunk`, `priority`, `enabled`.
- Prioridade crescente: sort `pluginPriority(a) - pluginPriority(b)`.
- Nunca usar `taskkill /F /IM chdman.exe` (usado pelo conversor CHD paralelo).
