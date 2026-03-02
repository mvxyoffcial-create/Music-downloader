import asyncio
import os
import aiohttp
from yt_dlp import YoutubeDL

DOWNLOAD_TMP = "/tmp/musicbot_dl"
os.makedirs(DOWNLOAD_TMP, exist_ok=True)

# yt-dlp options to bypass bot detection
BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extractor_retries": 3,
    "socket_timeout": 30,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    # Use piped.video as a proxy to avoid bot detection
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
            "player_skip": ["webpage", "configs"],
        }
    },
}


async def search_youtube(query: str, max_results: int = 10):
    """Search YouTube and return list of results (fetch more for pagination)."""
    ydl_opts = {
        **BASE_OPTS,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
    }
    loop = asyncio.get_event_loop()

    def _search():
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return result.get("entries", [])

    entries = await loop.run_in_executor(None, _search)
    results = []
    for entry in entries:
        if not entry:
            continue
        duration_sec = entry.get("duration", 0) or 0
        mins, secs = divmod(int(duration_sec), 60)
        vid_id = entry.get("id", "")
        results.append({
            "id": vid_id,
            "title": entry.get("title", "Unknown"),
            "url": f"https://youtu.be/{vid_id}",
            "duration": f"{mins}:{secs:02d}",
            "channel": entry.get("uploader") or entry.get("channel") or "Unknown",
            "thumbnail": entry.get("thumbnail") or f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
        })
    return results


async def download_audio(url: str, output_path: str = DOWNLOAD_TMP):
    """Download audio from YouTube URL with bot bypass."""
    ydl_opts = {
        **BASE_OPTS,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    loop = asyncio.get_event_loop()

    def _download():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base = os.path.splitext(filename)[0]
            mp3_path = base + ".mp3"
            return mp3_path, info

    return await loop.run_in_executor(None, _download)


async def download_video(url: str, output_path: str = DOWNLOAD_TMP):
    """Download video from YouTube URL with bot bypass."""
    ydl_opts = {
        **BASE_OPTS,
        "format": "best[ext=mp4][filesize<50M]/best[filesize<50M]/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
    }

    loop = asyncio.get_event_loop()

    def _download():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info

    return await loop.run_in_executor(None, _download)


async def get_thumbnail(video_id: str) -> bytes:
    """Download thumbnail bytes for a video."""
    url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    return None
