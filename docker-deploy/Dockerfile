FROM python:3.11-slim

# 動態指定容器用戶名（預設: appuser，可在 build 時覆蓋）
ARG BUILD_USER=appuser

# 安裝系統工具（包括 gosu 用於降權）
RUN apt-get update && apt-get install -y \
    curl wget jq tmux procps git gnupg2 lsb-release sudo zstd \
    && rm -rf /var/lib/apt/lists/*

# 安裝 gosu（輕量級 sudo 替代品，用於正確降權）
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gosu; \
    rm -rf /var/lib/apt/lists/*; \
    gosu nobody true

# 安裝 Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# 安裝 Ngrok
RUN curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
    tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
    tee /etc/apt/sources.list.d/ngrok.list && \
    apt-get update && apt-get install -y ngrok

# 安裝 AI Agent CLIs
RUN npm install -g @google/gemini-cli @anthropic-ai/claude-code @openai/codex && \
    echo "✅ AI CLI tools installed successfully" && \
    which gemini && which claude && which codex

# 建立非 root 用戶（使用動態指定的用戶名）
RUN useradd -m -s /bin/bash $BUILD_USER && \
    echo "$BUILD_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 【鏡像固化】只複製必要的生產代碼
RUN mkdir -p /app/octomatrix/docker-deploy/scripts

WORKDIR /app/octomatrix

# 安裝 Python 依賴
RUN pip install --no-cache-dir flask requests pyyaml apscheduler discord.py slack-sdk websockets aiohttp

# 複製 Python 腳本
COPY config.py /app/octomatrix/
COPY octo_router.py /app/octomatrix/
COPY telegram_gateway.py /app/octomatrix/
COPY discord_gateway.py /app/octomatrix/
COPY slack_socket_gateway.py /app/octomatrix/
COPY awake_manager.py /app/octomatrix/
COPY octo_reaper.py /app/octomatrix/
COPY auto_permission_responder.py /app/octomatrix/
COPY setup_agent_env.py /app/octomatrix/

# 複製 Bash 腳本
COPY start_octo_services.sh /app/octomatrix/
COPY status_octo_services.sh /app/octomatrix/
COPY stop_octo_services.sh /app/octomatrix/
COPY start_ngrok.sh /app/octomatrix/

# 複製設定範本與文件
COPY message_templates.yaml /app/octomatrix/
COPY AGENT_PROTOCOL.md /app/octomatrix/
COPY agent_home_rules.md /app/octomatrix/
COPY agent_rule_gen_template.txt /app/octomatrix/

# 複製工具目錄
COPY tools/ /app/octomatrix/tools/

# 複製容器入口腳本
COPY docker-deploy/scripts/entrypoint.sh /app/octomatrix/docker-deploy/scripts/

# 修正權限
RUN chown -R $BUILD_USER:$BUILD_USER /app && \
    chmod +x /app/octomatrix/docker-deploy/scripts/entrypoint.sh && \
    chmod +x /app/octomatrix/start_octo_services.sh && \
    chmod +x /app/octomatrix/status_octo_services.sh && \
    chmod +x /app/octomatrix/stop_octo_services.sh && \
    chmod +x /app/octomatrix/start_ngrok.sh

CMD ["/app/octomatrix/docker-deploy/scripts/entrypoint.sh"]