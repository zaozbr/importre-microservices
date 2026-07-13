# importre-lite

Orquestrador leve em Node.js para executar `importre` (download de ROMs PSX) e `chdman` (conversao para CHD) a partir de `F:\importre`.

## Dados preservados

- Configuracao, fila e logs: `D:\roms\library\roms\_importre_state\`
- Downloads e CHDs: `D:\roms\library\roms\psx\`
- Duplicados: `D:\roms\duplicados\`

Nada foi movido. Os scripts Python originais foram copiados para cá e sao executados a partir deste repo.

## Uso

```bash
cd F:\importre
npm start
```

Isso inicia:
- `importre.py` em http://127.0.0.1:8765
- `_chd_convert_v2.py` em http://127.0.0.1:8766
- Orquestrador Node.js em http://127.0.0.1:8767

## Comandos

- `npm start` — inicia tudo
- `npm run importre` — so importre
- `npm run chd` — so conversor CHD
- `npm run status` — alias para `npm start` (status via http://127.0.0.1:8767/status)

## Leveza

O orquestrador usa Node.js apenas para gerenciar subprocessos Python. Os executaveis (`importre.py`, `_chd_convert_v2.py`, `chdman.exe`) rodam como processos filhos. Workers reduzidos para 20 importre / 2 CHD por padrao.
