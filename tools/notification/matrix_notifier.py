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

# -*- coding: utf-8 -*-
"""
📢 Unified Notifier (matrix_notifier.py)
跨平臺通知中心 - 版型轉譯與自動備援

職責：
1. 統一接口：notify(target_platform, template_id, context)
2. 跨平臺版型渲染：相容舊版 (icon/title/content) 與新版 (platform-specific) 模板
3. 自動備援：若主通道失敗，自動轉向備援通道
4. 多平臺支援：TG (HTML) / DS (Markdown) / SL (Plain Text)
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

import requests
import yaml
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ============================================================================
# 配置與日誌
# ============================================================================

# 動態加載專案根目錄到 sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = _current_dir
for _ in range(5):
    if os.path.exists(os.path.join(_root_dir, 'config.py')):
        if _root_dir not in sys.path:
            sys.path.insert(0, _root_dir)
        break
    _root_dir = os.path.dirname(_root_dir)

_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.append(logging.FileHandler('/tmp/matrix_notifier.log'))
except PermissionError:
    # 防止容器內多用戶權限衝突
    pass

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=_log_handlers
)
logger = logging.getLogger(__name__)

# 通知服務配置
try:
    from config import MESSAGE_TEMPLATES_PATH, TELEGRAM_BOT_TOKEN
    TEMPLATES_PATH = MESSAGE_TEMPLATES_PATH
except ImportError:
    from pathlib import Path
    _cur_dir = Path(__file__).resolve().parent
    TEMPLATES_PATH = str(_cur_dir / 'message_templates.yaml')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

TELEGRAM_API_BASE_URL = "https://api.telegram.org/bot"

try:
    from config import CONFIG_PATH
except ImportError:
    from pathlib import Path
    _cur_dir = Path(__file__).resolve().parent
    CONFIG_PATH = os.getenv('CONFIG_PATH', str(_cur_dir / 'config.yaml'))
# 平臺 API 端點
DISCORD_API_URL = "https://discord.com/api/v10"
SLACK_API_URL = "https://slack.com/api"


class PlatformEnum(str, Enum):
    """通訊平臺列舉"""
    TELEGRAM = 'telegram'
    DISCORD = 'discord'
    SLACK = 'slack'
    EMAIL = 'email'


# ============================================================================
# 版型管理
# ============================================================================

class TemplateManager:
    """
    消息版型管理器
    """

    def __init__(self, templates_path: str):
        self.templates = self._load_templates(templates_path)
        logger.info(f"[Notifier] 版型已加載: {templates_path}")

    def _load_templates(self, path: str) -> dict:
        """加載消息版型配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"[Notifier] 版型加載失敗: {e}")
            return {}

    def render(self, platform: str, template_id: str, context: Dict[str, Any]) -> str:
        """
        根據平臺渲染消息版型
        """
        software = context.get('software')
        all_templates = self.templates.get("templates", {})
        sw_templates = self.templates.get("software_templates", {})

        # 1. 優先查找軟體特定版型
        template_entry = None
        if software and software in sw_templates:
            template_entry = sw_templates[software].get(template_id)
        
        # 2. 回退到通用版型
        if not template_entry:
            template_entry = all_templates.get(template_id, {})

        if not template_entry:
            return context.get('content', f"[未知版型: {template_id}]")

        # 3. 獲取平臺特定內容或執行 Legacy 合併
        template = template_entry.get(platform)
        if not template:
            # 處理舊版 icon + title + content 結構
            icon = template_entry.get('icon', '')
            title = template_entry.get('title', '')
            body = template_entry.get('content', '')
            
            if icon or title or body:
                template = f"{icon} {title}\n\n{body}".strip()
            else:
                # 避免將整個 dict 轉成字串導致 format_map 解析失敗
                template = f"[{template_id}] 通知: {context.get('content', '')}"
        
        # 準備基礎上下文
        full_context = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'platform': platform
        }
        full_context.update(context)

        class SafeDict(dict):
            def __missing__(self, key):
                return '{' + key + '}'

        rendered_text = str(template)
        if isinstance(template, str):
            try:
                rendered_text = template.format_map(SafeDict(full_context))
            except Exception as e:
                logger.error(f"[Notifier] 渲染異常: {e}")

        # --- 跨平臺標籤自動轉譯 (HTML -> Markdown) ---
        if platform == 'discord':
            rendered_text = rendered_text.replace('<b>', '**').replace('</b>', '**')
            rendered_text = rendered_text.replace('<i>', '*').replace('</i>', '*')
            rendered_text = rendered_text.replace('<code>', '`').replace('</code>', '`')
            rendered_text = rendered_text.replace('<pre>', '```\n').replace('</pre>', '\n```')
        elif platform == 'slack':
            rendered_text = rendered_text.replace('<b>', '*').replace('</b>', '*')
            rendered_text = rendered_text.replace('<i>', '_').replace('</i>', '_')
            rendered_text = rendered_text.replace('<code>', '`').replace('</code>', '`')
            rendered_text = rendered_text.replace('<pre>', '```\n').replace('</pre>', '\n```')

        return rendered_text.strip()


# ============================================================================
# 平臺發送器 (Platform Senders)
# ============================================================================

class TelegramSender:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id: str, message: str, parse_mode: str = 'HTML', **kwargs) -> bool:
        try:
            chunks = [message[i:i+3800] for i in range(0, len(message), 3800)]
            success = True
            for chunk in chunks:
                data = {'chat_id': chat_id, 'text': chunk, 'parse_mode': parse_mode}
                # Telegram 專屬鍵盤支援
                if 'reply_markup' in kwargs: data["reply_markup"] = kwargs["reply_markup"]
                resp = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=5)
                if resp.status_code != 200:
                    if parse_mode:
                        logger.warning(f"[Notifier] Telegram 解析錯誤 ({resp.status_code})，正嘗試以純文字模式重發。錯誤: {resp.text}")
                        if 'parse_mode' in data:
                            del data['parse_mode']
                        resp = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=5)
                        if resp.status_code != 200:
                            logger.error(f"[Notifier] Telegram 純文字重發失敗: {resp.text}")
                            success = False
                    else:
                        logger.error(f"[Notifier] Telegram 發送失敗: {resp.text}")
                        success = False
            return success
        except: return False

    def send_file(self, chat_id: str, file_path: str, file_type: str = 'document', caption: str = '', **kwargs) -> bool:
        is_temp_webp = False
        target_path = file_path
        try:
            # 貼圖特化處理：自動轉換為 WebP 且強制不帶 caption
            if file_type == 'sticker':
                if not file_path.lower().endswith('.webp'):
                    try:
                        from PIL import Image
                        target_path = file_path + ".webp"
                        Image.open(file_path).save(target_path, "WEBP")
                        is_temp_webp = True
                    except Exception as e:
                        logger.warning(f"[Notifier] 貼圖轉換失敗: {e}")
                caption = "" # 貼圖強制不帶文字

            method_map = {'photo': 'sendPhoto', 'video': 'sendVideo', 'audio': 'sendAudio', 'sticker': 'sendSticker'}
            method = method_map.get(file_type, 'sendDocument')
            
            param_map = {'photo': 'photo', 'video': 'video', 'audio': 'audio', 'sticker': 'sticker'}
            param = param_map.get(file_type, 'document')
            
            # 自動偵測 photo 且為 gif，改為 sendAnimation
            if file_type == 'photo' and target_path.lower().endswith('.gif'):
                method = 'sendAnimation'
                param = 'animation'
            
            with open(target_path, 'rb') as f:
                data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
                if caption:
                    data['caption'] = caption[:1000]
                resp = requests.post(f"{self.api_url}/{method}", files={param: f}, data=data, timeout=30)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"[Notifier] Telegram 發送檔案失敗: {e}")
            return False
        finally:
            if is_temp_webp and os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass


class DiscordSender:
    def __init__(self, bot_token: str):
        self.headers = {'Authorization': f'Bot {bot_token}'}

    def send(self, channel_id: str, message: str, **kwargs) -> bool:
        try:
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            success = True
            for chunk in chunks:
                resp = requests.post(f"{DISCORD_API_URL}/channels/{channel_id}/messages", json={'content': chunk}, headers=self.headers, timeout=5)
                if resp.status_code not in [200, 201]: success = False
            return success
        except: return False

    def send_file(self, channel_id: str, file_path: str, file_type: str = 'document', caption: str = '', **kwargs) -> bool:
        is_temp_webp = False
        target_path = file_path
        try:
            if file_type == 'sticker':
                if not file_path.lower().endswith('.webp'):
                    try:
                        from PIL import Image
                        target_path = file_path + ".webp"
                        Image.open(file_path).save(target_path, "WEBP")
                        is_temp_webp = True
                    except: pass
                caption = "" # 貼圖模式不帶文字

            with open(target_path, 'rb') as f:
                data = {'content': caption[:1900]}
                resp = requests.post(f"{DISCORD_API_URL}/channels/{channel_id}/messages", files={'file': (os.path.basename(target_path), f)}, data=data, headers=self.headers, timeout=30)
                return resp.status_code in [200, 201]
        except: return False
        finally:
            if is_temp_webp and os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass


class SlackSender:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.client = WebClient(token=bot_token)
        self.headers = {'Authorization': f'Bearer {bot_token}'}

    def send(self, channel_id: str, message: str, **kwargs) -> bool:
        try:
            chunks = [message[i:i+3800] for i in range(0, len(message), 3800)]
            success = True
            for chunk in chunks:
                resp = self.client.chat_postMessage(channel=channel_id, text=chunk)
                if not resp.get('ok'):
                    logger.error(f"[Notifier] Slack 發送失敗: {resp.get('error')}")
                    success = False
            return success
        except SlackApiError as e:
            logger.error(f"[Notifier] Slack API 異常: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"[Notifier] Slack 發送未知異常: {e}")
            return False

    def send_file(self, channel_id: str, file_path: str, file_type: str = 'document', caption: str = '', **kwargs) -> bool:
        is_temp_webp = False
        target_path = file_path
        try:
            if file_type == 'sticker':
                if not file_path.lower().endswith('.webp'):
                    try:
                        from PIL import Image
                        target_path = file_path + ".webp"
                        Image.open(file_path).save(target_path, "WEBP")
                        is_temp_webp = True
                    except: pass
                caption = "" # 貼圖模式不帶文字

            # 使用 files_upload_v2 自動處理全新的三階段上傳流程 (2025+ 規範)
            resp = self.client.files_upload_v2(
                channel=channel_id,
                file=target_path,
                initial_comment=caption[:1900] if caption else None,
                title=os.path.basename(target_path)
            )
            return resp.get('ok', False)
        except Exception as e:
            logger.error(f"[Notifier] Slack 檔案發送異常: {e}")
            return False
        finally:
            if is_temp_webp and os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass


# ============================================================================
# 統一通知器
# ============================================================================

class MatrixNotifier:
    def __init__(self, config_path: str = CONFIG_PATH, templates_path: str = TEMPLATES_PATH):
        self.template_manager = TemplateManager(templates_path)
        self.senders = self._initialize_senders()

    def _initialize_senders(self) -> Dict[str, Any]:
        senders = {}
        tg = os.getenv('TELEGRAM_BOT_TOKEN')
        if tg: senders['telegram'] = TelegramSender(tg)
        ds = os.getenv('DISCORD_TOKEN')
        if ds: senders['discord'] = DiscordSender(ds)
        sl = os.getenv('SLACK_BOT_TOKEN')
        if sl: senders['slack'] = SlackSender(sl)
        return senders

    def _get_target_id(self, platform):
        from config import TELEGRAM_CHAT_ID, DISCORD_CHANNEL_ID, SLACK_CHANNEL_ID
        env_id = os.environ.get(f"{platform.upper()}_CHAT_ID") or os.environ.get(f"{platform.upper()}_CHANNEL_ID")
        if env_id: return env_id
        return {'telegram': TELEGRAM_CHAT_ID, 'discord': DISCORD_CHANNEL_ID, 'slack': SLACK_CHANNEL_ID}.get(platform)

    def notify(self, target_platform: str, template_id: str, context: Dict[str, Any], target_id: Optional[str] = None) -> bool:
        # 檢查平臺是否啟用
        try:
            from config import PLATFORMS_ENABLED
            if not PLATFORMS_ENABLED.get(target_platform, True):
                logger.warning(f"[Notifier] 平臺 {target_platform} 已禁用，跳過通知")
                return False
        except ImportError:
            pass

        message = self.template_manager.render(target_platform, template_id, context)
        sender = self.senders.get(target_platform)
        if not sender: return False
        if not target_id: target_id = self._get_target_id(target_platform)
        if not target_id: return False
        
        # 傳遞所有 platform-specific 參數
        return sender.send(target_id, message, **context.get('_platform_kwargs', {}))

    def notify_file(self, target_platform: str, file_path: str, file_type: str = 'document', caption: str = '', target_id: Optional[str] = None) -> bool:
        # 檢查平臺是否啟用
        try:
            from config import PLATFORMS_ENABLED
            if not PLATFORMS_ENABLED.get(target_platform, True):
                logger.warning(f"[Notifier] 平臺 {target_platform} 已禁用，跳過檔案發送")
                return False
        except ImportError:
            pass

        sender = self.senders.get(target_platform)
        if not sender: return False
        if not target_id: target_id = self._get_target_id(target_platform)
        if not target_id: return False
        
        return sender.send_file(target_id, file_path, file_type, caption)


def get_router_url() -> str:
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        port_file = os.path.join(curr, '.router_port')
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    p = f.read().strip()
                    if p: return f"http://localhost:{p}"
            except: pass
        curr = os.path.dirname(curr)
    return f"http://localhost:{os.getenv('ROUTER_PORT', 12210)}"

def get_source_info():
    curr = os.path.dirname(os.path.abspath(__file__))
    enabled_platforms = {}
    default_platform = 'telegram'
    
    # 嘗試從配置獲取預設主通道與啟用狀態
    try:
        from config import DEFAULT_PRIMARY_CHANNEL, PLATFORMS_ENABLED
        default_platform = DEFAULT_PRIMARY_CHANNEL
        enabled_platforms = PLATFORMS_ENABLED
        
        # 如果預設通道已禁用，自動選擇第一個啟用的通道
        if not enabled_platforms.get(default_platform, False):
            active = [k for k, v in enabled_platforms.items() if v]
            if active: default_platform = active[0]
    except ImportError:
        pass

    for _ in range(4):
        path = os.path.join(curr, '.last_source')
        if os.path.exists(path):
            try:
                import json
                with open(path, 'r') as f:
                    source = json.load(f)
                    p = source.get('platform')
                    # 如果來源平台被禁用，強制降級到預設平台
                    if enabled_platforms and p and not enabled_platforms.get(p, False):
                        source['platform'] = default_platform
                    return source
            except: pass
        curr = os.path.dirname(curr)
    return {'platform': default_platform}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OctoMatrix Matrix Notifier CLI (Multi-Channel)')
    parser.add_argument('message', nargs='*', help='Message content')
    parser.add_argument('--file', nargs=2, metavar=('TYPE', 'PATH'), help='Send a file (type: photo, video, audio, document, sticker)')
    parser.add_argument('--caption', help='Caption for the file')
    parser.add_argument('--template', default='custom', help='Template ID to use')
    parser.add_argument('--software', help='Software name for template lookup')
    parser.add_argument('--keyboard', help='JSON string for TG custom keyboard')
    parser.add_argument('--get-id', action='store_true', help='Helper to find Telegram Chat ID')
    
    # Intercept sys.argv to safely handle dash-prefixed messages
    import sys
    known_flags = {'--file': 2, '--caption': 1, '--template': 1, '--software': 1, '--keyboard': 1, '--get-id': 0, '-h': 0, '--help': 0}
    new_argv = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in known_flags:
            new_argv.append(arg)
            n = known_flags[arg]
            for _ in range(n):
                i += 1
                if i < len(sys.argv):
                    new_argv.append(sys.argv[i])
        else:
            new_argv.append('--')
            new_argv.extend(sys.argv[i:])
            break
        i += 1

    args = parser.parse_args(new_argv)

    if args.get_id:
        if not TELEGRAM_BOT_TOKEN: print("❌ Missing TELEGRAM_BOT_TOKEN"); sys.exit(1)
        resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates").json()
        if resp.get('result'):
            print(f"✅ Latest Chat ID: {resp['result'][-1]['message']['chat']['id']}")
        else:
            print("⚠️ No updates found. Send a message to your bot first.")
        sys.exit(0)

    source = get_source_info()
    platform = source.get('platform', 'telegram')
    
    target_id = source.get('channel_id')
    if not target_id and platform == 'telegram': target_id = source.get('user_id')

    context = {'software': args.software} if args.software else {}
    if args.keyboard:
        # 僅 Telegram 支援此參數
        try: context['_platform_kwargs'] = {'reply_markup': json.loads(args.keyboard)}
        except: print("❌ Invalid keyboard JSON")

    router_url = get_router_url()

    if args.file:
        f_type, f_path = args.file
        caption = (args.caption or " ".join(args.message)).replace('\\n', '\n')
        if not os.path.exists(f_path): print(f"❌ File not found: {f_path}"); sys.exit(1)
        try:
            with open(f_path, 'rb') as f:
                # 【優化】僅在 target_id 有效時發送，避免傳遞無效字串
                payload = {'platform': platform, 'file_type': f_type, 'caption': caption}
                if target_id and str(target_id).lower() not in ['none', 'null', 'undefined']:
                    payload['target_id'] = target_id
                    
                resp = requests.post(f"{router_url}/notify_file", files={'file': (os.path.basename(f.name), f)}, data=payload, timeout=30)
                if resp.status_code == 200: print(f"✅ File sent via Router to {platform}"); sys.exit(0)
                else: print(f"❌ Router Error: {resp.status_code}"); sys.exit(1)
        except Exception as e: print(f"❌ Error: {e}"); sys.exit(1)

    elif args.message or args.template != 'custom':
        msg_content = " ".join(args.message).replace('\\n', '\n')
        context['content'] = msg_content
        payload = {'platform': platform, 'template_id': args.template, 'context': context, 'target_id': target_id}
        try:
            resp = requests.post(f"{router_url}/notify", json=payload, timeout=10)
            if resp.status_code == 200: print(f"✅ Message sent via Router to {platform}"); sys.exit(0)
            else: print(f"❌ Router Error: {resp.status_code}"); sys.exit(1)
        except Exception as e: print(f"❌ Error: {e}"); sys.exit(1)
    else:
        parser.print_help()
