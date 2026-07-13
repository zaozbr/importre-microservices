"""Desativa sites com timeout/403/404 e mantem apenas os que funcionam."""
import json
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")

with open(SITES_PATH, "r", encoding="utf-8") as f:
    sites = json.load(f)

# Sites que funcionam (HTTP 200 no diagnostico)
KEEP_ENABLED = {
    "coolrom": True,
    "retrostic": True,
    "romulation": True,
    "myrient": True,
    "archive_org": True,      # intermitente, mas tentar
    "archive_org_jp": True,   # intermitente, mas tentar
    "retroiso": True,
    "blueroms": True,         # 200 mas resposta curta (JS) - Playwright pode funcionar
    "homebrew": True,
    "psxdatacenter_jp": True, # pode funcionar via Playwright
    "retrostic_jp": True,
}

# Sites para DESATIVAR (timeout/403/404)
DISABLE = {
    "vimm": "timeout",
    "cdromance": "403 blocked",
    "romspedia": "timeout",
    "hexrom": "timeout",
    "psxdatacenter_jp": "timeout no host principal",
    "romsdl": "timeout (DNS redirecionando)",
    "romsretro": "404",
    "romsgames": "404",
    "retromania": "404",
    "consoleroms": "404",
    "edgeemu": "404",
    "romhustler": "banido permanentemente",
    "romsfun": "banido permanentemente",
    "romsbase": "banido permanentemente",
    "emuparadise": "banido permanentemente",
    "romspack": "timeout",
    "totalroms": "timeout",
    "romspure": "timeout",
    "roms2000": "timeout",
    "classicgames": "timeout",
    "retrobit": "timeout",
    "freeroms": "timeout",
}

for key, reason in DISABLE.items():
    if key in sites:
        was = sites[key].get("enabled", False)
        sites[key]["enabled"] = False
        if was:
            print(f"  DESATIVADO: {key} ({reason})")

# Garantir que os bons estao ativados
for key, enable in KEEP_ENABLED.items():
    if key in sites and enable:
        if not sites[key].get("enabled"):
            sites[key]["enabled"] = True
            sites[key]["fail_count"] = 0
            print(f"  ATIVADO: {key}")
        else:
            print(f"  OK: {key} ja ativo")

with open(SITES_PATH, "w", encoding="utf-8") as f:
    json.dump(sites, f, indent=2, ensure_ascii=False)

print("\nResumo:")
enabled = [k for k, v in sites.items() if v.get("enabled")]
print(f"  Sites ativos: {enabled}")
