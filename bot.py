from keep_alive import keep_alive
keep_alive()

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import re
import os
import logging

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

# ── Ignore keywords ─────────────────────────────────────────────
IGNORE_KEYWORDS = [
    'isaac godwin',
    '@isaacgodwiin',
    'one on one training',
    'one on one',
    'contact me',
    'limited slots',
    'account management',
    'earn daily revenue',
    'pocket partner',
    'join one on one',
    'direct access to the signal source',
    'are you ready to trade',
    'contact_me',
    'training',
    'met me',
    'meet me',
]

# ── Should ignore? ──────────────────────────────────────────────
def should_ignore(text):
    if not text:
        return False
    text_lower = text.lower()
    for keyword in IGNORE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False

# ── Is confirmation? ────────────────────────────────────────────
def is_confirmation(text):
    if not text:
        return False
    text_upper = text.upper()
    keywords = [
        'WIN AT DIRECT',
        'WIN AT M1',
        'WIN AT M2', 
        'WIN AT M3',
        'WIN ✅',
        '✅ WIN',
        'DIRECT WIN',
        'WIN IN',
        'WIN AT',
        'LOSS',
        'LOSE',
    ]
    for k in keywords:
        if k.upper() in text_upper:
            return True
    return False

# ── Extract OTC pair ────────────────────────────────────────────
def extract_pair(text):
    if not text:
        return ''
    match = re.search(r'[A-Z]{3}/[A-Z]{3}', text.upper())
    if match:
        return match.group(0)
    return ''

# ── Is trading signal? ──────────────────────────────────────────
def is_signal(text):
    if not text:
        return False
    text_upper = text.upper()
    if re.search(r'[A-Z]{3}/[A-Z]{3}', text_upper):
        return True
    signal_keywords = [
        'BUY', 'SELL', 'PUT', 'CALL',
        'ENTRY', 'EXPIRATION', 'OTC',
        'MARTINGALE', '🟥', '🟩',
    ]
    for k in signal_keywords:
        if k in text_upper:
            return True
    return False

# ── Format messages ─────────────────────────────────────────────
def format_signal(text):
    return (
        f"⚡️ REX SIGNAL ALERTS ⚡️\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 @RexSignalAlerts"
    )

def format_confirmation(text, pair=''):
    pair_line = f"🔰 {pair} OTC\n" if pair else ''
    return (
        f"✅ RESULT UPDATE\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{pair_line}"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 @RexSignalAlerts"
    )

def format_general(text):
    return (
        f"📢 REX SIGNAL ALERTS\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 @RexSignalAlerts"
    )

# ── Keepalive ───────────────────────────────────────────────────
async def keepalive(client):
    while True:
        try:
            await asyncio.sleep(240)
            await client.get_me()
            logger.info("💓 Keepalive ping OK")
        except Exception as e:
            logger.warning(f"⚠️ Keepalive error: {e}")

# ── Main bot logic ──────────────────────────────────────────────
async def run_bot():
    logger.info("🚀 Starting Rex Signal Bot...")

    if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_GROUP, DEST_GROUP, SESSION_STRING]):
        logger.error("❌ Missing environment variables!")
        return False

    userbot = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID,
        API_HASH,
        connection_retries=15,
        retry_delay=5,
        timeout=60,
        device_model="Linux",
        system_version="Ubuntu 20.04",
        app_version="1.0"
    )

    bot = TelegramClient('bot_session', API_ID, API_HASH)

    logger.info("🔌 Connecting userbot...")
    try:
        await asyncio.wait_for(userbot.connect(), timeout=60)
    except asyncio.TimeoutError:
        logger.error("❌ Connection timed out!")
        await userbot.disconnect()
        return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        await userbot.disconnect()
        return False

    if not await userbot.is_user_authorized():
        logger.error("❌ SESSION_STRING expired!")
        await userbot.disconnect()
        return False

    me = await userbot.get_me()
    logger.info(f"✅ Userbot authorized as: {me.first_name} (@{me.username})")

    logger.info("🔌 Starting bot...")
    try:
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("✅ Bot started!")
    except Exception as e:
        logger.error(f"❌ Bot start error: {e}")
        await userbot.disconnect()
        return False

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
        dest_entity = await userbot.get_entity(int(DEST_GROUP))
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

        # Ignore promotional messages
        if should_ignore(text):
            logger.info("🚫 Promotional — ignoring")
            return

        try:
            # Confirmation message
            if is_confirmation(text):
                pair = ''
                if message.reply_to_msg_id:
                    try:
                        replied = await userbot.get_messages(
                            source_entity,
                            ids=message.reply_to_msg_id
                        )
                        if replied:
                            pair = extract_pair(
                                replied.text or replied.caption or ''
                            )
                    except Exception:
                        pass
                formatted = format_confirmation(text, pair)

            # Trading signal
            elif is_signal(text):
                formatted = format_signal(text)

            # General message
            else:
                formatted = format_general(text)

            # Send message
            if message.media:
                await userbot.send_file(
                    dest_entity,
                    file=message.media,
                    caption=formatted
                )
            else:
                await userbot.send_message(
                    dest_entity,
                    formatted
                )

            logger.info("✅ Forwarded successfully!")

        except Exception as e:
            logger.error(f"❌ Forward error: {e}")

    logger.info("🤖 Rex Signal Bot is LIVE! Listening for signals...")
    asyncio.create_task(keepalive(userbot))
    await userbot.run_until_disconnected()
    return True


# ── Auto-restart wrapper ────────────────────────────────────────
async def main():
    while True:
        try:
            await run_bot()
        except Exception as e:
            logger.error(f"💥 Bot crashed: {e}")
        logger.warning("🔄 Restarting in 30 seconds...")
        await asyncio.sleep(30)


if __name__ == '__main__':
    asyncio.run(main())
