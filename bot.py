from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import re
import os

API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
SOURCE_GROUP = os.environ.get('SOURCE_GROUP')
DEST_GROUP = os.environ.get('DEST_GROUP')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

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

async def main():
    print("🚀 Starting Rex Signal Bot...")

    userbot = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH,
        connection_retries=5,
        retry_delay=3,
        timeout=30
    )

    bot = TelegramClient(
        StringSession(),
        API_ID,
        API_HASH
    )

    print("🔌 Connecting userbot...")
    await userbot.connect()

    if not await userbot.is_user_authorized():
        print("❌ Session string invalid or expired!")
        return

    print("✅ Userbot connected and authorized!")

    print("🔌 Starting bot...")
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Bot started!")

    print(f"📥 Finding source group...")
    try:
        source_entity = await userbot.get_entity(SOURCE_GROUP)
        print(f"✅ Source: {source_entity.title}")
    except Exception as e:
        print(f"❌ Source error: {e}")
        return

    print(f"📤 Finding destination group...")
    try:
        dest_entity = await bot.get_entity(DEST_GROUP)
        print(f"✅ Destination: {dest_entity.title}")
    except Exception as e:
        print(f"❌ Destination error: {e}")
        return

    @userbot.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        message = event.message
        text = message.text or message.caption or ''
        print(f"📨 Message: {text[:30]}...")
        if is_signal_message(text):
            print(f"🚨 Signal detected!")
            try:
                if message.media:
                    await bot.send_file(
                        dest_entity,
                        file=message.media,
                        caption=text
                    )
                else:
                    await bot.send_message(dest_entity, text)
                print("✅ Forwarded!")
            except Exception as e:
                print(f"❌ Error: {e}")

    print("🤖 Rex Signal Bot is LIVE!")
    await userbot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
