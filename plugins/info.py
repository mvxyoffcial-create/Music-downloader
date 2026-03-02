from pyrogram import Client, filters
from pyrogram.types import Message
from script import script


@Client.on_message(filters.command("info") & filters.private)
async def user_info(client: Client, message: Message):
    user = message.from_user

    first_name = user.first_name or "None"
    last_name = user.last_name or "None"
    username = f"@{user.username}" if user.username else "None"
    user_id = user.id

    # Get data center via get_chat (workaround)
    dc_id = "N/A"
    try:
        full = await client.get_chat(user.id)
        dc_id = getattr(full, "dc_id", "N/A")
    except Exception:
        pass

    caption = script.INFO_TXT.format(
        first_name,
        last_name,
        user_id,
        dc_id,
        username,
        user_id
    )

    # Try to get profile photo
    photos = await client.get_profile_photos(user.id, limit=1)
    if photos:
        await message.reply_photo(
            photo=photos[0].file_id,
            caption=caption
        )
    else:
        await message.reply(caption)
