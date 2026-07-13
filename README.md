# importre-microservices

Sistema de download e conversao de ROMs PSX em Node.js, usando arquitetura de microservicos.

## Arquitetura

- **queue-service** (porta 9001): gerencia queue.json
- **search-service** (porta 9002): busca ROMs em archive.org, coolrom, vimm
- **download-service** (porta 9003): baixa e extrai ROMs usando aria2c
- **chd-service** (porta 9004): converte CUE/BIN/ISO para CHD usando chdman.exe
- **orchestrator** (porta 8767): coordena todos os servicos e serve dashboard

## Dados preservados

- Configuracao, fila e logs: `D:\roms\library\roms\_importre_state\`
- Downloads e CHDs: `D:\roms\library\roms\psx\`
- Duplicados: `D:\roms\duplicados\`
- Temporario CHD: `F:\chd_temp`

## Requisitos

- Node.js 18+
- 7-Zip em `C:\Program Files\7-Zip\7z.exe` (ou defina `SEVEN_ZIP_PATH`)
- `chdman.exe` em `D:\roms\library\roms\psx\chdman.exe`
- aria2c incluido (`F:\importre\aria2c.exe`)

## Uso

```bash
cd F:\importre
npm install
npm start
```

Dashboard: http://127.0.0.1:8767

## Reconstruir fila

```bash
node tools/rebuild-queue.js
```

## Servicos individuais

```bash
npm run queue
npm run search
npm run download
npm run chd
```

## Notas

- archive.org usa HTTP por padrao para contornar bloqueios de HTTPS inspecionados
- Downloads usam aria2c com 16 conexoes; fallback para axios se aria2c falhar
- A fila tem estados separados: pending → searching → ready → downloading → completed/failed
