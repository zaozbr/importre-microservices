#!/usr/bin/env python3
"""Resolve DuckStation shortcut and find exe."""
import subprocess, os, struct

# Method 1: Read .lnk file manually
lnk_path = r"C:\Users\Usuario\Desktop\DuckStation.lnk"
if os.path.exists(lnk_path):
    with open(lnk_path, "rb") as f:
        data = f.read()
    # Try to find path in the lnk file (look for :\\ pattern)
    text = data.decode("utf-16-le", errors="replace")
    import re
    paths = re.findall(r'[A-Z]:\\[^\x00]+\.exe', text)
    if paths:
        print(f"LNK paths: {paths}")
    # Also try ASCII
    text2 = data.decode("ascii", errors="replace")
    paths2 = re.findall(r'[A-Z]:\\[^\x00]+\.exe', text2)
    if paths2:
        print(f"LNK ASCII paths: {paths2}")

# Method 2: Search common locations
search_paths = [
    r"C:\Program Files\DuckStation",
    r"C:\Program Files (x86)\DuckStation",
    r"D:\DuckStation",
    r"D:\Programs\DuckStation",
    r"C:\Users\Usuario\AppData\Local\DuckStation",
    r"C:\Users\Usuario\AppData\Local\Programs\DuckStation",
    r"C:\Games\DuckStation",
    r"D:\Games\DuckStation",
    r"D:\roms\DuckStation",
    r"D:\roms\library\DuckStation",
]
for sp in search_paths:
    if os.path.exists(sp):
        for root, dirs, files in os.walk(sp):
            for f in files:
                if "duckstation" in f.lower() and f.endswith(".exe"):
                    print(f"FOUND: {os.path.join(root, f)}")

# Method 3: Check Documents\DuckStation for settings (might have install path)
duck_dir = r"C:\Users\Usuario\Documents\DuckStation"
if os.path.exists(duck_dir):
    print(f"\nDuckStation dir exists: {duck_dir}")
    for f in os.listdir(duck_dir):
        print(f"  {f}")
    # Check settings file
    settings = os.path.join(duck_dir, "settings.ini")
    if os.path.exists(settings):
        with open(settings, "r", encoding="utf-8", errors="replace") as sf:
            content = sf.read()
        # Look for any path references
        for line in content.splitlines():
            if ".exe" in line.lower() or "path" in line.lower() or "dir" in line.lower():
                print(f"  SETTING: {line[:150]}")
