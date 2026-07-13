# Frustration Log — Importre Microservices

## 1. Pontos sem controle em caminhos/comandos

- **Data:** 2026-07-12
- **Contexto:** Usuario percebeu que a IA inseria `.` automaticamente no inicio de caminhos absolutos e comandos `exec`.
- **Impacto:** Falhas em `read`, `edit`, `write` e `exec` (Internal error, ParserError).
- **Acao corretiva:** Criada skill `.devin/skills/no-leading-dot/SKILL.md` e regra de comportamento; filtro pre-envio rigoroso aplicado.

## 2. STOP nao finalizava orchestrador

- **Data:** 2026-07-12
- **Contexto:** Teste de STOP mostrava que orchestrador permanecia vivo e porta 8767 continuava ocupada.
- **Impacto:** Necessidade de matar processos manualmente; risco de EADDRINUSE.
- **Acao corretiva:** Corrigido `killAndCleanup` para excluir ORCHESTRATOR do check de portas livres; adicionado `shutdownOrchestrator()` no endpoint de stop.

## 3. Reprocessar falhas nao atualizava cards

- **Data:** 2026-07-12
- **Contexto:** Usuario reportou que ao reprocessar falhas, os cards de status nao refletiam a mudanca.
- **Impacto:** Contador de falhas permanecia alto mesmo apos reprocessamento.
- **Acao corretiva:** Endpoint de reprocessar falhas agora readiciona itens de `q.failed` para `q.queue` como `pending` e limpa `q.failed`.
