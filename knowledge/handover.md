# Handover — Importre Microservices

**Data:** 2026-07-15
**Sistema:** Rodando

## Estado atual

- Orchestrator: porta 8767
- Queue: porta 9001
- Search: porta 9002
- Download: porta 9003
- CHD: porta 9004
- Dashboard: `http://127.0.0.1:8767/`
- aria2c: porta 16810, com cookie archive.org carregado
- AriaNg: `http://127.0.0.1:6880/` (web UI para aria2)

## Cookie archive.org (IMPORTANTE)

- Conta atual: `kideje5455@ezimb.com` / screenname `impcoll2026z` / senha `Arch2026xK9!mp`
- Cookie em `F:\importre\archive_cookies.txt` (formato Netscape) — NUNCA commitar (secret)
- Para renovar: `node tools/renew_archive_cookie.js`
- Se conta expirar: ver `knowledge/archive_cookie_renewal.md` (criar nova via temp-mail.org + Playwright)
- aria2c usa `--load-cookies=F:\importre\archive_cookies.txt` em `tools/start_aria2c.bat`

## Descoberta de porta RPC (NOVO)

- Watchdogs (`ariang_watchdog.js`, `motrix_watchdog.js`) descobrem porta RPC via netstat + PIDs de aria2c.exe
- Zero listas hardcoded — porta encontrada dinamicamente
- `ariang_web.js` expõe endpoint `/rpc-port` com a porta descoberta
- `inject_ariang_hack.js` busca porta do endpoint `/rpc-port`
- Daemon sempre volta à porta original do config do Motrix após restart

## Ultimas tarefas completadas (sessão 2026-07-15)

1. Descoberta de porta RPC 100% dinâmica via netstat (sem listas hardcoded)
2. Watchdog reinicia aria2 na porta original, com limpeza de TIME_WAIT
3. `inject_ariang_hack.js` usa endpoint `/rpc-port` em vez de lista hardcoded
4. `start_aria2c.bat` atualizado com `--load-cookies` e aspas no user-agent
5. Conversão de duplicados para CHD em `C:\teste` (subagente em background)
6. Re-enqueue de 111 seriais CHD falhos com priority=10
7. `sortSourcesBySpeed` prioriza fontes CHD diretas
8. Novos tools: `cdp_extract`, `convert_all_to_chd`, `dedup_chds`, `recompose_chd`, `reconvert_from_originals`, `archive_login`, `check_speed`, `check_stuck`
9. Novos services: `chd_convert_one`, `chd_worker` (subprocesso CHD separado)
10. Workflow de commit completo (7 passos) fixado em `knowledge/workflows/commit.md`

## Proximos passos recomendados

- Monitorar downloads de `archive.org` para performance
- Verificar resultado da conversão CHD em `C:\teste` (subagente pode ter terminado)
- Adicionar indices locais (archive_name_index, coolrom_index, etc.) aos plugins
- Melhorar resolvers de download para CoolROM, Vimm, RetroStic e RomsDL
- Considerar desativar google-fallback (scraping de buscadores bloqueado/lento)
- Adicionar testes automatizados para search e download

## Arquivos abertos no IDE

- services/download/index.js
- tools/cdp_extract.js
- tools/start_aria2c.bat
- tools/renew_archive_cookie.js
- knowledge/handover.md
- knowledge/lessons_learned.md
- knowledge/archive_cookie_renewal.md

## Notas

- Remote configurado: `origin https://github.com/zaozbr/importre-microservices.git`
- Repositorio criado e push realizado: https://github.com/zaozbr/importre-microservices
- Tag local: `v1.0.0` (enviada para o remoto)
- VERSION.md criado com SemVer
- Sistema antigo Python em `D:\roms\library\roms\psx\` (importre.py) nao deve ser confundido com a nova versao Node.js em `F:\importre\`
- Regra critica: nunca usar `taskkill /F /IM chdman.exe` (usado pelo conversor CHD paralelo na porta 8766)
- Workflow de commit completo em `knowledge/workflows/commit.md` (7 passos obrigatórios)
