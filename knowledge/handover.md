# Handover — Importre Microservices

**Data:** 2026-07-16 (sessao 3)
**Sistema:** Rodando — 377/486 completados (78%)

## Estado atual

- Orchestrator: porta 8767
- Queue: porta 9011
- Search: porta 9002
- Download: porta 9003
- CHD: porta 9004
- Dashboard: `http://127.0.0.1:8767/`
- aria2c: porta 6800, com cookie archive.org carregado
- AriaNg: porta 16801 (proxy RPC funcionando, hack injetado)
- 9 torrents via magnet adicionados ao aria2 (0 peers — DHT sem trackers funcionais)

## Cookie archive.org (IMPORTANTE)

- Conta atual: `kideje5455@ezimb.com` / screenname `impcoll2026z` / senha `Arch2026xK9!mp`
- Cookie em `F:\importre\archive_cookies.txt` (formato Netscape) — NUNCA commitar (secret)
- Para renovar: `node tools/renew_archive_cookie.js`
- Se conta expirar: ver `knowledge/archive_cookie_renewal.md`
- **STATUS:** Cookie valido, mas IP bloqueado por rate limiting. Necessario reiniciar router ou ativar VPN.

## archive.org — IP BLOQUEADO (CRITICO)

- Todos os endpoints do archive.org (metadata, search, download) retornam timeout (HTTP 000 apos 15s)
- Ping para archive.org (207.241.224.2) falha (perda de pacotes)
- Bloqueio por IP, nao por cookie
- Torrents via magnet tambem nao funcionam (trackers bloqueiam o IP)
- Sites web alternativos (retrostic, romsdl, vimm) funcionam mas caches nao tem os seriais pending
- myrient.com e parked domain (extinto)
- **ACAO NECESSARIA:** Reiniciar router/modem para pegar IP novo OU ativar VPN

## Queue

- completed: 377
- pending: 109
- searching: 40
- ready: 0
- downloading: 0
- failed: 0

## Sessao 2026-07-16 (sessao 3) — tarefas completadas

1. **Diagnostico de download stall:** downloads pararam porque archive.org bloqueou o IP por rate limiting. Confirmado via curl (HTTP 000), ping (perda de pacotes) e tracert.
2. **9 torrents via magnet adicionados ao aria2:** tentativa de contornar bloqueio via DHT, mas 0 peers encontrados (trackers tambem bloqueiam IP).
3. **DHT entry points e trackers adicionados:** router.bittorrent.com:6881 + 8 trackers UDP. Sem efeito (IP bloqueado).
4. **Teste de sites web alternativos:** retrostic (online, cache nao tem seriais), romspedia (online, busca nao encontra jogos), vimm (online, URL de busca mudou), consoleroms (404), myrient (parked domain), cdromance (403).
5. **Caches locais verificados:** archive_jp_name_index (7625), retrostic_cache (556), romsdl_cache (556), vimm_cache (1287) — nenhum dos 109 seriais pending esta em nenhum cache.
6. **41 warnings de lint corrigidos:** 2 subagents em paralelo (batch 1: services/download, batch 2: tools). Zero warnings agora. Zero erros. 200 testes passing.
7. **Commit + push:** 2 commits enviados (fdc6166 + 1056203) para origin/master.
8. **Skill global /commit criada:** `%APPDATA%\devin\skills\commit\SKILL.md` com workflow completo de 8 passos (documentar, backup, safe point, lint, test, commit, push, contexto). Trigger mapeado em `global_rules.md` para disparar quando usuario digitar `commit!`.
9. **Workflow de commit expandido:** passo 1 (DOCUMENTAR) agora tem 7 sub-passos detalhados cobrindo lessons_learned, frustration_log, handover, system_docs, TODO, AGENTS.md e shortcomings do Devin.

## Velocidade de download

- Media: 0 MB/s (archive.org bloqueado)
- Picos: 0 MB/s
- Meta: 40MB/s (nao alcancada — bloqueio de IP)
- Para voltar a baixar: reiniciar router ou ativar VPN

## Proximos passos recomendados

1. **REINICIAR ROUTER ou ATIVAR VPN** para desbloquear archive.org
2. Apos desbloqueio, o search service voltara a encontrar fontes para os 109 itens pending
3. Verificar se os 9 torrents via magnet comecam a encontrar peers apos desbloqueio
4. Considerar adicionar mais seriais aos caches locais (retrostic, romsdl, vimm) para reduzir dependencia do archive.org
5. Investigar plugins web com busca online real (nao so cache) para JP seriais (SLPM, SLPS, SCPS)
6. Considerar refatorar plugins de search para logar warnings quando archive.org timeout (silencioso hoje)

## Arquivos abertos no IDE

- tools/archive_login.js
- services/download/index.js
- services/download/chd_worker.js
- tools/process_duplicados.js
- tools/unecm.js
- C:\Users\Usuario\.windsurf\global_rules.md
- C:\Users\Usuario\AppData\Roaming\devin\skills\commit\SKILL.md

## Notas

- Remote configurado: `origin https://github.com/zaozbr/importre-microservices.git`
- Repositorio: https://github.com/zaozbr/importre-microservices
- Sistema antigo Python em `D:\roms\library\roms\psx\` (importre.py) nao confundir com Node.js em `F:\importre\`
- Regra critica: nunca usar `taskkill /F /IM chdman.exe`
- Workflow de commit completo em `knowledge/workflows/commit.md` (7 passos obrigatórios)
- Skill global `/commit` em `%APPDATA%\devin\skills\commit\SKILL.md` executa workflow completo
- Queue roda na porta 9011 (nao 9001)
- Lint: 0 erros, 0 warnings (corrigido nesta sessao)
- Testes: 200 passing, 1 pending, 0 failing
