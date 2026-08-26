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
Configuration Generator for OctoMatrix
Generates instance-specific configuration files (docker-compose, config.yaml, etc.)
"""

import sys
import yaml
import os

def generate_docker_compose(instance, user, script_dir, router_port=12210):
    """Generates a complete docker-compose file based on the template"""
    environment = [
        f"INSTANCE_NAME={instance}",
        f"APP_USER={user}",
        "ROUTER_HOST=0.0.0.0",
        "TELEGRAM_GATEWAY_HOST=0.0.0.0",
        f"ROUTER_PORT={router_port}",
        "TZ=${TZ:-Asia/Taipei}"
    ]
    # On a macOS host, agent_credential_wizard.sh guides the user through `claude setup-token`
    # and saves the resulting long-lived token to this file (macOS stores Claude Code
    # credentials in Keychain, which is incompatible with the container's file-based auth).
    # If the file exists, inject CLAUDE_CODE_OAUTH_TOKEN to bypass Keychain entirely.
    claude_token_file = os.path.join(script_dir, f"claude.token.{instance}")
    if os.path.isfile(claude_token_file):
        with open(claude_token_file, "r", encoding="utf-8") as f:
            claude_token = f.read().strip()
        if claude_token:
            # docker-compose interpolates ${VAR} references in every string value in
            # the compose file (the TZ=${TZ:-Asia/Taipei} line above deliberately relies
            # on this). If the token happens to contain a literal $ character, it would
            # get silently misinterpreted as a variable reference and stripped/mangled,
            # corrupting the token written into the container. Escape as $$ so
            # docker-compose treats it as a literal dollar sign.
            environment.append(f"CLAUDE_CODE_OAUTH_TOKEN={claude_token.replace('$', '$$')}")
    return {
        "services": {
            "bot": {
                "build": {
                    "context": "../",
                    "dockerfile": "docker-deploy/Dockerfile",
                    "args": {
                        "BUILD_USER": user,
                        "INSTANCE_NAME": instance
                    }
                },
                "container_name": f"octo_{instance}-bot",
                "restart": "unless-stopped",
                "environment": environment,
                "volumes": [
                    "../agent_home:/app/octomatrix/agent_home",
                    f"./container_home/{instance}:/home/{user}",
                    f"./.env.{instance}:/app/octomatrix/.env",
                    f"./config.{instance}.yaml:/app/octomatrix/config.yaml",
                    f"./awake.{instance}.yaml:/app/octomatrix/awake.yaml"
                ],
                "dns": ["8.8.8.8", "8.8.4.4"],
                "networks": [f"telegram_net_{instance}"]
            }
        },
        "networks": {
            f"telegram_net_{instance}": {
                "driver": "bridge",
                "name": f"telegram_net_{instance}"
            }
        }
    }

def generate_config(instance, data, telegram_gateway_port=11440, ngrok_api_port=4040, router_port=12210):
    """Generates the instance configuration yaml (full structure)"""
    agents = []
    if data:
        for entry in data.split('|||'):
            p = entry.split(':')
            if len(p) >= 4:
                agent_dict = {
                    "name": p[0],
                    "engine": p[1],
                    "usecase": p[2],
                    "description": p[3]
                }
                if len(p) >= 5 and p[4]:
                    agent_dict["model"] = p[4]
                agents.append(agent_dict)

    # Get default agent name (first agent)
    default_agent = agents[0]["name"] if agents else ""

    return {
        "server": {
            "host": "127.0.0.1",
            "telegram_gateway_port": telegram_gateway_port,
            "ngrok_api_port": ngrok_api_port
        },
        "router": {
            "host": "127.0.0.1",
            "port": router_port
        },
        "agents": agents,
        "default_active_agent": default_agent,
        "matrix_username": user,
        "octo_cyberbrain": {
            "ghost_check_interval_sec": 60,
            "ghost_compression_threshold_kb": 70,
            "ghost_long_term_compression_limit": 12,
            "ghost_awake_context_depth": 20
        },
        "telegram": {
            "api_base_url": "https://api.telegram.org/bot",
            "webhook_path": "/telegram_webhook"
        },
        "image_processing": {
            "temp_dir_name": "images_temp"
        },
        "tmux": {
            "session_name": f"ai_{instance}"
        },
        "menu": []
    }

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: generate_config.py <mode> <instance> <agents_data> <script_dir> [telegram_gateway_port] [ngrok_api_port] [user] [router_port]")
        sys.exit(1)

    mode = sys.argv[1]
    instance = sys.argv[2]
    data = sys.argv[3]
    script_dir = sys.argv[4]

    telegram_gateway_port = 11440
    ngrok_api_port = 4040
    user = os.environ.get('USER', 'appuser')
    router_port = 12210

    # Parse optional arguments
    if len(sys.argv) >= 6:
        try:
            telegram_gateway_port = int(sys.argv[5])
        except (ValueError, IndexError):
            pass

    if len(sys.argv) >= 7:
        try:
            ngrok_api_port = int(sys.argv[6])
        except (ValueError, IndexError):
            pass

    if len(sys.argv) >= 8:
        user = sys.argv[7]
        
    if len(sys.argv) >= 9:
        try:
            router_port = int(sys.argv[8])
        except (ValueError, IndexError):
            pass

    # Generate configuration
    if mode == "compose":
        compose = generate_docker_compose(instance, user, script_dir, router_port)
        output_file = os.path.join(script_dir, f"docker-compose.{instance}.yml")
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(compose, f, allow_unicode=True, default_flow_style=False)
        print(f"✅ Generated: {output_file}")

    elif mode == "config":
        config = generate_config(instance, data, telegram_gateway_port, ngrok_api_port, router_port)
        output_file = os.path.join(script_dir, f"config.{instance}.yaml")

        # Generate YAML with comments (using string template)
        agents_yaml = yaml.dump({"agents": config["agents"]}, allow_unicode=True, default_flow_style=False)
        menu_yaml = yaml.dump({"menu": config["menu"]}, allow_unicode=True, default_flow_style=False)

        config_content = f"""# ==========================================
# OctoMatrix Configuration File
# ==========================================

# 🌐 Server & Network Settings
server:
  host: {config['server']['host']}
  telegram_gateway_port: {config['server']['telegram_gateway_port']}
  ngrok_api_port: {config['server']['ngrok_api_port']}
router:
  host: {config['router']['host']}
  port: {config['router']['port']}

# [1] 🤖 AI Agent Army Configuration
{agents_yaml}
# Default active agent name on startup
default_active_agent: "{config['default_active_agent']}"

# [3] 🤝 Collaboration Groups
# Members within a group will automatically establish bi-directional soft-links (Full Mesh)
collaboration_groups: []

# [5] 🎮 Custom Menu
{menu_yaml}
# [4] 🧠 Cyberbrain Parameters
octo_cyberbrain:
  ghost_check_interval_sec: {config['octo_cyberbrain']['ghost_check_interval_sec']}
  ghost_compression_threshold_kb: {config['octo_cyberbrain']['ghost_compression_threshold_kb']}
  ghost_long_term_compression_limit: {config['octo_cyberbrain']['ghost_long_term_compression_limit']}
  ghost_awake_context_depth: {config['octo_cyberbrain']['ghost_awake_context_depth']}

# [2] 🪟 tmux Settings
tmux:
  session_name: "{config['tmux']['session_name']}"
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(config_content)
        print(f"✅ Generated: {output_file}")

    else:
        print(f"❌ Unknown mode: {mode}")
        sys.exit(1)
