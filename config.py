import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    MONGO_URI = os.environ.get("MONGO_URI", "")
    OWNER_ID = int(os.environ.get("OWNER_ID", 7408191872))  # @Venuboyy
    OWNER_USERNAME = "Venuboyy"
    DEVELOPER = "@Venuboyy"
    FORCE_SUB_CHANNELS = [
        "zerodev2",       # https://t.me/zerodev2
        "mvxyoffcail",    # https://t.me/mvxyoffcail
    ]
    WORKERS = 500
    WELCOME_IMG = "https://i.ibb.co/pr2H8cwT/img-8312532076.jpg"
    RANDOM_WALLPAPER_API = "https://api.aniwallpaper.workers.dev/random?type=girl"
    START_STICKER = "CAACAgIAAxkBAAEQZtFpgEdROhGouBVFD3e0K-YjmVHwsgACtCMAAphLKUjeub7NKlvk2TgE"
    STICKER_DELETE_DELAY = 2
