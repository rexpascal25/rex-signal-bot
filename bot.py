from keep_alive import keep_alive
keep_alive()

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import re
import os
import logging

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

# ── Message tracking ────────────────────────────────────────────
message_map         = {}  # {source_msg_id: dest_msg_id}
signal_direction_map = {}  # {source_msg_id: 'buy' or 'sell'}

# ── Ignore keywords ─────────────────────────────────────────────
IGNORE_KEYWORDS = [
    'isaac godwin', '@isaacgodwiin', 'one on one training',
    'one on one', 'contact me', 'limited slots',
    'account management', 'earn daily revenue', 'pocket partner',
    'join one on one', 'direct access to the signal source',
    'are you ready to trade', 'contact_me', 'training',
    'met me', 'meet me',
]

def should_ignore(text):
    if not text:
        return False
    text_lower = text.lower()
    for keyword in IGNORE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False

# ── Detect signal direction ────────────────────────────────────
def get_direction(text):
    if not text:
        return None
    text_upper = text.upper()
    if any(k in text_upper for k in ['BUY', 'CALL', '🟩']):
        return 'buy'
    elif any(k in text_upper for k in ['SELL', 'PUT', '🟥']):
        return 'sell'
    return None

def direction_emoji(direction):
    if direction == 'buy':
        return '🟢'
    elif direction == 'sell':
        return '🔴'
    return ''

# ── Extract OTC pair ────────────────────────────────────────────
def extract_pair(text):
    if not text:
        return ''
    match = re.search(r'[A-Z]{3}/[A-Z]{3}', text.upper())
    return match.group(0) if match else ''

# ── Is signal? ──────────────────────────────────────────────────
def is_signal(text):
    if not text:
        return False
    text_upper = text.upper()
    if re.search(r'[A-Z]{3}/[A-Z]{3}', text_upper):
        return True
    for k in ['BUY', 'SELL', 'PUT', 'CALL', 'ENTRY', 'OTC', 'MARTINGALE', '🟥', '🟩']:
        if k in text_upper:
            return True
    return False

# ── Is win/result? ──────────────────────────────────────────────
def is_result(text):
    if not text:
        return False
    text_upper = text.upper()
    result_keywords = [
        'WIN AT DIRECT', 'WIN AT M1', 'WIN AT M2', 'WIN AT M3',
        'WIN ✅', '✅ WIN', 'DIRECT WIN', 'WIN IN', 'WIN AT',
        'LOSS', 'LOSE', 'WIN AT INSTANT', 'INSTANT EXECUTION',
    ]
    for k in result_keywords:
        if k in text_upper:
            return True
    return False

# ── Is greeting? ────────────────────────────────────────────────
def is_greeting(text):
    if not text:
        return False
    greetings = [
        'good morning', 'good evening', 'good afternoon',
        'good night', 'hello everyone', 'hi everyone',
        'good morning everyone'
    ]
    return any(g in text.lower() for g in greetings)

# ══════════════════════════════════════════════════════════════
# ADD EMOJIS TO LINES
# ══════════════════════════════════════════════════════════════

def process_signal_lines(text):
    """
    Add direction emoji to signal execution lines
    BUY in 1 min → BUY in 1 min 🟢
    SELL in 1 min → SELL in 1 min 🔴
    Instant execution in 1 min → depends on direction
    """
    lines     = text.split('\n')
    new_lines = []
    direction = get_direction(text)

    for line in lines:
        line_upper = line.upper()

        # Match execution lines like:
        # "BUY in 1 min", "SELL in 2 min", "Instant execution in 1 min"
        if re.search(
            r'(BUY|SELL|CALL|PUT|INSTANT EXECUTION).*(IN\s*\d+\s*(MIN|MINUTE|SEC|SECOND))',
            line_upper
        ):
            # Determine emoji for this line
            if any(k in line_upper for k in ['BUY', 'CALL']):
                emoji = '🟢'
            elif any(k in line_upper for k in ['SELL', 'PUT']):
                emoji = '🔴'
            elif 'INSTANT' in line_upper:
                emoji = direction_emoji(direction)
            else:
                emoji = direction_emoji(direction)

            # Add emoji if not already there
            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)


def process_result_lines(text, direction):
    """
    Add direction emoji to win/result lines
    WIN at DIRECT in 2 Minutes → WIN at DIRECT in 2 Minutes 🟢 (if buy)
    WIN at M1 in 2 minutes → WIN at M1 in 2 minutes 🔴 (if sell)
    WIN ✅ at instant execution 1 minute sell → ... 🔴
    """
    lines     = text.split('\n')
    new_lines = []

    for line in lines:
        line_upper = line.upper()

        # Check if this line contains a win keyword
        win_patterns = [
            'WIN AT DIRECT', 'WIN AT M1', 'WIN AT M2', 'WIN AT M3',
            'WIN AT INSTANT', 'WIN ✅', '✅ WIN', 'DIRECT WIN',
            'WIN IN', 'WIN AT',
        ]

        is_win_line = any(p in line_upper for p in win_patterns)

        if is_win_line:
            # Detect direction from the line itself first
            line_dir = get_direction(line)
            # Fall back to signal direction
            final_dir = line_dir or direction
            emoji = direction_emoji(final_dir)

            # Add emoji if not already there
            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)


def process_greeting_lines(text):
    """
    Add 👋 to greeting lines if not already there
    Good morning, everyone → Good morning, everyone 👋
    """
    lines     = text.split('\n')
    new_lines = []
    greetings = [
        'good morning', 'good evening', 'good afternoon',
        'good night', 'hello everyone', 'hi everyone'
    ]
    for line in lines:
        line_lower = line.lower()
        if any(g in line_lower for g in greetings):
            if '👋' not in line:
                line = f"{line} 👋"
        new_lines.append(line)
    return '\n'.join(new_lines)


# ── Format messages ─────────────────────────────────────────────
def format_signal(text):
    processed = process_signal_lines(text)
    return (
        f"⚡️ REX SIGNAL ALERTS ⚡️\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{processed}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 @RexSignalAlerts"
    )

def format_result(text, pair='', direction=None):
    pair_line = f"🔰 {pair} OTC\n" if pair else ''
    processed = process_result_lines(text, direction)
    return (
        f"✅ RESULT UPDATE\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{pair_line}"
        f"{processed}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 @RexSignalAlerts"
    )

def format_greeting(text):
    processed = process_greeting_lines(text)
    return (
        f"📢 REX SIGNAL ALERTS\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{processed}\n\n"
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

# ── Format any message (detect type automatically) ─────────────
def format_message(text, pair='', direction=None):
    if is_greeting(text):
        return format_greeting(text)
    elif is_result(text):
        return format_result(text, pair, direction)
    elif is_signal(text):
        return format_signal(text)
    else:
        return format_general(text)

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
        StringSession(SESSION_STRING), API_ID, API_HASH,
        connection_retries=15, retry_delay=5, timeout=60,
        device_model="Linux", system_version="Ubuntu 20.04", app_version="1.0"
    )
    bot = TelegramClient('bot_session', API_ID, API_HASH)

    logger.info("🔌 Connecting userbot...")
    try:
        await asyncio.wait_for(userbot.connect(), timeout=60)
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        await userbot.disconnect()
        return False

    if not await userbot.is_user_authorized():
        logger.error("❌ SESSION_STRING expired!")
        await userbot.disconnect()
        return False

    me = await userbot.get_me()
    logger.info(f"✅ Userbot: {me.first_name} (@{me.username})")

    try:
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("✅ Bot started!")
    except Exception as e:
        logger.error(f"❌ Bot start error: {e}")
        await userbot.disconnect()
        return False

    try:
        source_entity = await userbot.get_entity(SOURCE_GROUP)
        logger.info(f"✅ Source: {source_entity.title}")
    except Exception as e:
        logger.error(f"❌ Source error: {e}")
        return False

    try:
        dest_entity = await userbot.get_entity(int(DEST_GROUP))
        logger.info(f"✅ Destination: {dest_entity.title}")
    except Exception as e:
        logger.error(f"❌ Destination error: {e}")
        return False

    # ── NEW MESSAGE Handler ────────────────────────────────────
    @userbot.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        message = event.message
        text    = message.text or message.caption or ''
        preview = text[:50].replace('\n', ' ')
        logger.info(f"📨 New message: {preview}...")

        if should_ignore(text):
            logger.info("🚫 Ignored")
            return

        try:
            direction = get_direction(text)
            pair      = ''

            # Save direction for this message
            if direction:
                signal_direction_map[message.id] = direction

            # Get pair from replied message if result
            if is_result(text) and message.reply_to_msg_id:
                try:
                    replied = await userbot.get_messages(
                        source_entity, ids=message.reply_to_msg_id
                    )
                    if replied:
                        pair = extract_pair(replied.text or replied.caption or '')
                        # Get direction from original signal
                        orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                        if orig_dir:
                            direction = orig_dir
                except: pass

            formatted = format_message(text, pair, direction)

            # Send and save message ID mapping
            if message.media:
                sent = await userbot.send_file(
                    dest_entity, file=message.media, caption=formatted
                )
            else:
                sent = await userbot.send_message(dest_entity, formatted)

            message_map[message.id] = sent.id
            logger.info(f"✅ Forwarded: {message.id} → {sent.id}")

        except Exception as e:
            logger.error(f"❌ Forward error: {e}")

    # ── EDIT MESSAGE Handler ───────────────────────────────────
    @userbot.on(events.MessageEdited(chats=source_entity))
    async def edit_handler(event):
        message = event.message
        text    = message.text or message.caption or ''
        logger.info(f"✏️ Message edited: {message.id}")

        # Check if we have corresponding dest message
        dest_msg_id = message_map.get(message.id)
        if not dest_msg_id:
            logger.info("⚠️ No mapping found — skipping edit")
            return

        if should_ignore(text):
            return

        try:
            direction = get_direction(text) or signal_direction_map.get(message.id)
            pair      = ''

            if is_result(text) and message.reply_to_msg_id:
                try:
                    replied = await userbot.get_messages(
                        source_entity, ids=message.reply_to_msg_id
                    )
                    if replied:
                        pair = extract_pair(replied.text or replied.caption or '')
                        orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                        if orig_dir:
                            direction = orig_dir
                except: pass

            # Update direction map
            if direction:
                signal_direction_map[message.id] = direction

            formatted = format_message(text, pair, direction)

            # Edit destination message
            await userbot.edit_message(dest_entity, dest_msg_id, formatted)
            logger.info(f"✅ Edit synced: {message.id} → {dest_msg_id}")

        except Exception as e:
            logger.error(f"❌ Edit sync error: {e}")

    logger.info("🤖 Rex Signal Bot LIVE!")
    asyncio.create_task(keepalive(userbot))
    await userbot.run_until_disconnected()
    return True

# ── Auto-restart ────────────────────────────────────────────────
async def main():
    while True:
        try:
            await run_bot()
        except Exception as e:
            logger.error(f"💥 Crash: {e}")
        logger.warning("🔄 Restarting in 30s...")
        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(main())
