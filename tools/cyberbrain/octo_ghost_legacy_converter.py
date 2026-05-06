#!/usr/bin/env python3
import os
import glob
import subprocess
from datetime import datetime

def convert_legacy_ghost():
    # 尋找當前目錄下的所有 .md 檔案
    md_files = glob.glob("*.md")
    
    if not md_files:
        print("⚠️ 當前目錄找不到任何 .md 檔案，無須轉換。")
        return
        
    # 依據檔案修改時間 (由舊到新) 進行排序
    md_files.sort(key=os.path.getmtime)
    
    print(f"🔄 開始依新舊順序整併 {len(md_files)} 個 .md 檔案至 Shell 壓縮日誌...")
    
    # 建立目標資料夾
    target_dir = "octo_cyberbrain/shell"
    os.makedirs(target_dir, exist_ok=True)
    
    # 產生標準檔名日期
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    target_file = os.path.join(target_dir, f"octo_shell.log.{ts}.zst")
    
    # 整併與壓縮
    try:
        # 使用 zstd 透過標準輸入進行壓縮
        zstd_process = subprocess.Popen(['zstd', '-c', '-', '-o', target_file], stdin=subprocess.PIPE)
        
        for md_file in md_files:
            print(f"   - 處理: {md_file}")
            # 加入檔名作為分隔標記
            header = f"\n\n{'='*50}\n[Archive: {md_file}]\n{'='*50}\n\n"
            zstd_process.stdin.write(header.encode('utf-8'))
            
            with open(md_file, 'rb') as f:
                while chunk := f.read(8192):
                    zstd_process.stdin.write(chunk)
                    
        zstd_process.stdin.close()
        zstd_process.wait()
        
        if zstd_process.returncode == 0:
            print(f"✅ 成功將舊版 .md 檔案整併並壓縮至: {target_file}")
            print(f"🗑️ 請確認內容無誤後，手動刪除或歸檔原始的 .md 檔案。")
        else:
            print(f"❌ 壓縮過程發生錯誤，zstd 退出碼: {zstd_process.returncode}")
            
    except FileNotFoundError:
         print("❌ 找不到 zstd 指令，請確定系統已安裝 zstd 套件。")
    except Exception as e:
         print(f"❌ 發生未知的錯誤: {e}")

if __name__ == "__main__":
    convert_legacy_ghost()