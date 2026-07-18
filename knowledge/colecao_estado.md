# Estado da Colecao PSX — Reabsorvivel

> **REABSORVER OBRIGATORIAMENTE a cada prompt.** Estado atual da colecao PSX apos tripla checagem.

## Data de atualizacao
2026-07-18 (sessao 8 — torrents seletivos + conversao CHD + pagina de downloads)

## ⚠️ DEMOS REMOVIDOS — REGRA PERMANENTE
**Demos foram EXCLUIDOS da colecao e da lista de faltantes. NAO baixar demos. NAO incluir demos.**
- Generos excluidos: Demo, Trial, Sample, Taikenban, Preview, Net Yaroze, Jampack, Kiosk, Promotional, Calpis, Pocket Zanmai
- Seriais SLED-* (discos de revista) sao demos e NAO devem ser baixados
- 3 CHDs demo removidos da colecao: Doko-Demo-Issho-Calpis, Jampack-Vol-1, Jampack-Vol-2
- 7 demos SLED-* removidos da lista de faltantes
- 15 arquivos demo removidos de F:\downloads
- **Faltantes agora: 233 (sem demos)**

## Numeros da colecao (TRIPLA CHECAGEM + SEM DEMOS + TORRENTS SELETIVOS)
- **CHDs na colecao principal:** 6064 (em `D:\roms\library\roms\psx\`) — +116 desde sessao 7
- **CHDs em duplicados:** ~2484 (em `D:\roms\duplicados\`, apos mover 80 de volta)
- **Seriais unicos na colecao:** ~4859
- **Total de faltantes catalogados:** 1415
- **Ja na colecao (por serial):** 861
- **Ainda em duplicados (tem versao melhor na colecao):** 119 — NAO precisam voltar
- **Realmente faltando (nao em lugar nenhum):** 435
- **Tem versao alternativa na colecao:** 195
- **UNICOS FALTANTES (lista final, SEM DEMOS):** 233
- **Downloads em andamento (torrents seletivos):** 420 arquivos .7z (177 PAL + 243 JP)
- **Downloads em andamento (archive.org):** 8 jogos na fila
- **Downloads em andamento (homebrews):** 31 HBREW faltantes
- **TOTAL REAL PARA BAIXAR:** ~454 jogos (apos remover 294 duplicados da lista original de 748)

## O que sao "jogos unicos"
Jogos unicos = jogos que faltam na colecao E em duplicados, e NAO tem nenhuma versao alternativa (outra regiao, outra linguagem) ja presente na colecao. Estes sao os jogos que realmente precisam ser baixados.

### Breakdown dos 233 unicos faltantes por regiao (SEM DEMOS):
- **JPN:** 130 — maioria sao jogos japoneses obscuros que nunca sairam do Japao
- **HBREW:** 35 — homebrews, alguns impossiveis de baixar
- **PAL:** 50 — jogos europeus, alguns em alemao/frances/italiano
- **USA:** 18 — jogos americanos faltantes (MAIS PRIORITARIOS)
- ~~DEMO: 7~~ — REMOVIDOS (demos nao fazem parte da colecao)

## Tripla checagem realizada
1. **Checagem 1:** Serial esta na lista de faltantes? (PSX_Colecao_Faltantes.md)
2. **Checagem 2:** Serial nao esta na colecao principal? (scan de D:\roms\library\roms\psx\)
3. **Checagem 3:** Serial nao esta em duplicados? (scan de D:\roms\duplicados\) — 80 seriais encontrados e movidos de volta

### Movimentacao de duplicados (80 seriais movidos de volta)
- 80 seriais que estavam em D:\roms\duplicados foram movidos de volta para a colecao
- Arquivos extras (duplicados dos mesmos seriais) movidos para D:\roms\duplicados\_moved_to_collection
- 119 seriais ainda em duplicados mas com versao melhor/equivalente na colecao (NAO precisam voltar)

## Multi-disco faltantes (discos individuais que faltam)
Apenas **1 disco** confirmado como faltante:
- **SLUS-01276** — Fear Effect 2: Retro Helix (USA) Disc 3
  - Fonte: Romspure (https://romspure.cc/download/fear-effect-2-retro-helix-7945/10)
  - Status: link encontrado, download pendente (protetor de links)
  - Discos 1, 2, 4 ja estao na colecao

## Jogos IMPOSSIVEIS de encontrar/baixar (17 jogos)
| # | Serial | Nome | Motivo |
|---|--------|------|--------|
| 1 | SLPS-00289 | Pile Up March | CANCELADO - nunca lancado para PSX |
| 2 | SLPS-02311 | Knights of Genesis | CANCELADO - nunca lancado para PSX |
| 3 | SLUS-01205 | Kengo | Jogo PS2, nunca teve versao PSX |
| 4 | SLUS-00901 | Motocross Madness | CANCELADO para PSX |
| 5 | HBREW-021 | Zia and the Goddesses of Magic | Homebrew pago ($15 USD), sem versao gratuita |
| 6 | HBREW-041 | Half-Life PSX | Projeto em desenvolvimento, sem download publico |
| 7 | SLPS-01259 | Tokyo 23Ku Seifuku-Wars | Jogo raro JP nao encontrado em nenhuma fonte |
| 8 | SLPS-02366 | Tall Infinite | Jogo raro JP nao encontrado em nenhuma fonte |
| 9 | SLES-01082 | Dodge'm Arena | Jogo raro PAL nao encontrado em nenhuma fonte |
| 10 | SLES-03235 | klzm2 | Jogo raro PAL nao encontrado em nenhuma fonte |
| 11 | SLES-02693 | Gute Zeiten Schlechte Zeiten Vol 1 | Jogo raro PAL nao encontrado |
| 12 | SLPS-01224 | Unknown JP | (na lista de 240? verificar) |
| 13 | SLPM-86880 | Unknown JP | (na lista de 240? verificar) |
| 14 | SLPS-02346 | Amerzone (JP?) | (na lista de 240? verificar) |
| 15 | yicestar-jap-UNKNOWN | Yopaz IceStar (JP) | Serial invalido/placeholder |
| 16 | yicestar-ntsc-UNKNOWN | Yopaz IceStar (NTSC) | Serial invalido/placeholder |
| 17 | SBL0-UNKNOWN | SBL0 Unknown | Serial invalido/placeholder |

## Mapeamento multi-regiao
Arquivo: `D:\roms\library\roms\mapeamento_multi_regiao.md`
- 101 grupos de jogos com versoes em 2+ regioes diferentes
- Aliases cross-linguagem aplicados: Biohazard→Resident Evil, Rockman→Mega Man, etc.

## Arquivos de analise
- `F:\importre_state\lista_final_faltantes.json` — LISTA FINAL apos tripla checagem
- `F:\importre_state\tripla_checagem.json` — resultado da tripla checagem
- `F:\importre_state\move_classification_v2.json` — classificacao dos arquivos movidos
- `F:\importre_state\move_results.json` — resultado da movimentacao
- `F:\importre_state\serial_to_title.json` — lookup de 5260 seriais
- `D:\roms\library\roms\PSX_Colecao_Faltantes.md` — lista original de faltantes (1415 jogos)
- `D:\roms\library\roms\mapeamento_multi_regiao.md` — mapeamento cross-regiao

## Regras de deduplicacao
- Prioridade: USA > PAL > OTHER > JPN > DEMO > HBREW
- 1 versao por jogo (exceto multi-disco)
- Aliases cross-linguagem: Biohazard=Resident Evil, Rockman=Mega Man, etc.
- Multi-disco: cada disco e unico (nao deduplicar)
- Arquivos "sem titulo" (chd-SERIAL.chd): usar lookup serial_to_title.json

## Subagents
- **SUBAGENTS DEVEM SER EM SERIE, NUNCA PARALELOS** (regra do usuario)
- Lancar um de cada vez, esperar terminar antes de lancar o proximo

## Torrents Seletivos (sessao 8 — 2026-07-18)

### Fontes torrent
- **PAL:** `magnet:?xt=urn:btih:8d6f0487c9afd39b9ad833254759b8be56281bad` — Sony PlayStation (PAL) [Redump]
- **NTSC-J:** `magnet:?xt=urn:btih:b2a4b46514562c7999354691b15a4528f5b864d6` — Sony PlayStation (NTSC-J) [Redump]
- Arquivos .torrent salvos em `F:\downloads\psx_torrents\`
- Trackers: 8 UDP + 2 WebSocket (openbittorrent, opentrackr, stealth, tiny-vps, explodie, moeco, dler, btorrent, openwebtorrent)
- DHT habilitado (`--enable-dht=true`, portas 6881-6999 e 6900-6999)

### Download seletivo (--select-file)
- Torrent original: 6932 arquivos .7z (842GB PAL + ~600GB JP)
- Cruzamento com faltantes: so 420 arquivos necessarios (177 PAL + 243 JP)
- 294 duplicados removidos (jogos que ja temos na colecao)
- aria2c com `--select-file=idx1,idx2,...` baixa apenas os arquivos selecionados
- Indices salvos em `F:\importre_state\pal_select.txt` e `jp_select.txt`

### Conversao torrent -> CHD
- Script: `F:\importre_state\convert_torrent_chd.py`
- Extrai .7z com 7-Zip, converte .cue/.bin com chdman
- CHDs convertidos vao para `F:\testes` (para teste antes de mover para colecao)
- Apos confirmacao do usuario, CHDs sao movidos para `D:\roms\library\roms\psx\`
- 15 CHDs convertidos e movidos na sessao 8

### Watchdog de performance
- Script: `F:\importre_state\perf_watchdog.py`
- Monitora velocidade a cada 30s, target 40MB/s
- Reinicia aria2c se 0 peers por 5+ minutos
- Log em `F:\importre_state\perf_watchdog.log`

### Problema: .7z incompletos
- Torrent baixa pieces inteiros (16MB cada) que podem conter dados de arquivos nao-selecionados
- Arquivos .7z podem ter o tamanho final mas conteudo incompleto/corrompido
- 7-Zip retorna "Can't open as archive" para arquivos corrompidos
- Arquivos sem .aria2 control file podem ainda estar corrompidos (pieces esparsos)
- Solucao: tentar extrair, pular se falhar (returncode != 0)

## Homebrews PSX (sessao 8)

### Fonte: psxhomebrewgames.com
- 28 homebrews listados no site
- 12 ja estavam na colecao
- 16 faltantes identificados
- 12 dos 16 faltantes sao Demo/Alpha/WIP (mas homebrews NAO seguem a regra de exclusao de demos — sao projetos independentes)

### Lista de 35 HBREW faltantes (lista_final_faltantes.json)
- Inclui os 16 do site + 19 outros HBREW catalogados
- Fontes de download: itch.io (requer Playwright), GameJolt, GitHub releases
- itch.io: pagina dinamica, botao "Download" abre modal com link direto
- GameJolt: URL direta para download em alguns casos
- GitHub: muitos repositorios sem releases publicadas

### Homebrews impossiveis
- HBREW-021 (Zia and the Goddesses of Magic): pago $15 USD, sem versao gratuita
- HBREW-041 (Half-Life PSX): projeto em desenvolvimento, sem download publico
- HBREW-043: sem fonte conhecida

### Downloads de homebrews em F:\downloads
- `F:\downloads\homebrews\` — zips baixados manualmente
- `F:\downloads\itch\` — zips baixados do itch.io (game-XXXXX.zip)
- `F:\downloads\itch_test\` e `itch_test2\` — testes de download do itch.io

## Dashboard de Downloads (sessao 8)

### Nova pagina: /downloads
- HTML standalone em `orchestrator/downloads.html`
- API: `GET /api/downloads-list` no orchestrator
- Lista unificada: torrents (PAL + NTSC-J) + aria2 RPC + fila do importre
- Ordenada por progresso (maior primeiro)
- Filtros: nome/serial, fonte, status, esconder completos
- Auto-refresh a cada 5 segundos
- Badges coloridos por fonte (torrent-PAL azul, torrent-NTSC-J laranja, archive.org verde, etc)
- Barras de progresso visuais com cores (verde >=100%, amarelo >=50%, laranja >0%, cinza 0%)
- Link adicionado no shell.html ("LISTA DE DOWNLOADS")
