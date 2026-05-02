#!/usr/bin/env python3
import os
import re
import json

def convert_legacy_ghost():
    md_file = "octo_cyberbrain/ghost/octo_ghost.md"
    json_file = "octo_cyberbrain/ghost/octo_ghost.json"
    
    if not os.path.exists(md_file):
        print(f"⚠️ 找不到舊版 {md_file}，無須遷移。")
        return
        
    print(f"🔄 開始從 {md_file} 遷移遺產至 GHOST 系統...")
    
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
        
    print(f"✅ 成功遷移 {len(kws)} 個關鍵字與 {len(paths)} 條路徑至 {json_file}。")
    print(f"🗑️ 請手動刪除或備份舊版 .md 檔案。")

if __name__ == "__main__":
    convert_legacy_ghost()