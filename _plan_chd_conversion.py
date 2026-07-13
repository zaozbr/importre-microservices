"""
Analisa a lista de jogos sem CHD e cria plano de conversao:
1. Filtra itens "nao-conversivel" (cue_only sem bin)
2. Filtra duplicados (mesmo jogo com e sem sufixo -nao-conversivel)
3. Classifica por tipo de acao: converter, buscar_chd, ignorar
4. Gera planilha de processamento
"""
import json, sys, os, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX_DIR = Path(r'D:\roms\library\roms\psx')
CHD_TEMP = Path(r'F:\chd_temp')
DUPLICADOS = Path(r'D:\roms\library\roms\psx\duplicados')

def main():
    with open(PSX_DIR / '_missing_chd_list.json', 'r', encoding='utf-8') as f:
        missing = json.load(f)
    
    print(f'Total bruto: {len(missing)}')
    
    # Classificar
    converter = []      # Tem fonte valida (bin+cue, img, iso, ecm)
    buscar_chd = []     # Marcado como nao-conversivel ou cue_only sem bin
    ignorar = []        # Arquivos tiny (0 bytes) ou duplicados
    
    seen_names = set()
    
    for item in missing:
        base = item['base_name']
        stype = item['source_type']
        size = item['total_size']
        
        # Remover sufixo -nao-conversivel para dedup
        base_clean = base.replace('-nao-conversivel', '')
        
        # Se ja vimos o nome limpo, pular (duplicado)
        key = base_clean.lower()
        if key in seen_names:
            # Verificar se o atual tem -nao-conversivel e o anterior nao
            # Nesse caso, manter o sem sufixo
            if '-nao-conversivel' in base:
                ignorar.append({**item, 'reason': 'duplicado_nao_conversivel'})
                continue
            else:
                # Remover o anterior (que tinha -nao-conversivel) e adicionar este
                # Procurar e remover
                for i, c in enumerate(converter):
                    if c['base_name'].replace('-nao-conversivel', '').lower() == key:
                        ignorar.append({**converter[i], 'reason': 'substituido_por_versao_limpa'})
                        converter.pop(i)
                        break
                for i, b in enumerate(buscar_chd):
                    if b['base_name'].replace('-nao-conversivel', '').lower() == key:
                        ignorar.append({**buscar_chd[i], 'reason': 'substituido_por_versao_limpa'})
                        buscar_chd.pop(i)
                        break
        
        seen_names.add(key)
        
        # Classificar
        if '-nao-conversivel' in base:
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif stype == 'cue_only' and size < 1024:
            # cue sem bin = fonte faltando
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif size < 1024 and stype == 'mds_ccd':
            # ccd/mds sem img = fonte faltando
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif size < 1024:
            ignorar.append({**item, 'reason': 'arquivo_vazio'})
        else:
            converter.append({**item, 'action': 'converter'})
    
    # Ordenar converter por tamanho (menores primeiro = converte mais rapido)
    converter.sort(key=lambda x: x['total_size'])
    buscar_chd.sort(key=lambda x: x['total_size'])
    
    print(f'\nClassificacao:')
    print(f'  Converter (fonte valida): {len(converter)}')
    print(f'  Buscar CHD pronto:        {len(buscar_chd)}')
    print(f'  Ignorar (vazio/dup):      {len(ignorar)}')
    
    total_conv = sum(i['total_size'] for i in converter)
    print(f'  Tamanho total converter:  {total_conv/1024/1024/1024:.1f} GB')
    
    # Estatisticas por tipo
    by_type = {}
    for item in converter:
        t = item['source_type']
        by_type[t] = by_type.get(t, 0) + 1
    print(f'\nConverter por tipo:')
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f'  {t:15s}: {c}')
    
    # Listar buscar_chd
    print(f'\n{"=" * 70}')
    print(f'  JOGOS PARA BUSCAR CHD PRONTO ({len(buscar_chd)})')
    print(f'{"=" * 70}')
    for i, item in enumerate(buscar_chd):
        print(f'  [{i+1:3d}] {item["base_name"][:60]}')
    
    # Listar converter (primeiros 20 e ultimos 20)
    print(f'\n{"=" * 70}')
    print(f'  JOGOS PARA CONVERTER ({len(converter)})')
    print(f'{"=" * 70}')
    print(f'\nPrimeiros 20 (menores):')
    for i, item in enumerate(converter[:20]):
        size_mb = item['total_size'] / 1024 / 1024
        print(f'  [{i+1:3d}] {size_mb:8.1f}MB | {item["source_type"]:10s} | {item["base_name"][:50]}')
    print(f'\nUltimos 20 (maiores):')
    for i, item in enumerate(converter[-20:]):
        size_mb = item['total_size'] / 1024 / 1024
        idx = len(converter) - 20 + i + 1
        print(f'  [{idx:3d}] {size_mb:8.1f}MB | {item["source_type"]:10s} | {item["base_name"][:50]}')
    
    # Salvar listas separadas
    with open(PSX_DIR / '_chd_converter_list.json', 'w', encoding='utf-8') as f:
        json.dump(converter, f, ensure_ascii=False, indent=2)
    with open(PSX_DIR / '_chd_buscar_list.json', 'w', encoding='utf-8') as f:
        json.dump(buscar_chd, f, ensure_ascii=False, indent=2)
    with open(PSX_DIR / '_chd_ignorar_list.json', 'w', encoding='utf-8') as f:
        json.dump(ignorar, f, ensure_ascii=False, indent=2)
    
    print(f'\nListas salvas:')
    print(f'  _chd_converter_list.json ({len(converter)} itens)')
    print(f'  _chd_buscar_list.json ({len(buscar_chd)} itens)')
    print(f'  _chd_ignorar_list.json ({len(ignorar)} itens)')


if __name__ == '__main__':
    main()
