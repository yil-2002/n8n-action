FROM node:18-alpine

RUN apk add --no-cache \
    ffmpeg \
    python3 \
    py3-pip

RUN pip3 install yt-dlp --break-system-packages

RUN npm install -g n8n@1.94.1

ENV N8N_DEFAULT_BINARY_DATA_MODE=filesystem
ENV EXECUTIONS_DATA_PRUNE=true
ENV EXECUTIONS_DATA_MAX_AGE=1
ENV N8N_PAYLOAD_SIZE_MAX=16
ENV N8N_PORT=5678

EXPOSE 5678

ENTRYPOINT ["n8n"]
CMD ["start"]



