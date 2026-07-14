#!/usr/bin/env python3
"""
Rename all .chd files in D:\roms\library\roms\PSX to the pattern:
  nome-do-jogo-SERIAL.chd

For files WITHOUT a serial in the name, extract the serial from the CHD header
using chdman extractcd, then rename.
"""

import os
import re
import sys
import subprocess
import shutil
import time
import json

PSX_DIR = r"D:\roms\library\roms\PSX"
CHDMAN = r"F:\importre\chdman.exe"
TEMP_DIR = r"F:\chd_temp"
PROGRESS_FILE = r"F:\importre\_rename_progress.json"

# Serial patterns for PSX
SERIAL_PATTERN = re.compile(r'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)-\d{5}', re.I)
# Pattern to search in binary data (PSX serials appear in the CD header)
SERIAL_SEARCH_PATTERN = re.compile(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)[-_](\d{5})', re.I)
# Also try without dash: SLUS01272
SERIAL_SEARCH_PATTERN2 = re.compile(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)(\d{5})', re.I)

INVALID_CHARS = '<>:"/\\|?*'


def sanitize_filename(name):
    """Sanitize a filename: replace spaces with hyphens, remove invalid chars, collapse duplicate hyphens."""
    # Replace spaces with hyphens
    name = name.replace(' ', '-')
    # Remove invalid characters
    for ch in INVALID_CHARS:
        name = name.replace(ch, '')
    # Remove parentheses content that's just noise
    # Collapse multiple hyphens
    while '--' in name:
        name = name.replace('--', '-')
    # Remove leading/trailing hyphens
    name = name.strip('-')
    # Limit to 150 characters (leave room for -SERIAL.chd)
    if len(name) > 150:
        name = name[:150].rstrip('-')
    return name


def build_new_name(game_name, serial):
    """Build the new filename: game-name-SERIAL.chd"""
    clean_name = sanitize_filename(game_name)
    # Serial format: SLUS-01272 (with dash)
    serial_clean = serial.upper().replace('_', '-')
    # Ensure serial has dash
    m = re.match(r'([A-Z]{4})-?(\d{5})', serial_clean)
    if m:
        serial_clean = f"{m.group(1)}-{m.group(2)}"
    new_name = f"{clean_name}-{serial_clean}.chd"
    return new_name


def extract_serial_from_chd(chd_path):
    """Extract the PSX serial from a CHD file by extracting to cue/bin and reading the header."""
    cue_path = os.path.join(TEMP_DIR, "_rn.cue")
    bin_path = os.path.join(TEMP_DIR, "_rn.bin")

    # Clean up any existing temp files
    for p in [cue_path, bin_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass

    try:
        result = subprocess.run(
            [CHDMAN, "extractcd", "-i", chd_path, "-o", cue_path, "-ob", bin_path, "-f"],
            capture_output=True,
            timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    serial = None
    try:
        if os.path.exists(bin_path):
            with open(bin_path, 'rb') as f:
                # Read first 256KB
                data = f.read(256 * 1024)
                # Search for serial pattern with dash or underscore
                matches = SERIAL_SEARCH_PATTERN.findall(data)
                if not matches:
                    # Try without separator
                    matches = SERIAL_SEARCH_PATTERN2.findall(data)

                if matches:
                    # Take the first match
                    prefix, num = matches[0]
                    serial = f"{prefix.decode().upper()}-{num.decode()}"
    except Exception:
        pass
    finally:
        # Clean up temp files
        for p in [cue_path, bin_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

    return serial


def extract_game_name(filename):
    """Extract a clean game name from the current filename."""
    # Remove .chd extension
    name = filename
    if name.lower().endswith('.chd'):
        name = name[:-4]

    # Remove common suffixes/patterns
    # Remove disc info like (Disc 1), [Disc 1], -Disc1
    name = re.sub(r'[\(\[]?\s*[Dd]isc\s*\d+[\)\]]?', '', name)
    name = re.sub(r'-Disc\d+', '', name, flags=re.I)

    # Remove region tags like (USA), (Japan), (Europe), (E), (U), (J)
    name = re.sub(r'[\(\[]\s*(USA|Europe|Japan|U\.S\.A|PAL|NTSC|JPN|EU|US|JP|E|U|J)\s*[\)\]]', '', name, flags=re.I)

    # Remove version tags like (v1.1), (Rev 1)
    name = re.sub(r'[\(\[]\s*(v\d+\.\d+|Rev\s*\d+)\s*[\)\]]', '', name, flags=re.I)

    # Remove (Unl) unofficial tags
    name = re.sub(r'[\(\[]\s*Unl\s*[\)\]]', '', name, flags=re.I)

    # Remove leading underscores
    name = name.lstrip('_')

    return name.strip()


def load_progress():
    """Load progress from file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"processed": [], "renamed": [], "failed": [], "skipped": []}


def save_progress(progress):
    """Save progress to file."""
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, indent=2)
    except:
        pass


def main():
    # Get all .chd files
    all_files = [f for f in os.listdir(PSX_DIR) if f.lower().endswith('.chd')]
    print(f"Total .chd files: {len(all_files)}")

    # Separate files with and without serial
    with_serial = [f for f in all_files if SERIAL_PATTERN.search(f)]
    without_serial = [f for f in all_files if not SERIAL_PATTERN.search(f)]
    print(f"With serial already: {len(with_serial)}")
    print(f"Without serial (need processing): {len(without_serial)}")

    # Load progress
    progress = load_progress()
    processed_set = set(progress["processed"])

    # Filter out already processed
    to_process = [f for f in sorted(without_serial) if f not in processed_set]
    print(f"Already processed: {len(processed_set)}")
    print(f"To process now: {len(to_process)}")
    print()

    # Skip files that are clearly temp/incomplete
    skip_patterns = ['_temp_', '_rn.', 'temp_cue', 'temp_Tony']
    to_process = [f for f in to_process if not any(p in f for p in skip_patterns)]
    print(f"After skipping temp files: {len(to_process)}")
    print()

    count = 0
    renamed_count = 0
    failed_count = 0
    skipped_count = 0

    for filename in to_process:
        count += 1
        chd_path = os.path.join(PSX_DIR, filename)

        # Skip if file doesn't exist anymore (maybe already renamed)
        if not os.path.exists(chd_path):
            progress["skipped"].append({"file": filename, "reason": "file not found"})
            progress["processed"].append(filename)
            save_progress(progress)
            skipped_count += 1
            continue

        # Report progress every 50 files
        if count % 50 == 0:
            print(f"\n=== PROGRESS: {count}/{len(to_process)} processed | {renamed_count} renamed | {failed_count} failed | {skipped_count} skipped ===\n")
            save_progress(progress)

        # Extract serial from CHD header
        serial = extract_serial_from_chd(chd_path)

        if serial:
            # Extract game name from current filename
            game_name = extract_game_name(filename)
            new_name = build_new_name(game_name, serial)
            new_path = os.path.join(PSX_DIR, new_name)

            # Avoid overwriting existing files
            if os.path.exists(new_path) and os.path.normpath(new_path) != os.path.normpath(chd_path):
                # Add a suffix to avoid collision
                base = new_name[:-4]
                i = 2
                while os.path.exists(os.path.join(PSX_DIR, f"{base}_{i}.chd")):
                    i += 1
                new_name = f"{base}_{i}.chd"
                new_path = os.path.join(PSX_DIR, new_name)

            try:
                os.rename(chd_path, new_path)
                print(f"[{count}] RENAMED: {filename[:60]} -> {new_name[:70]}")
                progress["renamed"].append({"old": filename, "new": new_name, "serial": serial})
                renamed_count += 1
            except Exception as e:
                print(f"[{count}] ERROR renaming {filename}: {e}")
                progress["failed"].append({"file": filename, "reason": f"rename error: {e}"})
                failed_count += 1
        else:
            print(f"[{count}] NO SERIAL FOUND: {filename[:70]}")
            progress["failed"].append({"file": filename, "reason": "no serial in header"})
            failed_count += 1

        progress["processed"].append(filename)
        save_progress(progress)

    # Final report
    print("\n" + "=" * 70)
    print(f"FINAL REPORT")
    print(f"=" * 70)
    print(f"Total processed: {count}")
    print(f"Renamed: {renamed_count}")
    print(f"Failed (no serial): {failed_count}")
    print(f"Skipped: {skipped_count}")

    if progress["failed"]:
        print(f"\n--- Files that need web lookup ({len(progress['failed'])}) ---")
        for item in progress["failed"][-50:]:
            print(f"  {item['file']}")

    save_progress(progress)


if __name__ == "__main__":
    main()
