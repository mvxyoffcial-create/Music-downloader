import asyncio
import os
import re
import aiohttp
from yt_dlp import YoutubeDL

DOWNLOAD_TMP = "/tmp/musicbot_dl"
os.makedirs(DOWNLOAD_TMP, exist_ok=True)

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://piped-api.garudalinux.org",
    "https://api.piped.yt",
]


# ─── Search ─────────────────────────────────────────────────────────────────

async def search_youtube(query: str, max_results: int = 10):
    try:
        results = await _search_piped(query, max_results)
        if results:
            return results
    except Exception:
        pass
    return await _search_ytdlp(query, max_results)


async def _search_piped(query: str, max_results: int):
    async with aiohttp.ClientSession() as session:
        for instance in PIPED_INSTANCES:
            try:
                encoded = aiohttp.helpers.requote_uri(query)
                url = f"{instance}/search?q={encoded}&filter=music_songs"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    items = data.get("items", [])[:max_results]
                    results = []
                    for item in items:
                        duration_sec = item.get("duration", 0) or 0
                        mins, secs = divmod(int(duration_sec), 60)
                        vid_id = item.get("url", "").replace("/watch?v=", "")
                        results.append({
                            "id": vid_id,
                            "title": item.get("title", "Unknown"),
                            "url": f"https://youtu.be/{vid_id}",
                            "duration": f"{mins}:{secs:02d}",
                            "channel": item.get("uploaderName", "Unknown"),
                            "thumbnail": item.get("thumbnail") or f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
                        })
                    if results:
                        return results
            except Exception:
                continue
    return []


async def _search_ytdlp(query: str, max_results: int):
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    loop = asyncio.get_event_loop()

    def _run():
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return result.get("entries", [])

    entries = await loop.run_in_executor(None, _run)
    results = []
    for entry in (entries or []):
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
            "channel": entry.get("uploader") or "Unknown",
            "thumbnail": f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
        })
    return results


# ─── Piped stream fetcher ────────────────────────────────────────────────────

async def _get_piped_stream(video_id: str):
    async with aiohttp.ClientSession() as session:
        for instance in PIPED_INSTANCES:
            try:
                url = f"{instance}/streams/{video_id}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                continue
    return None


def _extract_video_id(url: str) -> str:
    for p in [r"youtu\.be/([^?&]+)", r"[?&]v=([^&]+)", r"shorts/([^?&]+)"]:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:80]


# ─── Audio Download ──────────────────────────────────────────────────────────

async def download_audio(url: str, output_path: str = DOWNLOAD_TMP):
    video_id = _extract_video_id(url)
    if video_id:
        try:
            return await _audio_piped(video_id, output_path)
        except Exception:
            pass
    return await _audio_ytdlp(url, output_path)


async def _audio_piped(video_id: str, output_path: str):
    data = await _get_piped_stream(video_id)
    if not data:
        raise Exception("Piped: no data")

    streams = sorted(data.get("audioStreams", []), key=lambda x: x.get("bitrate", 0), reverse=True)
    if not streams:
        raise Exception("Piped: no audio streams")

    stream_url = streams[0].get("url")
    if not stream_url:
        raise Exception("Piped: no stream URL")

    title = _safe_filename(data.get("title", video_id))
    raw_path = f"{output_path}/{title}.webm"
    mp3_path = f"{output_path}/{title}.mp3"

    async with aiohttp.ClientSession() as session:
        async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            if resp.status != 200:
                raise Exception(f"Piped stream error: {resp.status}")
            with open(raw_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", raw_path, "-vn",
        "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3_path,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.communicate()

    try:
        os.remove(raw_path)
    except Exception:
        pass

    if not os.path.exists(mp3_path):
        raise Exception("FFmpeg conversion failed")

    return mp3_path, {
        "title": data.get("title", video_id),
        "uploader": data.get("uploader", "Unknown"),
        "duration": data.get("duration", 0),
    }


async def _audio_ytdlp(url: str, output_path: str):
    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"},
    }
    loop = asyncio.get_event_loop()

    def _run():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            return base + ".mp3", info

    return await loop.run_in_executor(None, _run)


# ─── Video Download ──────────────────────────────────────────────────────────

async def download_video(url: str, output_path: str = DOWNLOAD_TMP):
    video_id = _extract_video_id(url)
    if video_id:
        try:
            return await _video_piped(video_id, output_path)
        except Exception:
            pass
    return await _video_ytdlp(url, output_path)


async def _video_piped(video_id: str, output_path: str):
    data = await _get_piped_stream(video_id)
    if not data:
        raise Exception("Piped: no data")

    video_streams = data.get("videoStreams", [])
    if not video_streams:
        raise Exception("Piped: no video streams")

    def res_key(s):
        try:
            return int(s.get("quality", "0p").replace("p", ""))
        except Exception:
            return 0

    video_streams.sort(key=res_key, reverse=True)
    chosen = next((s for s in video_streams if res_key(s) <= 720), video_streams[-1])
    stream_url = chosen.get("url")
    if not stream_url:
        raise Exception("Piped: no video stream URL")

    audio_streams = sorted(data.get("audioStreams", []), key=lambda x: x.get("bitrate", 0), reverse=True)

    title = _safe_filename(data.get("title", video_id))
    vid_raw = f"{output_path}/{title}_v.webm"
    aud_raw = f"{output_path}/{title}_a.webm"
    mp4_path = f"{output_path}/{title}.mp4"

    async with aiohttp.ClientSession() as session:
        async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            with open(vid_raw, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

        has_audio = False
        if audio_streams and chosen.get("videoOnly", True):
            aud_url = audio_streams[0].get("url")
            if aud_url:
                async with session.get(aud_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    with open(aud_raw, "wb") as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            f.write(chunk)
                has_audio = True

    if has_audio:
        cmd = ["ffmpeg", "-y", "-i", vid_raw, "-i", aud_raw, "-c:v", "copy", "-c:a", "aac", mp4_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", vid_raw, "-c", "copy", mp4_path]

    proc = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.communicate()

    for f in [vid_raw, aud_raw]:
        try:
            os.remove(f)
        except Exception:
            pass

    if not os.path.exists(mp4_path):
        raise Exception("FFmpeg merge failed")

    return mp4_path, {
        "title": data.get("title", video_id),
        "uploader": data.get("uploader", "Unknown"),
        "duration": data.get("duration", 0),
        "width": chosen.get("width", 1280),
        "height": chosen.get("height", 720),
    }


async def _video_ytdlp(url: str, output_path: str):
    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "format": "best[ext=mp4][height<=720]/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"},
    }
    loop = asyncio.get_event_loop()

    def _run():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info), info

    return await loop.run_in_executor(None, _run)


# ─── Thumbnail ───────────────────────────────────────────────────────────────

async def get_thumbnail(video_id: str) -> bytes:
    url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return await resp.read()
    return None
