# Handover — Importre Microservices

**Data:** 2026-07-15 (sessao 2)
**Sistema:** Rodando — 2061/2725 completados (76%)

## Estado atual

- Orchestrator: porta 8767
- Queue: porta 9011 (nao 9001 — porta mudou)
- Search: porta 9002
- Download: porta 9003
- CHD: porta 9004
- Dashboard: `http://127.0.0.1:8767/`
- aria2c: porta 16810, com cookie archive.org carregado
- Speed monitor: `node tools/speed_monitor.js` rodando em background (reinicia aria2c automaticamente)

## Cookie archive.org (IMPORTANTE)

- Conta atual: `kideje5455@ezimb.com` / screenname `impcoll2026z` / senha `Arch2026xK9!mp`
- Cookie em `F:\importre\archive_cookies.txt` (formato Netscape) — NUNCA commitar (secret)
- Para renovar: `node tools/renew_archive_cookie.js`
- Se conta expirar: ver `knowledge/archive_cookie_renewal.md` (criar nova via temp-mail.org + Playwright)
- aria2c usa `--load-cookies=F:\importre\archive_cookies.txt` em `tools/start_aria2c.bat`

## Sessao 2026-07-15 (parte 2) — tarefas completadas

1. **Cookie archive.org renovado** via `ia configure` (internetarchive CLI) — conta nova criada via temp-mail.org
2. **Script `renew_archive_cookie.js`** automatiza login + extracao + restart aria2c
3. **Speed monitor com watchdog** (`tools/speed_monitor.js`) reinicia aria2c quando cai
4. **Diversificacao de fontes:** RR workers ociosos pegam qualquer fonte apos 2 ciclos; queue round-robin entre fontes no modo `any`
5. **114 CHDs renomeados** de serial para `[Nome-do-Jogo]-[SERIAL].chd` via 4 subagents em paralelo
6. **18 duplicatas corrigidas** (subagent usou Copy-Item em vez de Rename-Item)
7. **Knowledge documentado:** archive_cookie_renewal.md, lessons_learned itens 16-18, frustration_log itens 9-11

## Velocidade de download

- Media: ~60-80MB/s (meta: 40MB/s — meta alcancada)
- Picos: 100-114MB/s
- Quedas: aria2c cai ~3-4x por hora, monitor reinicia em ~30s
- Fontes ativas: archive.org, vimm, retrostic, romsdl (4 de 34 plugins)
- Problema: 181 itens pending sem fonte (search nao encontra URL)

## Proximos passos recomendados

- Esperar downloads terminarem (~660 itens restantes)
- Investigar por que 181 itens pending nao tem fontes (search service)
- Adicionar mais fontes aos itens ready (so 4 de 34 plugins tem URLs)
- Renomear SCES-03035.chd (0 bytes — deletar) e SLUS-00169.chd (jogo nao lancado)
- Considerar refatorar funcoes com complexidade cognitiva >25 (18 warnings lint)
- Adicionar testes automatizados para search e download

## Arquivos abertos no IDE

- tools/cdp_extract.js
- tools/read_cookies.js
- .gitignore
- knowledge/workflows/commit.md
- knowledge/frustration_log.md
- knowledge/handover.md

## Notas

- Remote configurado: `origin https://github.com/zaozbr/importre-microservices.git`
- Repositorio: https://github.com/zaozbr/importre-microservices
- Tag local: `v1.0.0`
- Sistema antigo Python em `D:\roms\library\roms\psx\` (importre.py) nao confundir com Node.js em `F:\importre\`
- Regra critica: nunca usar `taskkill /F /IM chdman.exe`
- Workflow de commit completo em `knowledge/workflows/commit.md` (7 passos obrigatórios)
- Queue roda na porta 9011 (nao 9001) — verificar porta atual com netstat
