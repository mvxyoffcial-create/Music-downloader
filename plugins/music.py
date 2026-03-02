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

# In-memory search cache: {user_id: [results]}
search_cache = {}

DOWNLOAD_TMP = "/tmp/musicbot_dl"
os.makedirs(DOWNLOAD_TMP, exist_ok=True)


def results_keyboard(results, user_id: int):
    """Build inline keyboard for search results."""
    buttons = []
    for i, r in enumerate(results):
        title = r["title"][:40] + "…" if len(r["title"]) > 40 else r["title"]
        buttons.append([InlineKeyboardButton(
            f"🎵 {title} [{r['duration']}]",
            callback_data=f"sel_{user_id}_{i}"
        )])
    return InlineKeyboardMarkup(buttons)


def format_type_keyboard(user_id: int, idx: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"dl_audio_{user_id}_{idx}"),
            InlineKeyboardButton("🎬 MP4 Video", callback_data=f"dl_video_{user_id}_{idx}"),
        ],
        [InlineKeyboardButton("🔙 Back to Results", callback_data=f"back_{user_id}")]
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
        results = await search_youtube(query, max_results=5)
        if not results:
            await searching_msg.edit("❌ <b>No results found. Try a different query.</b>")
            return

        user_id = message.from_user.id
        search_cache[user_id] = results

        # Show results as inline buttons
        await searching_msg.edit(
            text=f"🎵 <b>Results for:</b> <code>{query}</code>\n\n<b>Select a song below 👇</b>",
            reply_markup=results_keyboard(results, user_id)
        )

    except Exception as e:
        await searching_msg.edit(f"❌ <b>Error:</b> {str(e)[:200]}")


@Client.on_callback_query(filters.regex(r"^sel_(\d+)_(\d+)$"))
async def song_selected(client: Client, query: CallbackQuery):
    _, user_id, idx = query.data.split("_")
    user_id, idx = int(user_id), int(idx)

    if query.from_user.id != user_id:
        await query.answer("This is not your search!", show_alert=True)
        return

    results = search_cache.get(user_id, [])
    if not results or idx >= len(results):
        await query.answer("Session expired. Search again.", show_alert=True)
        return

    song = results[idx]
    text = (
        f"🎵 <b>{song['title']}</b>\n"
        f"👤 <b>Artist:</b> {song['channel']}\n"
        f"⏱️ <b>Duration:</b> {song['duration']}\n\n"
        f"<b>Choose download format:</b>"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=format_type_keyboard(user_id, idx)
    )


@Client.on_callback_query(filters.regex(r"^back_(\d+)$"))
async def back_to_results(client: Client, query: CallbackQuery):
    user_id = int(query.data.split("_")[1])
    if query.from_user.id != user_id:
        await query.answer("Not your session!", show_alert=True)
        return

    results = search_cache.get(user_id, [])
    if not results:
        await query.answer("Session expired. Search again.", show_alert=True)
        return

    await query.message.edit_text(
        text="🎵 <b>Select a song below 👇</b>",
        reply_markup=results_keyboard(results, user_id)
    )


@Client.on_callback_query(filters.regex(r"^dl_(audio|video)_(\d+)_(\d+)$"))
async def download_song(client: Client, query: CallbackQuery):
    parts = query.data.split("_")
    fmt, user_id, idx = parts[1], int(parts[2]), int(parts[3])

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
        f"<i>This may take a moment ⏳</i>"
    )

    try:
        # Download thumbnail
        thumb_bytes = None
        try:
            thumb_bytes = await get_thumbnail(song["id"])
            thumb_path = f"{DOWNLOAD_TMP}/{song['id']}_thumb.jpg"
            with open(thumb_path, "wb") as f:
                f.write(thumb_bytes)
        except Exception:
            thumb_path = None

        if fmt == "audio":
            file_path, info = await download_audio(song["url"], DOWNLOAD_TMP)
            duration_sec = info.get("duration", 0) or 0

            await client.send_audio(
                chat_id=query.from_user.id,
                audio=file_path,
                title=song["title"],
                performer=song["channel"],
                duration=int(duration_sec),
                thumb=thumb_path,
                caption=(
                    f"🎵 <b>{song['title']}</b>\n"
                    f"👤 <b>Artist:</b> {song['channel']}\n"
                    f"⏱️ <b>Duration:</b> {song['duration']}\n\n"
                    f"<b>Downloaded by</b> @{(await client.get_me()).username}"
                )
            )
            # Cleanup
            try:
                os.remove(file_path)
            except Exception:
                pass

        else:  # video
            file_path, info = await download_video(song["url"], DOWNLOAD_TMP)
            duration_sec = info.get("duration", 0) or 0
            width = info.get("width", 0)
            height = info.get("height", 0)

            await client.send_video(
                chat_id=query.from_user.id,
                video=file_path,
                duration=int(duration_sec),
                width=width,
                height=height,
                thumb=thumb_path,
                caption=(
                    f"🎬 <b>{song['title']}</b>\n"
                    f"👤 <b>Artist:</b> {song['channel']}\n"
                    f"⏱️ <b>Duration:</b> {song['duration']}\n\n"
                    f"<b>Downloaded by</b> @{(await client.get_me()).username}"
                )
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
        await query.message.edit_text(
            f"❌ <b>Download failed!</b>\n<code>{str(e)[:300]}</code>"
        )
