FROM n8nio/n8n:latest

USER root

RUN apk add --no-cache \
    ffmpeg \
    yt-dlp \
    python3 \
    py3-pip

ENV NODE_OPTIONS=--max-old-space-size=400
ENV N8N_DEFAULT_BINARY_DATA_MODE=filesystem
ENV EXECUTIONS_DATA_PRUNE=true
ENV EXECUTIONS_DATA_MAX_AGE=1
ENV N8N_PAYLOAD_SIZE_MAX=16

USER node
