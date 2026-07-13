# Handover — Importre Microservices

**Data:** 2026-07-12
**Sistema:** Rodando

## Estado atual

- Orchestrator: porta 8767, PID 205464
- Queue: porta 9001, PID 174560
- Search: porta 9002, PID 14964
- Download: porta 9003, PID 160180
- CHD: porta 9004, PID 31740
- Dashboard: `http://127.0.0.1:8767/`

## Ultimas tarefas completadas

1. Corrigido STOP/RESTART para finalizar orchestrador e liberar portas.
2. Criada arquitetura de plugins de fontes (28 plugins).
3. Ajustado dashboard: fila primeiro com dobro da altura, busca em segundo.
4. Corrigido reprocessamento de falhas para mover itens de `q.failed` de volta para fila.
5. Criado workflow `safe_point_commit` em `.devin/workflows/`.
6. Criada documentacao em `knowledge/`.

## Proximos passos recomendados

- Monitorar downloads de `archive.org` para performance.
- Adicionar resolvers especificos para plugins web (Vimm, RetroStic, RomsDL, etc.) se necessario.
- Testar downloads a partir de novas fontes.
- Revisar se `google-fallback` precisa de melhorias (scraping de buscadores pode ser bloqueado).

## Arquivos abertos no IDE

- services/queue/index.js
- services/download/index.js
- services/search/index.js
- services/search/sites.js
- services/search/plugins/google_fallback.js

## Notas

- Remote configurado: `origin https://github.com/zaozbr/importre-microservices.git`
- Repositorio criado e push realizado: https://github.com/zaozbr/importre-microservices
- Tag local: `v1.0.0` (enviada para o remoto).
- VERSION.md criado com SemVer.
- Sistema antigo Python em `D:\roms\library\roms\psx\` (importre.py) nao deve ser confundido com a nova versao Node.js em `F:\importre\`.
- Regra critica: nunca usar `taskkill /F /IM chdman.exe` (usado pelo conversor CHD paralelo na porta 8766).
