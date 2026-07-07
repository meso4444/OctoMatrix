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
"""
octo_generator_v2.py — OctoMatrix animated avatar generator (v2)

Drop-in replacement for octo_generator.py (v1).
Only difference: generates animated WebM (VP9, 512×512, transparent) instead of static PNG.

Avatar deployment flow (identical to v1):
  First-blood  → generates all moods, packs ZIP, extracts to local avatar/ dir
  Has avatar   → generates all moods, packs ZIP, POSTs to router /api/internal/avatar/update

CLI (mirrors v1 exactly):
    python3 octo_generator_v2.py --color R G B --headgear crown --token TOKEN
    python3 octo_generator_v2.py --color 130 80 200 --eyewear glasses --blush_style hearts --token abc123
"""

import os, sys, io, zipfile, argparse, requests


from octo_anim_v5_gen import (
    generate_sticker as _anim_gen,
    ALL_MOODS as _ALL_MOODS,
)

# ── public constants ──────────────────────────────────────────────────────────

ALL_MOODS = _ALL_MOODS   # ['base','happy','love',...,'embarrassed']

BLUSH_STYLES = ['oval', 'dots', 'hearts', 'lightning', 'stars', 'swirls']

HEADGEAR_OPTS = [
    'none','crown','tophat','beret','cap','chef','wizard',
    'ninja','viking','halo','propeller','straw_hat','hard_hat','pirate',
    'headphones','antenna',
]

EYEWEAR_OPTS  = ['none','glasses','round_glasses','monocle','monocle_left']

ITEM_OPTS     = ['none','sword','wand','shield','lantern','book','scroll']


# ── router helpers (mirrors v1) ───────────────────────────────────────────────

def _get_agent_info_cwd():
    cwd   = os.path.abspath(os.getcwd())
    parts = cwd.split(os.sep)
    for i in range(len(parts)):
        if parts[i] == 'agent_home' and i < len(parts) - 1:
            return parts[i + 1], os.sep.join(parts[:i + 2])
    return os.path.basename(cwd), cwd


def _get_router_port(agent_home):
    port_file = os.path.join(os.path.dirname(os.path.dirname(agent_home)), '.router_port')
    if os.path.exists(port_file):
        try:
            return int(open(port_file).read().strip())
        except Exception:
            pass
    return 12210


# ── core API ──────────────────────────────────────────────────────────────────

def generate_sticker(
    mood       = 'base',
    body_rgb   = (130, 80, 200),
    headgear   = 'none',
    eyewear    = 'none',
    item_r     = 'none',
    item_l     = 'none',
    blush_style= 'oval',
    out_webm   = None,
    fps        = None,
) -> str:
    """Generate a single animated webm sticker and return the output path."""
    if out_webm is None:
        out_webm = f'/tmp/octo_v2_{mood}.webm'
    _anim_gen(
        mood=mood, body_rgb=body_rgb, headgear=headgear,
        eyewear=eyewear, item_r=item_r, item_l=item_l,
        blush_style=blush_style,
        frame_dir=f'/tmp/octo_v2_frames_{mood}_{os.getpid()}',
        out_webm=out_webm, fps=fps,
    )
    return os.path.abspath(out_webm)


def generate_all(
    out_dir    = './octo_animated_v2',
    body_rgb   = (130, 80, 200),
    headgear   = 'crown',
    eyewear    = 'none',
    item_r     = 'none',
    item_l     = 'none',
    blush_style= 'oval',
    fps        = None,
    verbose    = True,
) -> dict:
    """Generate all moods to out_dir. Returns dict {mood: webm_path}."""
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for mood in ALL_MOODS:
        out = os.path.join(out_dir, f'{mood}.webm')
        if verbose:
            print(f'  {mood}...', end='', flush=True)
        generate_sticker(
            mood=mood, body_rgb=body_rgb, headgear=headgear,
            eyewear=eyewear, item_r=item_r, item_l=item_l,
            blush_style=blush_style, out_webm=out, fps=fps,
        )
        if verbose:
            print(f' {os.path.getsize(out)/1024:.1f} KB')
        results[mood] = os.path.abspath(out)
    return results


def generate_all_avatars(
    body_rgb   = (150, 150, 150),
    eyewear    = 'none',
    headgear   = 'none',
    item_r     = 'none',
    item_l     = 'none',
    blush_style= 'oval',
    has_gold   = False,
    token      = '',
    fps        = None,
):
    """
    Generate all moods as WebM, pack into ZIP, then deploy (mirrors v1 flow):
      - First-blood (no avatar/base.webm): extract ZIP to local avatar/ dir
      - Has avatar: POST ZIP to router /api/internal/avatar/update with token
    """
    agent_name, agent_home = _get_agent_info_cwd()
    avatar_dir      = os.path.join(agent_home, 'avatar')
    base_webm_path  = os.path.join(avatar_dir, 'base.webm')
    is_first_blood  = not os.path.exists(base_webm_path)

    archive_files = {}

    for mood in ALL_MOODS:
        tmp_out = f'/tmp/avatar_v2_{mood}_{os.getpid()}.webm'
        print(f'  [{mood}] generating...', end='', flush=True)
        generate_sticker(
            mood=mood, body_rgb=body_rgb, headgear=headgear,
            eyewear=eyewear, item_r=item_r, item_l=item_l,
            blush_style=blush_style, out_webm=tmp_out, fps=fps,
        )
        with open(tmp_out, 'rb') as f:
            data = f.read()
        os.remove(tmp_out)

        arcname = 'base.webm' if mood == 'base' else f'emojis/{mood}.webm'
        archive_files[arcname] = data
        print(f' {len(data)//1024} KB → {arcname}')

    # Pack into ZIP in memory
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as z:
        for arcname, data in archive_files.items():
            z.writestr(arcname, data)
    zip_bytes = zip_io.getvalue()

    if is_first_blood:
        os.makedirs(avatar_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(avatar_dir)
        print('✨ [Generator v2] First-blood state (no avatar). Generated and extracted ZIP locally.')
    else:
        router_port = _get_router_port(agent_home)
        url   = f'http://127.0.0.1:{router_port}/api/internal/avatar/update'
        files = {'archive': ('avatar.zip', zip_bytes, 'application/zip')}
        data  = {'agent_name': agent_name, 'token': token}
        try:
            resp = requests.post(url, files=files, data=data, timeout=30)
            if resp.status_code == 200:
                print('✅ [Generator v2] Avatar updated and synced successfully.')
            else:
                print(f'❌ [Generator v2] Router rejected update: {resp.status_code} - {resp.text}')
                sys.exit(1)
        except Exception as e:
            print(f'❌ [Generator v2] Failed to connect to Router: {e}')
            sys.exit(1)


# ── CLI (mirrors v1 interface) ────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='OctoMatrix animated avatar generator v2 (WebM drop-in for v1 PNG)')
    parser.add_argument('--color',       nargs=3, type=int, default=[150, 150, 150],
                        metavar=('R', 'G', 'B'), help='Body colour (default: 150 150 150)')
    parser.add_argument('--eyewear',     default='none',
                        help=f'Eyewear: {", ".join(EYEWEAR_OPTS)}')
    parser.add_argument('--headgear',    default='none',
                        help=f'Headgear: {", ".join(HEADGEAR_OPTS)}')
    parser.add_argument('--item_r',      default='none',
                        help=f'Right-hand item: {", ".join(ITEM_OPTS)}')
    parser.add_argument('--item_l',      default='none',
                        help=f'Left-hand item: {", ".join(ITEM_OPTS)}')
    parser.add_argument('--gold',        action='store_true',
                        help='Enable gold accent (reserved, mirrors v1 flag)')
    parser.add_argument('--blush_style', default='oval',
                        help=f'Blush style: {", ".join(BLUSH_STYLES)}')
    parser.add_argument('--token',       default='',
                        help='Router auth token for avatar update')
    parser.add_argument('--fps',         default=None, type=int,
                        help='Animation FPS (default: 10)')

    args = parser.parse_args()

    generate_all_avatars(
        body_rgb    = tuple(args.color),
        eyewear     = args.eyewear,
        headgear    = args.headgear,
        item_r      = args.item_r,
        item_l      = args.item_l,
        blush_style = args.blush_style,
        has_gold    = args.gold,
        token       = args.token,
        fps         = args.fps,
    )
