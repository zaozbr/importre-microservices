# HANDOVER — Importre Microservices

## Data
2026-07-18 (sessao 8 — torrents seletivos + conversao CHD + dashboard de downloads)

## Resumo da sessao
- **Colecao: 6064 CHDs** (+116 desde sessao 7)
- **Torrents seletivos configurados:** 420 arquivos .7z (177 PAL + 243 JP)
- **15 CHDs convertidos** dos torrents e movidos para colecao
- **Dashboard de downloads** criado em `/downloads`
- **Watchdog de performance** rodando em background (target 40MB/s)
- **294 duplicados removidos** da lista de download original

## Sistema
- **Orchestrator (8767):** RODANDO
- **Queue (9011):** RODANDO
- **Search (9002):** RODANDO
- **Download (9003):** RODANDO
- **CHD (9004):** RODANDO
- **Aria2 RPC (6800):** status desconhecido (aria2c standalone para torrents em portas separadas)
- **Torrents aria2c:** 2 instancias (PAL porta 6881-6999, JP porta 6900-6999)
- **Watchdog perf:** rodando em background (perf_watchdog.py)

## Downloads em andamento
- **Torrents seletivos:** 420 arquivos .7z (177 PAL + 243 JP), ~18-32 MB/s
- **archive.org:** 8 jogos na fila (to_download.json)
- **Homebrews:** 31 HBREW faltantes (precisam Playwright para itch.io)
- **TOTAL:** ~454 jogos para baixar

## Torrentes seletivos
- **PAL:** magnet `8d6f0487c9afd39b9ad833254759b8be56281bad` — 177 arquivos selecionados
- **NTSC-J:** magnet `b2a4b46514562c7999354691b15a4528f5b864d6` — 243 arquivos selecionados
- Indices em `F:\importre_state\pal_select.txt` e `jp_select.txt`
- Trackers: 8 UDP + 2 WebSocket + DHT
- 1248 arquivos .7z completos (254GB), mas muitos corrompidos (pieces esparsos)

## Conversao CHD
- Script: `F:\importre_state\convert_torrent_chd.py`
- CHDs vao para `F:\testes` (para teste antes de mover para colecao)
- 15 CHDs convertidos e movidos na sessao 8
- Usuario confirmou "todos ok, pode mover" apos testar

## Dashboard de downloads (NOVO)
- Pagina: `http://127.0.0.1:8767/downloads`
- API: `GET /api/downloads-list`
- HTML: `orchestrator/downloads.html`
- Lista unificada: torrents + aria2 RPC + fila do importre
- Ordenada por progresso, filtros por fonte/status/nome
- Auto-refresh 5s, badges coloridos por fonte
- Link adicionado no shell.html

## Watchdog de performance (NOVO)
- Script: `F:\importre_state\perf_watchdog.py`
- Roda em background, nao bloqueia chat
- Monitora velocidade a cada 30s, target 40MB/s
- Reinicia aria2c se 0 peers por 5+ minutos
- Log: `F:\importre_state\perf_watchdog.log`

## Proximos passos recomendados
1. **Monitorar torrents** — quando terminarem, extrair e converter .7z restantes
2. **Baixar homebrews** — criar plugin Playwright para itch.io/GameJolt
3. **Converter .7z completos** — rodar `convert_torrent_chd.py` periodicamente
4. **Mover CHDs validados** — de `F:\testes` para `D:\roms\library\roms\psx\`
5. **Integrar Ehrgeiz** — ainda baixando via aria2c (background)

## Arquivos criados nesta sessao
- `orchestrator/downloads.html` — pagina de lista de downloads
- `F:\importre_state\perf_watchdog.py` — watchdog de performance
- `F:\importre_state\convert_torrent_chd.py` — conversor torrent -> CHD
- `F:\importre_state\torrent_selective.py` — gerador de indices seletivos
- `F:\importre_state\regen_indices.py` — regenerador de indices sem duplicados
- `F:\importre_state\final_download_list.py` — lista final de downloads
- `F:\importre_state\torrent_match.py` — cruzamento torrent x faltantes
- `F:\importre_state\status.py` — status geral do sistema

## Arquivos modificados
- `orchestrator/index.js` — API /api/downloads-list + rota /downloads
- `orchestrator/shell.html` — link para lista de downloads
- `knowledge/colecao_estado.md` — atualizado com torrents + homebrews + dashboard
- `knowledge/lessons_learned.md` — 6 novas licoes (14-19)
- `knowledge/handover.md` — este arquivo

## Notas
- Remote: origin (github.com)
- CHDs em D:\roms\library\roms\psx (6064 CHDs)
- Regra critica: NUNCA usar taskkill /F /IM chdman.exe
- Regra critica: NUNCA usar taskkill /F /IM aria2c.exe (mata torrents tambem)
- Portas: QUEUE=9011, SEARCH=9002, DOWNLOAD=9003, CHD=9004, ORCHESTRATOR=8767
- Torrents aria2c: portas DHT 6881-6999 (PAL) e 6900-6999 (JP)
