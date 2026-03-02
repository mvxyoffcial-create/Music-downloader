# 🎵 Music Downloader Bot

A powerful Telegram Music Downloader Bot built with Pyrogram.

## Features
- 🎵 YouTube Music Search & Download (MP3/MP4)
- 📢 Force Subscribe to 2 channels
- 🖼️ Animated sticker on start (auto-deletes after 2s)
- 🌅 Random anime wallpaper as welcome image
- 📊 Admin stats command
- 📣 Broadcast to all users
- ℹ️ /info command with profile photo
- 🗄️ MongoDB database
- ⚡ 500 workers

## Setup

### 1. Clone & Install
```bash
pip install -r requirements.txt
```
> **Note:** FFmpeg must be installed on your system: `apt install ffmpeg`

### 2. Configure
Copy `.env.example` to `.env` and fill:
```
BOT_TOKEN=        # From @BotFather
API_ID=           # From my.telegram.org
API_HASH=         # From my.telegram.org
MONGO_URI=        # MongoDB connection string
OWNER_ID=         # Your Telegram user ID
```

### 3. Run
```bash
python bot.py
```

## Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Start the bot | All |
| `/info` | View your Telegram info + profile pic | All |
| `/stats` | View bot user statistics | Owner |
| `/broadcast` | Broadcast a message to all users | Owner |

## Music Search
Just type a **song name** or **YouTube link** in the private chat!  
Results appear as inline buttons → select a song → choose **MP3** or **MP4**.

## Developer
[@Venuboyy](https://t.me/Venuboyy)
