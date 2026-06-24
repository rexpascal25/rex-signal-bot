from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import re
import os
import logging
import socks

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Environment variables ───────────────────────────────────────
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH', '')
BOT_TOKEN      = os.environ.get('BOT_TOKEN', '')
SOURCE_GROUP   = os.environ.get('SOURCE_GROUP', '')
DEST_GROUP     = os.environ.get('DEST_GROUP', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

# ── Proxy settings (rotating through multiple proxies) ──────────
PROXIES = [
    (socks.SOCKS5, "159.65.181.194", 9050),
    (socks.SOCKS5, "46.8.31.104", 1080),
    (socks.SOCKS5, "45.144.49.156", 1080),
    (socks.SOCKS5, "77.239.106.24", 1080),
    (socks.SOCKS5, "89.22.226.129", 1080),
]

# ── Signal keywords ─────────────────────────────────────────────
SIGNAL_KEYWORDS = [
    'BUY', 'SELL', 'PUT', 'CALL', 'SIGNAL', 'ENTRY',
    'EXPIRATION', 'MARTINGALE', 'WIN', 'OTC', 'GBP',
    'USD', 'EUR', 'DIRECT WIN', 'INSTANT EXECUTION',
    'DO BUY', '🟥', '🟩', '⏺', '🕘', '✅', '1️⃣', '2️⃣', '3️⃣'
]

PROFIT_KEYWORDS = [
    'screenshot', 'profit', 'screenshots',
    'win at', 'win ✅', '✅ win',
    'instant execution', 'do buy in'
]

# ── Signal detection ────────────────────────────────────────────
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

# ── Keepalive ping every 4 minutes ─────────────────────────────
async def keepalive(client):
    while True:
        try:
            await asyncio.sleep(240)
            await client.get_me()
            logger.info("💓 Keepalive ping OK")
        except Exception as e:
            logger.warning(f"⚠️ Keepalive error: {e}")

# ── Main bot logic ──────────────────────────────────────────────
async def run_bot(proxy):
    logger.info(f"🚀 Starting Rex Signal Bot with proxy {proxy[1]}:{proxy[2]}...")

    # Validate env vars
    if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_GROUP, DEST_GROUP, SESSION_STRING]):
        logger.error("❌ Missing environment variables! Check Railway Variables tab.")
        return False

    userbot = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH,
        proxy=proxy,
        connection_retries=15,
        retry_delay=5,
        timeout=60,
        device_model="Linux",
        system_version="Ubuntu 20.04",
        app_version="1.0"
    )

    bot = TelegramClient(
        'bot_session',
        API_ID,
        API_HASH
    )

    # ── Connect userbot ─────────────────────────────────────────
    logger.info("🔌 Connecting userbot...")
    try:
        await asyncio.wait_for(userbot.connect(), timeout=60)
    except asyncio.TimeoutError:
        logger.error(f"❌ Proxy {proxy[1]} timed out! Trying next proxy...")
        await userbot.disconnect()
        return False
    except Exception as e:
        logger.error(f"❌ Connection error with proxy {proxy[1]}: {e}")
        await userbot.disconnect()
        return False

    if not await userbot.is_user_authorized():
        logger.error("❌ SESSION_STRING is invalid or expired! Generate a new one.")
        await userbot.disconnect()
        return False

    me = await userbot.get_me()
    logger.info(f"✅ Userbot authorized as: {me.first_name} (@{me.username})")

    # ── Start bot ───────────────────────────────────────────────
    logger.info("🔌 Starting bot...")
    try:
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("✅ Bot started!")
    except Exception as e:
        logger.error(f"❌ Bot start error: {e}")
        await userbot.disconnect()
        return False

    # ── Resolve source & destination ────────────────────────────
    logger.info("📥 Finding source group...")
    try:
        source_entity = await userbot.get_entity(SOURCE_GROUP)
        logger.info(f"✅ Source: {source_entity.title}")
    except Exception as e:
        logger.error(f"❌ Source error: {e}")
        await userbot.disconnect()
        await bot.disconnect()
        return False

    logger.info("📤 Finding destination group...")
    try:
        dest_entity = await bot.get_entity(DEST_GROUP)
        logger.info(f"✅ Destination: {dest_entity.title}")
    except Exception as e:
        logger.error(f"❌ Destination error: {e}")
        await userbot.disconnect()
        await bot.disconnect()
        return False

    # ── Message handler ─────────────────────────────────────────
    @userbot.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        message = event.message
        text = message.text or message.caption or ''
        preview = text[:40].replace('\n', ' ')
        logger.info(f"📨 New message: {preview}...")

        if is_signal_message(text):
            logger.info("🚨 Signal detected! Forwarding...")
            try:
                if message.media:
                    await bot.send_file(
                        dest_entity,
                        file=message.media,
                        caption=text
                    )
                else:
                    await bot.send_message(dest_entity, text)
                logger.info("✅ Forwarded successfully!")
            except Exception as e:
                logger.error(f"❌ Forward error: {e}")
        else:
            logger.info("⏭️ Not a signal, skipping")

    # ── Start keepalive & run ───────────────────────────────────
    logger.info("🤖 Rex Signal Bot is LIVE! Listening for signals...")
    asyncio.create_task(keepalive(userbot))
    await userbot.run_until_disconnected()
    return True


# ── Auto-restart with proxy rotation ───────────────────────────
async def main():
    proxy_index = 0
    fail_count = 0

    while True:
        proxy = PROXIES[proxy_index % len(PROXIES)]
        try:
            success = await run_bot(proxy)
            if not success:
                fail_count += 1
                logger.warning(f"⚠️ Proxy {proxy[1]} failed. Trying next one...")
                proxy_index += 1
                if fail_count >= len(PROXIES):
                    logger.error("❌ All proxies failed! Waiting 5 minutes before retry...")
                    fail_count = 0
                    proxy_index = 0
                    await asyncio.sleep(300)
                else:
                    await asyncio.sleep(10)
            else:
                fail_count = 0
                proxy_index = 0
        except Exception as e:
            logger.error(f"💥 Bot crashed: {e}")
            proxy_index += 1
        logger.warning("🔄 Restarting in 30 seconds...")
        await asyncio.sleep(30)


if __name__ == '__main__':
    asyncio.run(main())
