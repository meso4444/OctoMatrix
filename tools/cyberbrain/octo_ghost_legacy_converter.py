#!/usr/bin/env python3
import os
import re
import json

def convert_legacy_ghost():
    md_file = "octo_cyberbrain/ghost/octo_ghost.md"
    json_file = "octo_cyberbrain/ghost/octo_ghost.json"
    
    if not os.path.exists(md_file):
        print(f"⚠️ Legacy {md_file} not found, no migration needed.")
        return

    print(f"🔄 Starting migration from {md_file} to GHOST system...")

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    kws = set()
    paths = set()

    # Extract KW
    for match in re.finditer(r'\[KW:\s*(.+?)\]', content):
        items = match.group(1).split(',')
        kws.update([i.strip() for i in items if i.strip()])

    # Extract PATH
    for match in re.finditer(r'\[PATH:\s*(.+?)\]', content):
        paths.add(match.group(1).strip())

    ghost_data = {
        "keywords": list(kws),
        "file_paths": list(paths),
        "semantic_outline": []
    }

    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(ghost_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Successfully migrated {len(kws)} keywords and {len(paths)} paths to {json_file}.")
    print(f"🗑️ Please manually delete or backup the old .md file.")

if __name__ == "__main__":
    convert_legacy_ghost()