import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from script import script
from config import Config
from utils.database import add_user
from utils.forcesub import check_force_sub, force_sub_markup


async def get_random_wallpaper() -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                Config.RANDOM_WALLPAPER_API,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return str(resp.url)
    except Exception:
        return Config.WELCOME_IMG


def start_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Channel 1", url="https://t.me/zerodev2"),
            InlineKeyboardButton("📢 Channel 2", url="https://t.me/mvxyoffcail"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about"),
        ],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Venuboyy")]
    ])


@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.first_name, user.username)

    # Force sub check — reply to /start
    not_joined = await check_force_sub(client, user.id)
    if not_joined:
        await message.reply_photo(
            photo=Config.WELCOME_IMG,
            caption=script.FORCE_SUB_TXT,
            reply_markup=force_sub_markup(not_joined),
            quote=True
        )
        return

    # Send sticker as reply, auto-delete after 2 seconds
    sticker_msg = await message.reply_sticker(
        Config.START_STICKER,
        quote=True
    )
    await asyncio.sleep(Config.STICKER_DELETE_DELAY)
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    # Get random wallpaper
    img_url = await get_random_wallpaper()

    # Send welcome as reply to /start
    await message.reply_photo(
        photo=img_url,
        caption=script.START_TXT.format(user.mention, "👋"),
        reply_markup=start_buttons(),
        quote=True
    )


@Client.on_message(filters.command("start") & filters.group)
async def group_start(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.first_name, user.username)
    me = await client.get_me()
    await message.reply_photo(
        photo=Config.WELCOME_IMG,
        caption=script.GSTART_TXT.format(user.mention, "👋"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Start Bot", url=f"https://t.me/{me.username}?start=start")]
        ]),
        quote=True
    )


# ─── Force sub verify ────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^check_sub$"))
async def verify_sub(client: Client, query: CallbackQuery):
    user = query.from_user
    not_joined = await check_force_sub(client, user.id)
    if not_joined:
        await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        return

    await query.message.delete()

    # Sticker then welcome — reply to original message isn't possible after delete,
    # so send directly to user chat
    sticker_msg = await client.send_sticker(user.id, Config.START_STICKER)
    await asyncio.sleep(Config.STICKER_DELETE_DELAY)
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    img_url = await get_random_wallpaper()
    await client.send_photo(
        chat_id=user.id,
        photo=img_url,
        caption=script.START_TXT.format(user.mention, "👋"),
        reply_markup=start_buttons()
    )


# ─── Help / About / Back callbacks ───────────────────────────────────────────

@Client.on_callback_query(filters.regex("^help$"))
async def help_cb(client: Client, query: CallbackQuery):
    await query.message.edit_caption(
        caption=script.HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
        ])
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^about$"))
async def about_cb(client: Client, query: CallbackQuery):
    me = await client.get_me()
    await query.message.edit_caption(
        caption=script.ABOUT_TXT.format(me.username, me.first_name),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
        ])
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^start_back$"))
async def back_to_start(client: Client, query: CallbackQuery):
    user = query.from_user
    img_url = await get_random_wallpaper()
    try:
        await query.message.edit_caption(
            caption=script.START_TXT.format(user.mention, "👋"),
            reply_markup=start_buttons()
        )
    except Exception:
        pass
    await query.answer()
