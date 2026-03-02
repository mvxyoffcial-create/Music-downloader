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
    """Fetch random wallpaper URL from API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(Config.RANDOM_WALLPAPER_API, allow_redirects=True) as resp:
                return str(resp.url)
    except Exception:
        return Config.WELCOME_IMG


@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.first_name, user.username)

    # Force sub check
    not_joined = await check_force_sub(client, user.id)
    if not_joined:
        await message.reply_photo(
            photo=Config.WELCOME_IMG,
            caption=script.FORCE_SUB_TXT,
            reply_markup=force_sub_markup(not_joined)
        )
        return

    # Send sticker (animated), auto-delete after 2 seconds
    sticker_msg = await message.reply_sticker(Config.START_STICKER)
    await asyncio.sleep(Config.STICKER_DELETE_DELAY)
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    # Get random wallpaper for welcome
    img_url = await get_random_wallpaper()

    first_name = user.mention
    greet = "👋"

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Channel 1", url="https://t.me/zerodev2"),
            InlineKeyboardButton("📢 Channel 2", url="https://t.me/mvxyoffcail"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton("ℹ️ About", callback_data="about"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Venuboyy"),
        ]
    ])

    await message.reply_photo(
        photo=img_url,
        caption=script.START_TXT.format(first_name, greet),
        reply_markup=buttons
    )


@Client.on_message(filters.command("start") & filters.group)
async def group_start(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.first_name, user.username)
    first_name = user.mention
    greet = "👋"
    await message.reply_photo(
        photo=Config.WELCOME_IMG,
        caption=script.GSTART_TXT.format(first_name, greet),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Start Bot", url=f"https://t.me/{(await client.get_me()).username}?start=start")]
        ])
    )


@Client.on_callback_query(filters.regex("^check_sub$"))
async def verify_sub(client: Client, query: CallbackQuery):
    user = query.from_user
    not_joined = await check_force_sub(client, user.id)
    if not_joined:
        await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        return

    await query.message.delete()

    # Send sticker then welcome
    sticker_msg = await query.message.reply_sticker(Config.START_STICKER)
    await asyncio.sleep(Config.STICKER_DELETE_DELAY)
    try:
        await sticker_msg.delete()
    except Exception:
        pass

    img_url = await get_random_wallpaper()
    first_name = user.mention
    greet = "👋"

    buttons = InlineKeyboardMarkup([
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

    await client.send_photo(
        chat_id=user.id,
        photo=img_url,
        caption=script.START_TXT.format(first_name, greet),
        reply_markup=buttons
    )


@Client.on_callback_query(filters.regex("^help$"))
async def help_cb(client: Client, query: CallbackQuery):
    await query.message.edit_caption(
        caption=script.HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ])
    )


@Client.on_callback_query(filters.regex("^about$"))
async def about_cb(client: Client, query: CallbackQuery):
    me = await client.get_me()
    await query.message.edit_caption(
        caption=script.ABOUT_TXT.format(me.username, me.first_name),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ])
    )


@Client.on_callback_query(filters.regex("^start$"))
async def back_to_start(client: Client, query: CallbackQuery):
    user = query.from_user
    img_url = await get_random_wallpaper()
    buttons = InlineKeyboardMarkup([
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
    try:
        await query.message.edit_caption(
            caption=script.START_TXT.format(user.mention, "👋"),
            reply_markup=buttons
        )
    except Exception:
        pass
