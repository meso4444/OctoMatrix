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

from flask import Flask, request, jsonify
import json
import os
import requests
import logging
import subprocess
from datetime import datetime
from config import (
    SYS_PREFIX,
    TELEGRAM_GATEWAY_PORT,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    AGENTS, CUSTOM_MENU
)

# 日誌配置
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# OctoMatrix Router 配置
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = os.getenv('ROUTER_PORT', '12210')
ROUTER_URL = f"http://{ROUTER_HOST}:{ROUTER_PORT}"
ROUTER_INJECT_ENDPOINT = f"{ROUTER_URL}/inject"
ROUTER_STATUS_ENDPOINT = f"{ROUTER_URL}/status"

class ImageManager:
    """圖片管理員：負責從各平臺下載圖片至指定 Agent 目錄"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def download_telegram_photo(self, file_id, agent_name):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            # 獲取檔案資訊
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
            resp = requests.get(url, timeout=10).json()
            if not resp.get('ok'): return None

            file_path = resp['result']['file_path']
            ext = os.path.splitext(file_path)[1] or ".jpg"
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_id[:8]}{ext}"
            local_path = os.path.join(agent_img_dir, filename)

            # 下載實體
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            content = requests.get(download_url, timeout=20).content
            with open(local_path, 'wb') as f:
                f.write(content)

            # telegram_gateway.py 以啟動服務的使用者身分執行，下載出來的檔案預設歸屬
            # 該使用者；但檔案最終是交給對應的 Agent（以自己的 agent_<name> OS 使用者
            # 身分透過 su - 執行，見 setup_agent_env.py 的 spawn_agent()）讀取處理，
            # 故下載完成後須將所有權轉移給該 Agent，否則會讀不到檔案。
            agent_user = f"agent_{agent_name.lower()}"
            subprocess.run(["sudo", "chown", f"{agent_user}:{agent_user}", local_path], check=True)

            logger.info(f"📸 圖片已下載至 [{agent_name}]: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ 圖片下載失敗: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

def get_current_agent():
    """向 Router 詢問當前活躍 Agent"""
    try:
        resp = requests.get(ROUTER_STATUS_ENDPOINT, timeout=3)
        if resp.status_code == 200:
            return resp.json().get('current_agent', AGENTS[0]['name'])
    except: pass
    return AGENTS[0]['name']

def send_message_with_keyboard(chat_id, text, kb): 
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id, 
        'text': text, 
        'parse_mode': 'HTML', 
        'reply_markup': json.dumps({
            'keyboard': kb, 
            'resize_keyboard': True, 
            'one_time_keyboard': True
        })
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        logger.error(f"❌ 發送選單訊息失敗: {e}")

def show_control_menu(chat_id):
    if not CUSTOM_MENU: return
    menu_message = f"🎮 <b>OctoMatrix  系統控制選單</b>\n\n請選擇操作項目："
    keyboard = []
    for row in CUSTOM_MENU:
        keyboard_row = []
        for item in row:
            label = item.get('label') if isinstance(item, dict) else item
            keyboard_row.append(str(label))
        keyboard.append(keyboard_row)
    send_message_with_keyboard(chat_id, menu_message, keyboard)

def forward_to_router(content, user_id, username, metadata=None):
    try:
        payload = {
            'source': 'telegram',
            'user_id': str(user_id),
            'username': username,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        resp = requests.post(ROUTER_INJECT_ENDPOINT, json=payload, timeout=5)
        return resp.json() if resp.status_code == 200 else {'status': 'error'}
    except: return {'status': 'error'}

@app.route('/health', methods=['GET'])
def health_check(): return 'OK', 200

@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    try:
        webhook_data = request.get_json()
        if not webhook_data or 'message' not in webhook_data:
            return jsonify({'status': 'ok'})

        msg_data = webhook_data['message']
        chat_id = str(msg_data.get('chat', {}).get('id', ''))
        user_id = msg_data.get('from', {}).get('id')
        username = msg_data.get('from', {}).get('username', f"user_{user_id}")
        text = msg_data.get('text', '')

        # 👑 選單攔截邏輯 (確保 chat_id 已賦值)
        if text in ['/start', '/menu', '菜單']:
            show_control_menu(chat_id)
            return jsonify({'status': 'ok'})

        # 安全檢查
        if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
            return jsonify({'status': 'unauthorized'}), 403

        if text:
            forward_to_router(text, user_id, username)
        
        # 📸 處理圖片
        elif 'photo' in msg_data:
            current_agent = get_current_agent()
            photo_array = msg_data['photo']
            best_photo = photo_array[-1] # 取解析度最高的
            file_id = best_photo['file_id']
            
            local_path = image_manager.download_telegram_photo(file_id, current_agent)
            if local_path:
                caption = msg_data.get('caption', '').strip()
                img_prompt = f"{SYS_PREFIX}請處理這張圖片，檔案位於: `{local_path}`"
                
                if caption:
                    img_prompt += f"\n\n用戶的說明/提問：\n{caption}"
                else:
                    img_prompt += (
                        f"\n任務：\n"
                        f"1. 描述圖片內容。\n"
                        f"2. 提取文字（如有）。\n"
                        f"3. 總結重點。"
                    )
                
                forward_to_router(img_prompt, user_id, username, metadata={'file_type': 'image', 'local_path': local_path})
        
        # 📄 處理一般檔案 (Document)
        elif 'document' in msg_data:
            current_agent = get_current_agent()
            document = msg_data['document']
            file_id = document['file_id']
            
            local_path = image_manager.download_telegram_photo(file_id, current_agent)
            if local_path:
                caption = msg_data.get('caption', '').strip()
                doc_prompt = f"{SYS_PREFIX}請處理這個檔案，檔案位於: `{local_path}`"
                
                if caption:
                    doc_prompt += f"\n\n用戶的說明/提問：\n{caption}"
                
                forward_to_router(doc_prompt, user_id, username, metadata={'file_type': 'file', 'local_path': local_path})
        
        # 🎭 處理貼圖 (Sticker)
        elif 'sticker' in msg_data:
            sticker = msg_data['sticker']
            emoji = sticker.get('emoji', '貼圖')
            sticker_prompt = f"{SYS_PREFIX}用戶傳送了一個貼圖：{emoji}"
            forward_to_router(sticker_prompt, user_id, username, metadata={'file_type': 'sticker'})
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"❌ Webhook 異常: {e}")
        return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    logger.info(f"🚀 OctoMatrix Telegram Gateway 硬化版啟動 (Port: {TELEGRAM_GATEWAY_PORT})")
    app.run(host='0.0.0.0', port=TELEGRAM_GATEWAY_PORT, debug=False)
