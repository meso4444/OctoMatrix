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
RUN pip install --no-cache-dir flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp

# 4. 複製核心原始碼與設定檔 (複製所需的最少檔案)
COPY config.py /app/octomatrix/
COPY octo_router.py /app/octomatrix/
COPY telegram_gateway.py /app/octomatrix/
COPY discord_gateway.py /app/octomatrix/
COPY slack_socket_gateway.py /app/octomatrix/
COPY awake_manager.py /app/octomatrix/
COPY octo_reaper.py /app/octomatrix/
COPY auto_permission_responder.py /app/octomatrix/
COPY setup_agent_env.py /app/octomatrix/

# 5. 複製啟動與管理腳本
COPY start_octo_services.sh /app/octomatrix/
COPY status_octo_services.sh /app/octomatrix/
COPY stop_octo_services.sh /app/octomatrix/
COPY start_ngrok.sh /app/octomatrix/

# 6. 複製模板與規則
COPY message_templates.yaml /app/octomatrix/
COPY AGENT_PROTOCOL.md /app/octomatrix/
COPY agent_home_rules.md /app/octomatrix/
COPY agent_rule_gen_template.txt /app/octomatrix/

# 7. 複製 Tools 與 Skills
COPY tools/ /app/octomatrix/tools/
COPY skills/ /app/octomatrix/skills/

# 8. 預先編譯 Skills (在建置階段安裝系統套件與依賴並重新打包)
# 這會解壓縮所有技能包，尋找 setup.sh 與 requirements.txt 並執行，然後將包含 node_modules 的完整目錄重新打包
RUN echo "⚙️ 預先執行 Skills 安裝腳本並封裝..." && \
    for archive in /app/octomatrix/skills/*.tar.gz; do \
        if [ -f "$archive" ]; then \
            echo "📦 處理技能包: $archive"; \
            tmp_dir="/tmp/skill_build_tmp"; \
            rm -rf "$tmp_dir" && mkdir -p "$tmp_dir"; \
            tar -xzf "$archive" -C "$tmp_dir"; \
            for req_file in "$tmp_dir"/*/requirements.txt "$tmp_dir"/requirements.txt; do \
                if [ -f "$req_file" ]; then \
                    echo "🐍 發現 Python 依賴，正在安裝: $req_file"; \
                    pip install --no-cache-dir -r "$req_file"; \
                fi; \
            done; \
            for setup_script in "$tmp_dir"/*/setup.sh "$tmp_dir"/setup.sh; do \
                if [ -f "$setup_script" ]; then \
                    echo "🚀 執行安裝腳本: $setup_script"; \
                    chmod +x "$setup_script"; \
                    (cd "$(dirname "$setup_script")" && bash setup.sh); \
                fi; \
            done; \
            echo "📦 重新打包技能包 (包含依賴)..."; \
            (cd "$tmp_dir" && tar -czf "$archive" *); \
            rm -rf "$tmp_dir"; \
        fi; \
    done

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