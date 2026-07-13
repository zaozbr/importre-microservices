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

## Caminhos e Shell

- Nunca usar `.` no inicio de caminhos absolutos ou comandos exec (ver skill `no-leading-dot`).
- Usar `cd "F:\importre" && ...` ou paths absolutos diretos.

## Arquitetura

- Microservicos Node.js: queue (9001), search (9002), download (9003), chd (9004), orchestrator (8767).
- Plugins de fontes em `services/search/plugins/` devem declarar: `name`, `matchType`, `needsMultiChunk`, `priority`, `enabled`.
- Prioridade crescente: sort `pluginPriority(a) - pluginPriority(b)`.
- Nunca usar `taskkill /F /IM chdman.exe` (usado pelo conversor CHD paralelo).
