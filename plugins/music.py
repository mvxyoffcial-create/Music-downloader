import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from utils.youtube import search_youtube, download_audio, download_video, get_thumbnail
from utils.forcesub import check_force_sub, force_sub_markup
from config import Config
from script import script

DOWNLOAD_TMP = "/tmp/musicbot_dl"
os.makedirs(DOWNLOAD_TMP, exist_ok=True)

RESULTS_PER_PAGE = 5

# In-memory search cache: {user_id: [results]}
search_cache = {}


def results_keyboard(results: list, user_id: int, page: int = 0):
    """Build paginated inline keyboard for search results (5 per page)."""
    total = len(results)
    total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    start = page * RESULTS_PER_PAGE
    end = min(start + RESULTS_PER_PAGE, total)
    page_results = results[start:end]

    buttons = []
    for i, r in enumerate(page_results):
        actual_idx = start + i
        title = r["title"][:38] + "…" if len(r["title"]) > 38 else r["title"]
        buttons.append([InlineKeyboardButton(
            f"🎵 {title} [{r['duration']}]",
            callback_data=f"sel_{user_id}_{actual_idx}"
        )])

    # Navigation row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"page_{user_id}_{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{user_id}_{page + 1}"))

    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(buttons)


def format_type_keyboard(user_id: int, idx: int, page: int = 0):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"dl_audio_{user_id}_{idx}_{page}"),
            InlineKeyboardButton("🎬 MP4 Video", callback_data=f"dl_video_{user_id}_{idx}_{page}"),
        ],
        [InlineKeyboardButton("🔙 Back to Results", callback_data=f"page_{user_id}_{page}")]
    ])


@Client.on_message(filters.private & ~filters.command(["start", "help", "about", "stats", "broadcast", "info"]))
async def music_search(client: Client, message: Message):
    # Check force sub
    not_joined = await check_force_sub(client, message.from_user.id)
    if not_joined:
        await message.reply_photo(
            photo=Config.WELCOME_IMG,
            caption=script.FORCE_SUB_TXT,
            reply_markup=force_sub_markup(not_joined)
        )
        return

    query = message.text
    if not query or query.startswith("/"):
        return

    searching_msg = await message.reply("🔍 <b>Searching for your song...</b>")

    try:
        results = await search_youtube(query, max_results=10)
        if not results:
            await searching_msg.edit("❌ <b>No results found. Try a different query.</b>")
            return

        user_id = message.from_user.id
        search_cache[user_id] = results

        await searching_msg.edit(
            text=(
                f"🎵 <b>Results for:</b> <code>{query}</code>\n"
                f"<b>Found {len(results)} results — Select a song 👇</b>"
            ),
            reply_markup=results_keyboard(results, user_id, page=0)
        )

    except Exception as e:
        await searching_msg.edit(f"❌ <b>Search error:</b> <code>{str(e)[:200]}</code>")


# ── Pagination ──────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^page_(\d+)_(\d+)$"))
async def paginate_results(client: Client, query: CallbackQuery):
    _, user_id, page = query.data.split("_")
    user_id, page = int(user_id), int(page)

    if query.from_user.id != user_id:
        await query.answer("Not your search!", show_alert=True)
        return

    results = search_cache.get(user_id)
    if not results:
        await query.answer("Session expired. Search again.", show_alert=True)
        return

    await query.message.edit_text(
        text=f"🎵 <b>Select a song 👇</b>  (Page {page + 1})",
        reply_markup=results_keyboard(results, user_id, page=page)
    )


@Client.on_callback_query(filters.regex(r"^noop$"))
async def noop(client: Client, query: CallbackQuery):
    await query.answer()


# ── Song Selected ────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^sel_(\d+)_(\d+)$"))
async def song_selected(client: Client, query: CallbackQuery):
    _, user_id, idx = query.data.split("_")
    user_id, idx = int(user_id), int(idx)

    if query.from_user.id != user_id:
        await query.answer("Not your search!", show_alert=True)
        return

    results = search_cache.get(user_id, [])
    if not results or idx >= len(results):
        await query.answer("Session expired. Search again.", show_alert=True)
        return

    song = results[idx]
    page = idx // RESULTS_PER_PAGE

    text = (
        f"🎵 <b>{song['title']}</b>\n"
        f"👤 <b>Artist:</b> {song['channel']}\n"
        f"⏱️ <b>Duration:</b> {song['duration']}\n\n"
        f"<b>Choose download format 👇</b>"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=format_type_keyboard(user_id, idx, page)
    )


# ── Download ─────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^dl_(audio|video)_(\d+)_(\d+)_(\d+)$"))
async def download_song(client: Client, query: CallbackQuery):
    parts = query.data.split("_")
    # dl_audio_userid_idx_page  →  parts = ['dl','audio','userid','idx','page']
    fmt = parts[1]
    user_id = int(parts[2])
    idx = int(parts[3])
    page = int(parts[4])

    if query.from_user.id != user_id:
        await query.answer("Not your session!", show_alert=True)
        return

    results = search_cache.get(user_id, [])
    if not results or idx >= len(results):
        await query.answer("Session expired. Search again.", show_alert=True)
        return

    song = results[idx]

    await query.message.edit_text(
        f"⬇️ <b>Downloading</b> <code>{song['title']}</code>...\n"
        f"<i>Please wait ⏳</i>"
    )

    try:
        # Thumbnail
        thumb_path = None
        try:
            thumb_bytes = await get_thumbnail(song["id"])
            if thumb_bytes:
                thumb_path = f"{DOWNLOAD_TMP}/{song['id']}_thumb.jpg"
                with open(thumb_path, "wb") as f:
                    f.write(thumb_bytes)
        except Exception:
            pass

        me = await client.get_me()
        caption = (
            f"🎵 <b>{song['title']}</b>\n"
            f"👤 <b>Artist:</b> {song['channel']}\n"
            f"⏱️ <b>Duration:</b> {song['duration']}\n\n"
            f"<b>Downloaded by</b> @{me.username}"
        )

        if fmt == "audio":
            file_path, info = await download_audio(song["url"], DOWNLOAD_TMP)
            duration_sec = int(info.get("duration", 0) or 0)

            await client.send_audio(
                chat_id=user_id,
                audio=file_path,
                title=song["title"],
                performer=song["channel"],
                duration=duration_sec,
                thumb=thumb_path,
                caption=caption
            )
            try:
                os.remove(file_path)
            except Exception:
                pass

        else:
            file_path, info = await download_video(song["url"], DOWNLOAD_TMP)
            duration_sec = int(info.get("duration", 0) or 0)

            await client.send_video(
                chat_id=user_id,
                video=file_path,
                duration=duration_sec,
                width=info.get("width", 0),
                height=info.get("height", 0),
                thumb=thumb_path,
                caption=caption
            )
            try:
                os.remove(file_path)
            except Exception:
                pass

        if thumb_path:
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        await query.message.delete()

    except Exception as e:
        err = str(e)
        # Strip ANSI color codes for cleaner display
        import re
        err = re.sub(r'\x1b\[[0-9;]*m', '', err)
        await query.message.edit_text(
            f"❌ <b>Download failed!</b>\n<code>{err[:300]}</code>\n\n"
            f"<i>Try another song or try again later.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data=f"page_{user_id}_{page}")]
            ])
        )
