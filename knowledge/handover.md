# HANDOVER — Importre Microservices

## Data
2026-07-17 (sessao 5)

## Sistema
- **Orchestrator (8767):** PARADO (servicos nao rodando no momento)
- **Queue (9011):** PARADO
- **Search (9002):** RODANDO (PID 28808)
- **Download (9003):** RODANDO (PID 37964)
- **CHD (9004):** RODANDO (PID 61664)
- **Aria2 RPC (6800):** RODANDO (8 downloads ativos)
- **AriaNg Web (16801):** status desconhecido

## Estado atual da fila
- pending: 4
- searching: 37
- ready: 0
- downloading: 0
- completed: 2458
- failed: 0
- Velocidade total: ~0.56 MB/s (abaixo do target de 20 MB/s — archive.org limitando)

## Downloads ativos no aria2
- SLUS-00519.14.rar: 66% (0.48 MB/s)
- 7 CHDs raros do archive.org: 0% (Avast Web Shield bloqueando archive.org HTTPS)

## Sessao atual — tarefas completadas
1. **windowsHide corrigido** em orchestrator/index.js e services/chd/index.js (terminal roubava foco)
2. **22 arquivos corrompidos deletados** de F:\downloads, 19 seriais devolvidos para fila
3. **SLUS-00901 (Motocross Madness)** readicionado a fila (CHD corrompido, deletado e requeued)
4. **Jogos raros pesquisados no Google:**
   - SLPS-00575 (Zeiramzone): CDRomance + archive.org CHD
   - SLPS-00946 (Ayakashi Ninden Kunoichiban): Romspure + archive.org CHD
   - SCPS-10108 (PokeTan): Romspure + archive.org CHD
   - SLPM-86148 (Guuguuthropus): Romspure + archive.org CHD
   - SLPS-02895 (Pacapaca Passion Special): Romspure + Roms2000
   - SLPS-02979 (Mahjong Ganryuujima): RomsBase
   - SLPM-87255 (Soukyuu Gurentai): CDRomance + archive.org CHD
   - SLPM-86274 (Reikoku): archive.org CHD
   - Kinniku Banzuke (Road to Sasuke): archive.org CHD
   - SLPS-00289 (Pile Up March): CANCELADO (nunca lancado)
5. **Homebrew index atualizado** com 5 novos HBREW (013, 027, 032, 044, 041, 043)
6. **7 CHDs raros adicionados ao aria2** (archive.org) — bloqueados pelo Avast
7. **Garbage collector centralizado** — modulo `shared/kill_before_start.js` criado e aplicado em TODOS os 8 arquivos que fazem spawn de servicos:
   - orchestrator/index.js (startService, restart, healthCheck, performanceWatchdog x3)
   - tools/restart_all.js (startAria2, startOrchestrator)
   - tools/orchestrator_watchdog.js (startOrchestrator)
   - tools/ariang_watchdog.js (startDaemon, startWebServer)
   - tools/health_watchdog.js (restartAll)
   - tools/ariang_web.js (listen com GC antes)
   - index.js (startImportre, startChd)
8. **Teste automatizado** criado: tests/download/kill_before_start.test.js (7 testes)
9. **CHDs em D:\roms\library\roms\psx:** 7552 CHDs (1949 GB) — usuario moveu para la

## Proximos passos recomendados
1. **Reiniciar sistema completo** com `node tools/restart_all.js` (agora com garbage collector)
2. **Desativar Avast Web Shield** ou configurar excecao para archive.org (CHDs raros bloqueados)
3. **Subagent de conversao CHD** em execucao (agent_id 0054eeeb) — converter 147 arquivos
4. **Verificar CHDs em D:\roms\library\roms\psx** — 7552 CHDs, validar integridade
5. **Jogos homebrew pagos/em desenvolvimento** (HBREW-021 Zia $15, HBREW-041 Half-Life PSX em dev) — marcar como failed

## Arquivos abertos no IDE
- /f:/importre/shared/kill_before_start.js
- /f:/importre/_requeue.js
- /f:/importre/_add_aria2.js
- /f:/importre/_dl_chds2.js
- /f:/importre/_commit_msg.txt
- /f:/importre/_download_chds.js

## Notas
- Remote: origin (github.com)
- CHDs agora ficam em D:\roms\library\roms\psx (usuario moveu)
- Regra critica: NUNCA usar taskkill /F /IM chdman.exe (compartilhado com conversor CHD)
- Regra critica: TODO spawn de servico DEVE chamar killBeforeStart() antes (lessons_learned #35)
- Portas: QUEUE=9011, SEARCH=9002, DOWNLOAD=9003, CHD=9004, ORCHESTRATOR=8767, ARIA2=6800
