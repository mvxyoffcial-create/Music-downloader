import asyncio
import os
import re
import aiohttp

DOWNLOAD_TMP = "/tmp/musicbot_dl"
os.makedirs(DOWNLOAD_TMP, exist_ok=True)

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://piped-api.garudalinux.org",
    "https://api.piped.yt",
    "https://pipedapi.adminforge.de",
]

SAAVN_API = "https://saavn.dev/api"


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)[:80]


def _extract_video_id(url: str) -> str:
    for p in [r"youtu\.be/([^?&\s]+)", r"[?&]v=([^&\s]+)", r"shorts/([^?&\s]+)"]:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


# ─── Search: JioSaavn first (music-focused, no bot issues) ──────────────────

async def search_youtube(query: str, max_results: int = 10):
    """Search via JioSaavn API — best for music, no bot detection."""
    try:
        results = await _search_saavn(query, max_results)
        if results:
            return results
    except Exception:
        pass

    # Fallback: Piped search
    try:
        results = await _search_piped(query, max_results)
        if results:
            return results
    except Exception:
        pass

    return []


async def _search_saavn(query: str, max_results: int):
    async with aiohttp.ClientSession() as session:
        url = f"{SAAVN_API}/search/songs?query={aiohttp.helpers.requote_uri(query)}&limit={max_results}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            songs = data.get("data", {}).get("results", [])
            results = []
            for song in songs:
                duration_sec = int(song.get("duration", 0) or 0)
                mins, secs = divmod(duration_sec, 60)
                # Get best image
                images = song.get("image", [])
                thumbnail = images[-1].get("url", "") if images else ""
                # Get artists
                artists = song.get("artists", {}).get("primary", [])
                artist_name = artists[0].get("name", "Unknown") if artists else "Unknown"
                results.append({
                    "id": song.get("id", ""),
                    "title": song.get("name", "Unknown"),
                    "url": song.get("id", ""),  # saavn ID used for download
                    "duration": f"{mins}:{secs:02d}",
                    "channel": artist_name,
                    "thumbnail": thumbnail,
                    "source": "saavn",
                    "download_url": _best_saavn_url(song.get("downloadUrl", [])),
                })
            return results


def _best_saavn_url(download_urls: list) -> str:
    """Get highest quality download URL from JioSaavn."""
    if not download_urls:
        return ""
    # Sort by quality: 320kbps > 160kbps > 96kbps > etc
    quality_order = {"320kbps": 4, "160kbps": 3, "96kbps": 2, "48kbps": 1, "12kbps": 0}
    best = max(download_urls, key=lambda x: quality_order.get(x.get("quality", ""), 0))
    return best.get("url", "")


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
                            "source": "piped",
                            "download_url": "",
                        })
                    if results:
                        return results
            except Exception:
                continue
    return []


# ─── Audio Download ──────────────────────────────────────────────────────────

async def download_audio(song: dict, output_path: str = DOWNLOAD_TMP):
    """Download audio. Uses direct Saavn URL or Piped stream."""
    source = song.get("source", "piped")

    if source == "saavn" and song.get("download_url"):
        return await _download_direct(song["download_url"], song, output_path, "mp3")

    # Piped stream download
    video_id = _extract_video_id(song.get("url", "")) or song.get("id", "")
    if video_id:
        return await _audio_piped(video_id, song, output_path)

    raise Exception("No download source available")


async def _download_direct(url: str, song: dict, output_path: str, ext: str):
    """Direct file download (for Saavn)."""
    title = _safe_filename(song.get("title", "audio"))
    file_path = f"{output_path}/{title}.{ext}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.jiosaavn.com/",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            if resp.status != 200:
                raise Exception(f"Direct download failed: {resp.status}")
            with open(file_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

    # If not mp3, convert
    if ext != "mp3":
        mp3_path = file_path.replace(f".{ext}", ".mp3")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", file_path, "-vn",
            "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        try:
            os.remove(file_path)
        except Exception:
            pass
        file_path = mp3_path

    info = {
        "title": song.get("title", "Unknown"),
        "uploader": song.get("channel", "Unknown"),
        "duration": _duration_to_sec(song.get("duration", "0:00")),
    }
    return file_path, info


async def _audio_piped(video_id: str, song: dict, output_path: str):
    data = await _get_piped_stream(video_id)
    if not data:
        raise Exception("Could not fetch stream from Piped")

    streams = sorted(data.get("audioStreams", []), key=lambda x: x.get("bitrate", 0), reverse=True)
    if not streams:
        raise Exception("No audio streams available")

    stream_url = streams[0].get("url")
    if not stream_url:
        raise Exception("No stream URL")

    title = _safe_filename(data.get("title", video_id))
    raw_path = f"{output_path}/{title}.webm"
    mp3_path = f"{output_path}/{title}.mp3"

    async with aiohttp.ClientSession() as session:
        async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            if resp.status != 200:
                raise Exception(f"Stream error: {resp.status}")
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
        raise Exception("Audio conversion failed")

    return mp3_path, {
        "title": data.get("title", video_id),
        "uploader": data.get("uploader", "Unknown"),
        "duration": data.get("duration", 0),
    }


# ─── Video Download ──────────────────────────────────────────────────────────

async def download_video(song: dict, output_path: str = DOWNLOAD_TMP):
    video_id = _extract_video_id(song.get("url", "")) or song.get("id", "")
    if not video_id:
        raise Exception("No video ID found")
    return await _video_piped(video_id, song, output_path)


async def _video_piped(video_id: str, song: dict, output_path: str):
    data = await _get_piped_stream(video_id)
    if not data:
        raise Exception("Could not fetch stream from Piped")

    video_streams = data.get("videoStreams", [])
    if not video_streams:
        raise Exception("No video streams available")

    def res_key(s):
        try:
            return int(s.get("quality", "0p").replace("p", ""))
        except Exception:
            return 0

    video_streams.sort(key=res_key, reverse=True)
    chosen = next((s for s in video_streams if res_key(s) <= 720), video_streams[-1])
    stream_url = chosen.get("url")
    if not stream_url:
        raise Exception("No video stream URL")

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
        raise Exception("Video merge failed")

    return mp4_path, {
        "title": data.get("title", video_id),
        "uploader": data.get("uploader", "Unknown"),
        "duration": data.get("duration", 0),
        "width": chosen.get("width", 1280),
        "height": chosen.get("height", 720),
    }


# ─── Piped stream helper ─────────────────────────────────────────────────────

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


# ─── Thumbnail ───────────────────────────────────────────────────────────────

async def get_thumbnail(song: dict) -> bytes:
    thumbnail_url = song.get("thumbnail", "")
    if not thumbnail_url:
        vid_id = song.get("id", "")
        thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        pass
    return None


# ─── Utils ───────────────────────────────────────────────────────────────────

def _duration_to_sec(duration_str: str) -> int:
    try:
        parts = duration_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except Exception:
        return 0
