FROM n8nio/n8n:latest

USER root

RUN apk add --no-cache ffmpeg python3 py3-pip \
    && pip3 install yt-dlp --break-system-packages \
    && apk info n8n 2>/dev/null || true

USER node

ENV N8N_DEFAULT_BINARY_DATA_MODE=filesystem
ENV EXECUTIONS_DATA_PRUNE=true
ENV EXECUTIONS_DATA_MAX_AGE=1
ENV N8N_PAYLOAD_SIZE_MAX=16






