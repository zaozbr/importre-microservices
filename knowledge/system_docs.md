# Importre Microservices — Documentacao do Sistema

## Visao geral

Sistema Node.js de download e conversao de ROMs PSX, usando arquitetura de microservicos coordenados por um orchestrator.

## Servicos

| Servico | Porta | Responsabilidade |
|---------|-------|------------------|
| Orchestrator | 8767 | Coordena servicos, serve dashboard, expoe API de controle |
| Queue | 9011 | Gerencia fila (`queue.json`), estados e reprocessamento |
| Search | 9002 | Busca ROMs em multiplas fontes via plugins |
| Download | 9003 | Resolve paginas de download e baixa com aria2c |
| CHD | 9004 | Converte CUE/BIN/ISO para CHD com chdman.exe |
| AriaNg | 16801 | Interface web do aria2 com proxy RPC e hack de auto-descoberta |

## Diretorios importantes

- `F:\importre\` — codigo-fonte Node.js
- `F:\importre_state\` — fila, caches, logs, indices (estado runtime)
- `D:\roms\library\roms\psx\` — downloads e CHDs finais
- `F:\chd_temp\` — temporario CHD
- `F:\testes\` — CHDs convertidos aguardando validacao manual
- `F:\importre\safe_point\` — backups e safe points do workflow de commit
- `C:\Users\Usuario\AppData\Roaming\devin\skills\commit\SKILL.md` — skill global /commit

## Arquitetura de plugins de fontes

Local: `services/search/plugins/`

Cada plugin exporta:
- `name`: nome da fonte
- `matchType`: `serial`, `title` ou `index`
- `needsMultiChunk`: boolean
- `priority`: ordem de tentativa (menor = primeiro)
- `enabled`: boolean
- `search(serial, title)`: retorna array de `{ site, url, title, size? }`

Plugins atuais: coolrom, vimm, archive.org, archive.org-jp, archive.org-extra, retroiso, retrostic, romsdl, hexrom, myrient, homebrew, psxdatacenter, romspedia, romsgames, retromania, consoleroms, romulation, romsretro, blueroms, freeroms, romspure, roms2000, classicgames, retrogames.games, retrogames.cc, playretrogames, oldiesnest, google-fallback.

## Download

- `aria2c` e usado por padrao com 16 conexoes.
- `archive.org` usa 32 conexoes.
- Paginas de download sao resolvidas genericamente em `services/download/index.js`.

## Dashboard

- URL: `http://127.0.0.1:8767/`
- Micro-frontend: iframes para cada servico.
- Ordem atual: fila (altura 680px), busca, download, chd, log.

## Estados da fila

`pending -> searching -> ready -> downloading -> completed/failed`

## Controle

- `GET /api/control/pause`
- `GET /api/control/resume`
- `GET /api/control/restart`
- `GET /api/control/stop`
- `POST /api/reprocess-failures`

## Regras de comportamento

- Nunca usar `.` (ponto) em caminhos absolutos ou comandos `exec`.
- Reabsorver `AGENTS.md`, `knowledge/lessons_learned.md`, `knowledge/workflows/commit_workflow.md`, `knowledge/handover.md` antes de cada prompt.
