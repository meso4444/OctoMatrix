FROM python:3.11-slim

# Dynamically specify the container username (default: appuser, can be overridden during build)
ARG BUILD_USER=appuser

# Install system tools (including gosu for privilege de-escalation)
RUN apt-get update && apt-get install -y \
    curl wget jq tmux procps git gnupg2 lsb-release sudo zstd \
    && rm -rf /var/lib/apt/lists/*

# Install gosu (lightweight sudo alternative for correct privilege de-escalation)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gosu; \
    rm -rf /var/lib/apt/lists/*; \
    gosu nobody true

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install Ngrok
RUN curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
    tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
    tee /etc/apt/sources.list.d/ngrok.list && \
    apt-get update && apt-get install -y ngrok

# Install AI Agent CLIs
RUN npm install -g @google/gemini-cli @anthropic-ai/claude-code @openai/codex && \
    echo "✅ AI CLI tools installed successfully" && \
    which gemini && which claude && which codex

# Create non-root user (using the dynamically specified username)
RUN useradd -m -s /bin/bash $BUILD_USER && \
    echo "$BUILD_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# [Image Hardening] Only copy necessary production code
RUN mkdir -p /app/octomatrix/docker-deploy/scripts

WORKDIR /app/octomatrix

# Install Python dependencies
RUN pip install --no-cache-dir flask requests pyyaml apscheduler pillow discord.py slack-sdk websockets aiohttp

# 4. Copy core source code and configurations (Copy minimum files required)
COPY config.py /app/octomatrix/
COPY octo_router.py /app/octomatrix/
COPY telegram_gateway.py /app/octomatrix/
COPY discord_gateway.py /app/octomatrix/
COPY slack_socket_gateway.py /app/octomatrix/
COPY awake_manager.py /app/octomatrix/
COPY octo_reaper.py /app/octomatrix/
COPY auto_permission_responder.py /app/octomatrix/
COPY setup_agent_env.py /app/octomatrix/

# 5. Copy startup and management scripts
COPY start_octo_services.sh /app/octomatrix/
COPY status_octo_services.sh /app/octomatrix/
COPY stop_octo_services.sh /app/octomatrix/
COPY start_ngrok.sh /app/octomatrix/

# 6. Copy templates and rules
COPY message_templates.yaml /app/octomatrix/
COPY AGENT_PROTOCOL.md /app/octomatrix/
COPY agent_home_rules.md /app/octomatrix/
COPY agent_rule_gen_template.txt /app/octomatrix/

# 7. Copy Tools and Skills
COPY tools/ /app/octomatrix/tools/
COPY skills/ /app/octomatrix/skills/

# 8. Pre-build Skills (Install OS packages and dependencies dynamically based on setup_docker.sh)
ARG INSTANCE_NAME
# Use wildcard trick to safely copy dynamically generated dependency files (will not fail if missing, as long as extract_skill_deps.py exists)
COPY docker-deploy/extract_skill_deps.py docker-deploy/dynamic_requirements.${INSTANCE_NAME}.tx[t] docker-deploy/dynamic_prebuild.${INSTANCE_NAME}.s[h] /tmp/dynamic_deps/

RUN echo "⚙️ Pre-executing registered Skill dependencies and setup scripts..." && \
    if [ -f "/tmp/dynamic_deps/dynamic_requirements.${INSTANCE_NAME}.txt" ] && [ -s "/tmp/dynamic_deps/dynamic_requirements.${INSTANCE_NAME}.txt" ]; then \
        echo "🐍 Found Python dependencies list, installing..."; \
        pip install --no-cache-dir -r "/tmp/dynamic_deps/dynamic_requirements.${INSTANCE_NAME}.txt"; \
    fi && \
    if [ -f "/tmp/dynamic_deps/dynamic_prebuild.${INSTANCE_NAME}.sh" ]; then \
        echo "🚀 Executing dynamic skill repackaging and OS package installation script..."; \
        chmod +x "/tmp/dynamic_deps/dynamic_prebuild.${INSTANCE_NAME}.sh"; \
        bash "/tmp/dynamic_deps/dynamic_prebuild.${INSTANCE_NAME}.sh"; \
    fi && \
    rm -rf /tmp/dynamic_deps

# Copy container entrypoint script
COPY docker-deploy/scripts/entrypoint.sh /app/octomatrix/docker-deploy/scripts/

# Fix permissions
RUN chown -R $BUILD_USER:$BUILD_USER /app && \
    chmod +x /app/octomatrix/docker-deploy/scripts/entrypoint.sh && \
    chmod +x /app/octomatrix/start_octo_services.sh && \
    chmod +x /app/octomatrix/status_octo_services.sh && \
    chmod +x /app/octomatrix/stop_octo_services.sh && \
    chmod +x /app/octomatrix/start_ngrok.sh

CMD ["/app/octomatrix/docker-deploy/scripts/entrypoint.sh"]
