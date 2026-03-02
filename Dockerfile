FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    pyrogram==2.0.106 \
    TgCrypto \
    motor \
    yt-dlp \
    aiohttp \
    ffmpeg-python

# Create temp download directory
RUN mkdir -p /tmp/musicbot_dl

# Copy all bot files
COPY . .

# Environment variables (override at runtime)
ENV BOT_TOKEN=""
ENV API_ID=""
ENV API_HASH=""
ENV MONGO_URI=""
ENV OWNER_ID="7408191872"

CMD ["python", "bot.py"]

