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

import json
import os
import time
import threading
import requests
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
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

# OctoMatrix Router 配置
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = os.getenv('ROUTER_PORT', '12210')
ROUTER_URL = f"http://{ROUTER_HOST}:{ROUTER_PORT}"
ROUTER_INJECT_ENDPOINT = f"{ROUTER_URL}/inject"
ROUTER_STATUS_ENDPOINT = f"{ROUTER_URL}/status"

# 本服務自己的監聽位址：預設僅本機(127.0.0.1)，Docker 容器化部署才需要對外(0.0.0.0)，
# 由部署層透過環境變數 TELEGRAM_GATEWAY_HOST 覆寫。改用 long polling 後這個 port
# 只服務極簡的 /health 存活檢查，不再接收 Telegram 的推送請求。
TELEGRAM_GATEWAY_HOST = os.getenv('TELEGRAM_GATEWAY_HOST', '127.0.0.1')

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# offset 持久化檔案：記錄最後一筆「已完整處理完成」的 update_id，重啟後從這裡接續，
# 只在 process_message() 真的跑完之後才會被推進（見 polling_loop）。
# 放在 agent_home/ 底下而不是 repo 根目錄：start_octo_services.sh 的 Runtime 權限鎖定
# 會把 repo 根目錄本身 chmod o-rw，執行期的 system_user 對該目錄沒有「建立新檔案」的
# 權限（既有檔案可讀寫，但生不出新檔案），2026-08-29 Solas 在 testsolo01 實測時
# 就是因此在 polling_loop() 第一次 save_offset() 時撞到 PermissionError；agent_home/
# 這個目錄本身是執行期可寫的，所以把這個純執行期產生的狀態檔案改放到這裡。
OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_home', '.telegram_offset')

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
            # 身分透過 su - 執行，見 setup_agent_env.py 的 spawn_agent()）讀取處理。
            # 原本用 sudo chown 轉移所有權，但 sudo 未設定 NOPASSWD 時會卡在密碼提示
            # 卡死整個 gateway；改用 chmod 開放 other 的讀寫權限，不需變更擁有者也能
            # 讓 Agent 讀寫檔案內容，不會有 sudo 卡死風險。
            os.chmod(local_path, 0o666)

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

def process_message(msg_data):
    """處理單一則 Telegram message（webhook 與 long polling 共用同一套邏輯）"""
    chat_id = str(msg_data.get('chat', {}).get('id', ''))
    user_id = msg_data.get('from', {}).get('id')
    username = msg_data.get('from', {}).get('username', f"user_{user_id}")
    text = msg_data.get('text', '')

    # 👑 選單攔截邏輯 (確保 chat_id 已賦值)
    if text in ['/start', '/menu', '菜單']:
        show_control_menu(chat_id)
        return

    # 安全檢查
    if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
        return

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

    # 🎵 處理音訊檔案 (Audio / MP3)
    elif 'audio' in msg_data:
        current_agent = get_current_agent()
        audio = msg_data['audio']
        file_id = audio['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            audio_prompt = f"{SYS_PREFIX}請處理這個音訊檔案，檔案位於: `{local_path}`"

            if caption:
                audio_prompt += f"\n\n用戶的說明/提問：\n{caption}"

            forward_to_router(audio_prompt, user_id, username, metadata={'file_type': 'audio', 'local_path': local_path})

    # 🎙️ 處理語音訊息 (Voice)
    elif 'voice' in msg_data:
        current_agent = get_current_agent()
        voice = msg_data['voice']
        file_id = voice['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            voice_prompt = f"{SYS_PREFIX}請處理這則語音訊息，檔案位於: `{local_path}`"

            if caption:
                voice_prompt += f"\n\n用戶的說明/提問：\n{caption}"

            forward_to_router(voice_prompt, user_id, username, metadata={'file_type': 'voice', 'local_path': local_path})

    # 🎬 處理影片 (Video)
    elif 'video' in msg_data:
        current_agent = get_current_agent()
        video = msg_data['video']
        file_id = video['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            video_prompt = f"{SYS_PREFIX}請處理這個影片檔案，檔案位於: `{local_path}`"

            if caption:
                video_prompt += f"\n\n用戶的說明/提問：\n{caption}"

            forward_to_router(video_prompt, user_id, username, metadata={'file_type': 'video', 'local_path': local_path})

    # 📹 處理圓形視訊留言 (Video Note)
    elif 'video_note' in msg_data:
        current_agent = get_current_agent()
        video_note = msg_data['video_note']
        file_id = video_note['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            video_note_prompt = f"{SYS_PREFIX}請處理這則圓形視訊留言，檔案位於: `{local_path}`"
            forward_to_router(video_note_prompt, user_id, username, metadata={'file_type': 'video_note', 'local_path': local_path})

    # 🎞️ 處理動態圖片 (Animation / GIF)
    elif 'animation' in msg_data:
        current_agent = get_current_agent()
        animation = msg_data['animation']
        file_id = animation['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            animation_prompt = f"{SYS_PREFIX}請處理這個動態圖片(GIF)，檔案位於: `{local_path}`"

            if caption:
                animation_prompt += f"\n\n用戶的說明/提問：\n{caption}"

            forward_to_router(animation_prompt, user_id, username, metadata={'file_type': 'animation', 'local_path': local_path})

    # 🎭 處理貼圖 (Sticker)
    elif 'sticker' in msg_data:
        sticker = msg_data['sticker']
        emoji = sticker.get('emoji', '貼圖')
        sticker_prompt = f"{SYS_PREFIX}用戶傳送了一個貼圖：{emoji}"
        forward_to_router(sticker_prompt, user_id, username, metadata={'file_type': 'sticker'})

def load_offset():
    try:
        with open(OFFSET_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_offset(update_id):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(update_id))

def polling_loop():
    """Long polling 主迴圈：取代原本 webhook 被動接收，改為主動向 Telegram 長輪詢拉取訊息。"""
    try:
        requests.post(f"{TELEGRAM_API_BASE}/deleteWebhook", timeout=10)
        logger.info("✅ 已刪除 webhook 註冊，改用 getUpdates long polling")
    except Exception as e:
        logger.error(f"❌ deleteWebhook 失敗（若舊 webhook 仍註冊中可能導致 409）: {e}")

    offset = load_offset()
    logger.info(f"🔄 Long polling 啟動，起始 offset={offset}")

    while True:
        try:
            params = {'timeout': 30}
            if offset:
                params['offset'] = offset + 1
            resp = requests.post(f"{TELEGRAM_API_BASE}/getUpdates", json=params, timeout=35)
            data = resp.json()
        except Exception as e:
            logger.error(f"❌ getUpdates 請求失敗，5 秒後重試: {e}")
            time.sleep(5)
            continue

        if not data.get('ok'):
            logger.error(f"❌ getUpdates 回應異常，5 秒後重試: {data}")
            time.sleep(5)
            continue

        for update in data.get('result', []):
            update_id = update['update_id']
            msg_data = update.get('message')
            # 刻意不在這裡包 try/except：process_message() 真的處理完才會往下推進 offset，
            # 若這裡拋出例外，整個程序會中止，交由 tmux/monitor 那層重啟；重啟後從舊 offset
            # 接續，Telegram 會重送這筆尚未確認的訊息（at-least-once，不會漏收）。
            if msg_data:
                process_message(msg_data)
            offset = update_id
            save_offset(offset)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 靜音預設的存取日誌，避免洗版

def start_health_server():
    server = HTTPServer((TELEGRAM_GATEWAY_HOST, TELEGRAM_GATEWAY_PORT), HealthHandler)
    server.serve_forever()

if __name__ == '__main__':
    logger.info(f"🚀 OctoMatrix Telegram Gateway (Long Polling 版) 啟動 (健康檢查 Port: {TELEGRAM_GATEWAY_PORT})")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    polling_loop()
