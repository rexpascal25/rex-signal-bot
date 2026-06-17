from telethon import TelegramClient, events
import asyncio
import re

API_ID = 38204492
API_HASH = 'a92814edfc66bbc882ef019e2a2b35f3'
BOT_TOKEN = '8938711224:AAGUE7ZZrF8Jkvw6Pu-31gdl03AiFQ--s8o'
SOURCE_GROUP = 'https://t.me/+_iUGF8oXadg4M2I8'
DEST_GROUP = 'https://t.me/+xpJoAOt0B2c4N2I0'

SIGNAL_KEYWORDS = [
    'BUY','SELL','PUT','CALL','SIGNAL','ENTRY',
    'EXPIRATION','MARTINGALE','WIN','OTC','GBP',
    'USD','EUR','DIRECT WIN','INSTANT EXECUTION',
    'DO BUY','🟥','🟩','⏺','🕘','✅','1️⃣','2️⃣','3️⃣'
]

PROFIT_KEYWORDS = [
    'screenshot','profit','screenshots',
    'win at','win ✅','✅ win',
    'instant execution','do buy in'
]

def is_signal_message(text):
    if not text:
        return False
    text_upper = text.upper()
    if re.search(r'[A-Z]{3}/[A-Z]{3}', text_upper):
        return True
    for keyword in SIGNAL_KEYWORDS:
        if keyword.upper() in text_upper:
            return True
    for keyword in PROFIT_KEYWORDS:
        if keyword.upper() in text_upper:
            return True
    return False

userbot = TelegramClient('userbot_session', API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def main():
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Bot is running...")
    source_entity = await userbot.get_entity(SOURCE_GROUP)
    dest_entity = await bot.get_entity(DEST_GROUP)

    @userbot.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        message = event.message
        text = message.text or message.caption or ''
        if is_signal_message(text):
            print(f"🚨 Signal detected: {text[:50]}...")
            try:
                if message.media:
                    await bot.send_file(dest_entity, file=message.media, caption=text)
                else:
                    await bot.send_message(dest_entity, text)
                print("✅ Forwarded!")
            except Exception as e:
                print(f"❌ Error: {e}")

    print("🤖 Rex Signal Bot is LIVE!")
    await userbot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
