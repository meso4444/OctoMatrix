#!/usr/bin/env python3
# Copyright 2026 meso4444
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import glob
import subprocess
from datetime import datetime

def convert_legacy_ghost():
    # Find all .md files in the current directory
    md_files = glob.glob("*.md")
    
    if not md_files:
        print("⚠️ No .md files found in the current directory, nothing to convert.")
        return
        
    # Sort files by modification time (oldest to newest)
    md_files.sort(key=os.path.getmtime)
    
    print(f"🔄 Starting to merge {len(md_files)} .md files chronologically into Shell compressed log...")
    
    # Generate standard filename date
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    target_file = f"octo_shell.log.{ts}.zst"
    
    # Merge and compress
    try:
        # Use zstd compression via standard input
        zstd_process = subprocess.Popen(['zstd', '-c', '-', '-o', target_file], stdin=subprocess.PIPE)
        
        for md_file in md_files:
            print(f"   - Processing: {md_file}")
            # Add filename as a separator marker
            header = f"\n\n{'='*50}\n[Archive: {md_file}]\n{'='*50}\n\n"
            zstd_process.stdin.write(header.encode('utf-8'))
            
            with open(md_file, 'rb') as f:
                while chunk := f.read(8192):
                    zstd_process.stdin.write(chunk)
                    
        zstd_process.stdin.close()
        zstd_process.wait()
        
        if zstd_process.returncode == 0:
            print(f"✅ Successfully merged and compressed legacy .md files to: {target_file}")
            print(f"🗑️ Please verify the content, then manually delete or archive the original .md files.")
        else:
            print(f"❌ Compression error occurred, zstd exit code: {zstd_process.returncode}")
            
    except FileNotFoundError:
         print("❌ zstd command not found, please ensure the zstd package is installed.")
    except Exception as e:
         print(f"❌ An unknown error occurred: {e}")

if __name__ == "__main__":
    convert_legacy_ghost()