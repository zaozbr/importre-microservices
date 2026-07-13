# Licoes Aprendidas — Importre Microservices

## 1. Uso de ponto (`.`) em caminhos e comandos

**Problema:** Insercao automatica de `.` no inicio de caminhos absolutos (`.F:/importre/...`) e comandos (`. cd ...`) causava erros de internal error e parser error no PowerShell.

**Correcao:** Criada regra em `.devin/skills/no-leading-dot/SKILL.md` e filtro mental pre-envio para nunca usar `.` em caminhos absolutos ou comandos `exec`.

## 2. STOP/RESTART e EADDRINUSE

**Problema:** Endpoint de stop nao finalizava o orchestrador e a verificacao de portas incluia a porta do proprio orchestrator, causando loop infinito.

**Correcao:** `killAndCleanup` agora verifica apenas portas dos servicos; endpoint `/api/control/stop` chama `shutdownOrchestrator()` apos responder.

## 3. Reprocessar falhas

**Problema:** Itens em `q.failed` nao voltavam para `q.queue` como pendentes, entao cards de status nao refletiam a mudanca.

**Correcao:** Endpoint `/reprocess-failures` agora tambem itera sobre `q.failed`, readiciona itens a fila como `pending` e limpa o objeto `failed`.

## 4. Arquitetura de plugins de fontes

**Aprendizado:** Plugins devem declarar explicitamente `matchType`, `needsMultiChunk`, `priority` e `enabled`. Isso permite ordenar fontes e ativar fallback web apenas quando fontes diretas falham.

## 5. Prioridade de plugins

**Problema:** Ordem inicial estava invertida (maior prioridade primeiro), fazendo fallbacks web serem tentados antes de caches locais.

**Correcao:** Sort crescente por prioridade (`pluginPriority(a) - pluginPriority(b)`).

## 6. Sonar / ESLint — qualidade de codigo obrigatoria

**Problema:** Codigo sem verificacao automatica de qualidade acumulava bugs silenciosos: variaveis nao usadas, complexidade cognitiva alta, strings duplicadas, escapes desnecessarios, reatribuicao de parametros.

**Correcao:** Instalado `eslint-plugin-sonarjs` + `eslint` 9 com flat config em `eslint.config.mjs`. Todas as regras Sonar de bug/correcao ativadas como `error`. Complexidade cognitiva maxima 25. Scripts npm: `npm run lint`, `npm run lint:fix`, `npm run sonar`.

**Regra OBRIGATORIA:** Rodar `npm run lint` antes de todo commit. Zero warnings e zero erros sao exigidos. Se uma regra Sonar for muito barulhenta, desativa-la com justificativa no comentario da regra em `eslint.config.mjs` — nunca ignorar warnings.
