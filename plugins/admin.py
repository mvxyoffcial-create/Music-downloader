import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from config import Config
from script import script
from utils.database import get_user_count, get_today_users, get_all_user_ids


def is_owner(_, __, message: Message):
    return message.from_user and message.from_user.id == Config.OWNER_ID


owner_filter = filters.create(is_owner)


@Client.on_message(filters.command("stats") & owner_filter)
async def stats(client: Client, message: Message):
    total = await get_user_count()
    today = await get_today_users()
    await message.reply(script.STATS_TXT.format(total, today))


@Client.on_message(filters.command("broadcast") & owner_filter)
async def broadcast(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("⚠️ <b>Reply to a message to broadcast it.</b>")
        return

    bcast_msg = message.reply_to_message
    all_ids = await get_all_user_ids()

    status_msg = await message.reply(
        f"📢 <b>Broadcasting to {len(all_ids)} users...</b>"
    )

    success, failed = 0, 0

    for user_id in all_ids:
        try:
            await bcast_msg.copy(user_id)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await bcast_msg.copy(user_id)
                success += 1
            except Exception:
                failed += 1
        except (UserIsBlocked, InputUserDeactivated):
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit(
        script.BROADCAST_TXT.format(success, failed, len(all_ids))
    )
