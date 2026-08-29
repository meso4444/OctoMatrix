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

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# OctoMatrix Router Configuration
ROUTER_HOST = os.getenv('ROUTER_HOST', 'localhost')
ROUTER_PORT = os.getenv('ROUTER_PORT', '12210')
ROUTER_URL = f"http://{ROUTER_HOST}:{ROUTER_PORT}"
ROUTER_INJECT_ENDPOINT = f"{ROUTER_URL}/inject"
ROUTER_STATUS_ENDPOINT = f"{ROUTER_URL}/status"

# This service's own listen address: defaults to localhost only (127.0.0.1);
# only Docker-containerized deployments need external (0.0.0.0), overridden
# by the deployment layer via the TELEGRAM_GATEWAY_HOST env var. After
# switching to long polling this port only serves a minimal /health check,
# it no longer receives Telegram's push requests.
TELEGRAM_GATEWAY_HOST = os.getenv('TELEGRAM_GATEWAY_HOST', '127.0.0.1')

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Offset persistence file: records the last update_id that was "fully
# processed", so restarts pick up from here. Only advanced after
# process_message() actually finishes (see polling_loop).
# Placed under agent_home/ rather than the repo root: start_octo_services.sh's
# Runtime permission lockdown chmod o-rw's the repo root directory itself, so
# the runtime system_user has no permission to CREATE new files there (it can
# still read/write pre-existing files); 2026-08-29 Solas hit exactly this as a
# PermissionError on the first save_offset() call during a testsolo01 real-world
# test. agent_home/ itself is writable at runtime, so this purely-runtime state
# file lives there instead.
OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_home', '.telegram_offset')

class ImageManager:
    """Image Manager: Responsible for downloading images from various platforms to specified Agent directory"""
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def download_telegram_photo(self, file_id, agent_name):
        try:
            agent_img_dir = os.path.join(self.base_dir, 'agent_home', agent_name, 'downloads_temp')
            os.makedirs(agent_img_dir, exist_ok=True)

            # Get file information
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
            resp = requests.get(url, timeout=10).json()
            if not resp.get('ok'): return None

            file_path = resp['result']['file_path']
            ext = os.path.splitext(file_path)[1] or ".jpg"
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_id[:8]}{ext}"
            local_path = os.path.join(agent_img_dir, filename)

            # Download the file
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            content = requests.get(download_url, timeout=20).content
            with open(local_path, 'wb') as f:
                f.write(content)

            # telegram_gateway.py runs as whichever user started the service, so
            # the downloaded file is owned by that user by default; but it's
            # ultimately handed to the target Agent, which runs under its own
            # agent_<name> OS user via `su -` (see spawn_agent() in
            # setup_agent_env.py), to read and process. Previously used sudo
            # chown to transfer ownership, but sudo isn't configured NOPASSWD
            # here and hangs waiting for a password, blocking the whole gateway.
            # chmod to open "other" read/write avoids sudo entirely while still
            # letting the Agent read/write the file content.
            os.chmod(local_path, 0o666)

            logger.info(f"📸 Image downloaded to [{agent_name}]: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ Image download failed: {e}")
            return None

image_manager = ImageManager(os.path.dirname(os.path.abspath(__file__)))

def get_current_agent():
    """Ask Router for current active Agent"""
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
        logger.error(f"❌ Failed to send menu message: {e}")

def show_control_menu(chat_id):
    if not CUSTOM_MENU: return
    menu_message = f"🎮 <b>OctoMatrix System Control Menu</b>\n\nPlease select an operation:"
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
    """Process a single Telegram message (shared logic for webhook and long polling)"""
    chat_id = str(msg_data.get('chat', {}).get('id', ''))
    user_id = msg_data.get('from', {}).get('id')
    username = msg_data.get('from', {}).get('username', f"user_{user_id}")
    text = msg_data.get('text', '')

    # 👑 Menu interception logic (ensure chat_id is set)
    if text in ['/start', '/menu', 'menu']:
        show_control_menu(chat_id)
        return

    # Safety check
    if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
        return

    if text:
        forward_to_router(text, user_id, username)

    # 📸 Handle photos
    elif 'photo' in msg_data:
        current_agent = get_current_agent()
        photo_array = msg_data['photo']
        best_photo = photo_array[-1] # Get highest resolution
        file_id = best_photo['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            img_prompt = f"{SYS_PREFIX} Please process this image, file path: `{local_path}`"

            if caption:
                img_prompt += f"\n\nUser explanation/question:\n{caption}"
            else:
                img_prompt += (
                    f"\nTasks:\n"
                    f"1. Describe image content.\n"
                    f"2. Extract text (if any).\n"
                    f"3. Summarize key points."
                )

            forward_to_router(img_prompt, user_id, username, metadata={'file_type': 'image', 'local_path': local_path})

    # 📄 Handle general files (Document)
    elif 'document' in msg_data:
        current_agent = get_current_agent()
        document = msg_data['document']
        file_id = document['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            doc_prompt = f"{SYS_PREFIX} Please process this file, file path: `{local_path}`"

            if caption:
                doc_prompt += f"\n\nUser explanation/question:\n{caption}"

            forward_to_router(doc_prompt, user_id, username, metadata={'file_type': 'file', 'local_path': local_path})

    # 🎵 Handle audio files (Audio / MP3)
    elif 'audio' in msg_data:
        current_agent = get_current_agent()
        audio = msg_data['audio']
        file_id = audio['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            audio_prompt = f"{SYS_PREFIX} Please process this audio file, file path: `{local_path}`"

            if caption:
                audio_prompt += f"\n\nUser explanation/question:\n{caption}"

            forward_to_router(audio_prompt, user_id, username, metadata={'file_type': 'audio', 'local_path': local_path})

    # 🎙️ Handle voice messages (Voice)
    elif 'voice' in msg_data:
        current_agent = get_current_agent()
        voice = msg_data['voice']
        file_id = voice['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            voice_prompt = f"{SYS_PREFIX} Please process this voice message, file path: `{local_path}`"

            if caption:
                voice_prompt += f"\n\nUser explanation/question:\n{caption}"

            forward_to_router(voice_prompt, user_id, username, metadata={'file_type': 'voice', 'local_path': local_path})

    # 🎬 Handle video files (Video)
    elif 'video' in msg_data:
        current_agent = get_current_agent()
        video = msg_data['video']
        file_id = video['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            video_prompt = f"{SYS_PREFIX} Please process this video file, file path: `{local_path}`"

            if caption:
                video_prompt += f"\n\nUser explanation/question:\n{caption}"

            forward_to_router(video_prompt, user_id, username, metadata={'file_type': 'video', 'local_path': local_path})

    # 📹 Handle round video messages (Video Note)
    elif 'video_note' in msg_data:
        current_agent = get_current_agent()
        video_note = msg_data['video_note']
        file_id = video_note['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            video_note_prompt = f"{SYS_PREFIX} Please process this video note, file path: `{local_path}`"
            forward_to_router(video_note_prompt, user_id, username, metadata={'file_type': 'video_note', 'local_path': local_path})

    # 🎞️ Handle animations (Animation / GIF)
    elif 'animation' in msg_data:
        current_agent = get_current_agent()
        animation = msg_data['animation']
        file_id = animation['file_id']

        local_path = image_manager.download_telegram_photo(file_id, current_agent)
        if local_path:
            caption = msg_data.get('caption', '').strip()
            animation_prompt = f"{SYS_PREFIX} Please process this animation (GIF), file path: `{local_path}`"

            if caption:
                animation_prompt += f"\n\nUser explanation/question:\n{caption}"

            forward_to_router(animation_prompt, user_id, username, metadata={'file_type': 'animation', 'local_path': local_path})

    # 🎭 Handle Sticker
    elif 'sticker' in msg_data:
        sticker = msg_data['sticker']
        emoji = sticker.get('emoji', 'sticker')
        sticker_prompt = f"{SYS_PREFIX} User sent a sticker: {emoji}"
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
    """Long polling main loop: replaces the passive webhook receive with actively long-polling Telegram for messages."""
    try:
        requests.post(f"{TELEGRAM_API_BASE}/deleteWebhook", timeout=10)
        logger.info("✅ Webhook registration deleted, switching to getUpdates long polling")
    except Exception as e:
        logger.error(f"❌ deleteWebhook failed (a lingering webhook registration may cause a 409): {e}")

    offset = load_offset()
    logger.info(f"🔄 Long polling started, initial offset={offset}")

    while True:
        try:
            params = {'timeout': 30}
            if offset:
                params['offset'] = offset + 1
            resp = requests.post(f"{TELEGRAM_API_BASE}/getUpdates", json=params, timeout=35)
            data = resp.json()
        except Exception as e:
            logger.error(f"❌ getUpdates request failed, retrying in 5s: {e}")
            time.sleep(5)
            continue

        if not data.get('ok'):
            logger.error(f"❌ getUpdates returned an error, retrying in 5s: {data}")
            time.sleep(5)
            continue

        for update in data.get('result', []):
            update_id = update['update_id']
            msg_data = update.get('message')
            # Deliberately no try/except here: offset only advances after
            # process_message() actually finishes. If this raises, the whole
            # process aborts and is restarted by the tmux/monitor layer;
            # restarting picks up from the old offset, so Telegram resends
            # this unconfirmed message (at-least-once, nothing is lost).
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
        pass  # Silence the default access log to avoid flooding output

def start_health_server():
    server = HTTPServer((TELEGRAM_GATEWAY_HOST, TELEGRAM_GATEWAY_PORT), HealthHandler)
    server.serve_forever()

if __name__ == '__main__':
    logger.info(f"🚀 OctoMatrix Telegram Gateway (Long Polling) starting (Health check port: {TELEGRAM_GATEWAY_PORT})")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    polling_loop()
