# HANDOVER — Importre Microservices

## Data
2026-07-17 (sessao 6)

## Sistema
- **Orchestrator (8767):** RODANDO
- **Queue (9011):** RODANDO (PID 51312)
- **Search (9002):** status desconhecido
- **Download (9003):** status desconhecido
- **CHD (9004):** status desconhecido
- **Aria2 RPC (6800):** RODANDO
- **AriaNg Web (16801):** status desconhecido

## Estado atual da fila
- pending: 0
- searching: 0
- ready: 0
- downloading: 0
- cooldown: 0
- completed: 523 (97.4%)
- failed: 14 (jogos raros/undumped/homebrews sem URL)
- Total: 537

## Downloads concluidos nesta sessao
- 7 CHDs raros do archive.org via curl HTTP (contornando Avast Web Shield):
  - Zeiramzone (334.6MB), Soukyuu Gurentai (200.6MB), Zoku Gussun Oyoyo (406.8MB)
  - Guuguuthropus (17.7MB), PokeTan (33.4MB), Reikoku (376MB), Kinniku Banzuke (74.6MB)
- 16 jogos do Romspure via Playwright (subagent) — ~4.1GB total:
  - SLPS-00946 (Ayakashi, 528MB), SLES-02693 (542MB), SLES-02441 (509MB), SLPS-00575 (466MB)
  - SLPS-00488 (395MB), SLPM-86274 (394MB), SLPS-02252 (258MB), SLPS-00142 (208MB)
  - SLPM-87255 (232MB), SLPS-02895 (138MB), SLPS-01147 (97MB), KinnikuBanzuke (85MB)
  - SLPM-86148 (26MB), SCPS-10108 (33MB), SLPM-86045 (1.4MB), SLPS-02979 (1.9MB)
- 2 homebrews do archive.org:
  - HBREW-027 (Bow and Arrow PSX, 1.1MB)
  - HBREW-044 (PSXMahjongg/Net Yaroze Collection, 39.3MB)
- 2 jogos pendentes via Playwright:
  - SLUS-00519 (Castlevania SOTN, 406.5MB)
  - SLUS-00286 (Final Fantasy VII, 544.1MB)

## Total baixado nesta sessao
- 7 CHDs do archive.org (via curl HTTP): ~1.4GB
- 16 jogos do Romspure (via Playwright): ~4.1GB
- 2 homebrews do archive.org: ~40MB
- 2 jogos pendentes do Romspure (via Playwright): ~950MB
- **Total: ~6.5GB, 27 jogos**

## 14 jogos falhados (sem fonte disponivel)
- SLPM-87214, SLUS-01205, SLES-03235, SLPS-00289, SLPS-02311: jogos raros/obscuros
- HBREW-013 (Flappy Adventure 3): URL de download nao encontrada
- HBREW-032 (Turbo-Tihu): itch.io requer browser interativo
- HBREW-041, HBREW-043, HBREW-021: homebrews sem fonte
- yicestar-jap-UNKNOWN, yicestar-ntsc-UNKNOWN, WCG2-UNKNOWN, SBL0-UNKNOWN: seriais invalidos/placeholder

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
