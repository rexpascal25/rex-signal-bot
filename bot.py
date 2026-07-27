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

# ── Message tracking (for edit sync) ──────────────────────────
message_map          = {}  # {source_msg_id: dest_msg_id}
signal_direction_map = {}  # {source_msg_id: 'buy' or 'sell'}

# ── Signal keywords ─────────────────────────────────────────────
SIGNAL_KEYWORDS = [
    'BUY', 'SELL', 'PUT', 'CALL', 'SIGNAL', 'ENTRY',
    'EXPIRATION', 'MARTINGALE', 'WIN', 'OTC', 'GBP',
    'USD', 'EUR', 'DIRECT WIN', 'INSTANT EXECUTION',
    'DO BUY', '🟥', '🟩', '⏺', '🕘', '✅', '1️⃣', '2️⃣', '3️⃣',
    'CALL ✅', 'BUY ✅', 'SELL ✅', 'PUT ✅',
    'AT INSTANT EXECUTION', 'WIN ✅',
    'WIN AT', 'WIN IN',
]

PROFIT_KEYWORDS = [
    'screenshot', 'profit', 'screenshots',
    'win at', 'win ✅', '✅ win',
    'instant execution', 'do buy in'
]

# ── Extra messages to forward ───────────────────────────────────
FORWARD_KEYWORDS = [
    'good morning', 'good evening', 'good afternoon',
    'good night', 'i hope you are doing good',
    "we'll trade", 'we will trade', "let's trade",
    'lets trade', 'lost', 'cannot stress',
    'next signals will drop', 'signals will drop',
]

# ── Promotional keywords to REPLACE ────────────────────────────
PROMO_KEYWORDS = [
    'one on one', 'contact me', 'limited slots',
    'account management', 'pocket partner',
    'earn daily revenue', 'join one on one',
    'direct access to the signal source',
    'are you ready to trade', 'contact_me',
    'isaac godwin', '@isaacgodwiin',
    'met me', 'meet me',
]

def is_promo_message(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(k in text_lower for k in PROMO_KEYWORDS)

def extract_signal_time_from_promo(text):
    """
    Extract the real signal time announcement buried
    inside the promotional message and return it cleanly.

    Examples:
    "Next signals will drop by 5pm today" 
        → "📌 Next signals will drop by 5pm today ⏰️"
    "Next signals will drop by 11am tomorrow"
        → "📌 Next signals will drop by 11am tomorrow ⏰️"
    """
    if not text:
        return "📌 Stay tuned for the next signals ⏰️"

    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip()
        line_lower = line_clean.lower()

        # Look for lines containing signal time info
        if 'next signals will drop' in line_lower or            'signals will drop' in line_lower or            'signal will drop' in line_lower:

            # Clean up the line — remove bullet points/icons
            line_clean = re.sub(r'^[📌✔️🎉•\-\s]+', '', line_clean).strip()

            # Add ⏰ if not already there
            if '⏰' not in line_clean:
                line_clean = f"{line_clean} ⏰️"

            # Add 📌 prefix
            return f"📌 {line_clean}"

    # Default if no time found in promo
    return "📌 Stay tuned for the next signals ⏰️"

# ── Signal detection ────────────────────────────────────────────
def is_signal_message(text):
    if not text:
        return False
    text_lower = text.lower()
    text_upper = text.upper()
    # Forward greetings and general messages
    if any(k in text_lower for k in FORWARD_KEYWORDS):
        return True
    if re.search(r'[A-Z]{3}/[A-Z]{3}', text_upper):
        return True
    for keyword in SIGNAL_KEYWORDS:
        if keyword.upper() in text_upper:
            return True
    for keyword in PROFIT_KEYWORDS:
        if keyword.upper() in text_upper:
            return True
    return False

# ── Detect direction (BUY or SELL) ────────────────────────────
def get_direction(text):
    if not text:
        return None
    text_upper = text.upper()
    # Check for BUY/CALL indicators
    if any(k in text_upper for k in ['BUY', 'CALL', '🟩', 'DO BUY']):
        return 'buy'
    # Check for SELL/PUT indicators
    elif any(k in text_upper for k in ['SELL', 'PUT', '🟥', 'DO SELL']):
        return 'sell'
    return None

def direction_emoji(direction):
    if direction == 'buy':
        return '🟢'
    elif direction == 'sell':
        return '🔴'
    return ''

# ── Add emoji to greeting and general lines ───────────────────
def process_greeting(text):
    lines     = text.split('\n')
    new_lines = []
    for line in lines:
        line_lower = line.lower().strip()
        line_upper = line.upper()

        # Good morning/evening → 👋
        if any(g in line_lower for g in [
            'good morning', 'good evening', 'good afternoon',
            'good night', 'hello everyone', 'hi everyone'
        ]):
            if '👋' not in line:
                line = f"{line} 👋"

        # I hope you are doing good → 🎊
        elif 'i hope you are doing good' in line_lower:
            if '🎊' not in line:
                line = f"{line} 🎊"

        # We'll trade / We will trade / Let's trade → ⏰
        elif any(k in line_lower for k in ["we'll trade", 'we will trade', "let's trade", 'lets trade']):
            if '⏰' not in line:
                line = f"{line} ⏰"

        # Lost / cannot stress → ❌
        elif any(k in line_lower for k in ['lost', 'cannot stress']):
            if '❌' not in line:
                line = f"{line} ❌"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Add emoji to signal execution lines ───────────────────────
def process_signal_emojis(text):
    """
    Add correct emoji to lines like:
    - BUY in 1 minute → BUY in 1 minute 🟢
    - SELL in 1 minute → SELL in 1 minute 🔴
    - Do sell in 1 minute → Do sell in 1 minute 🔴
    - Do buy in 1 minute → Do buy in 1 minute 🟢
    - Instant execution in 1 min → depends on signal direction
    """
    overall_direction = get_direction(text)
    lines     = text.split('\n')
    new_lines = []

    for line in lines:
        line_upper = line.upper().strip()

        # Match execution lines
        is_execution_line = bool(re.search(
            r'(DO\s+)?(BUY|SELL|CALL|PUT|INSTANT\s+EXECUTION)'
            r'.*(IN\s*\d+\s*(MIN|MINUTE|MINUTES|SEC|SECOND))',
            line_upper
        ))

        if is_execution_line:
            # Determine emoji for this specific line
            if any(k in line_upper for k in ['BUY', 'CALL', 'DO BUY']):
                emoji = '🟢'
            elif any(k in line_upper for k in ['SELL', 'PUT', 'DO SELL']):
                emoji = '🔴'
            else:
                # Instant execution — use overall signal direction
                emoji = direction_emoji(overall_direction)

            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Add emoji to win/result lines ─────────────────────────────
def process_result_emojis(text, direction):
    """
    Add correct emoji to lines like:
    - WIN at DIRECT in 2 Minutes → WIN at DIRECT in 2 Minutes 🟢
    - WIN at M1 in 2 minutes → WIN at M1 in 2 minutes 🔴
    - WIN ✅ at instant execution → WIN ✅ at instant execution 🟢
    """
    lines     = text.split('\n')
    new_lines = []

    WIN_PATTERNS = [
        'WIN AT DIRECT', 'WIN AT M1', 'WIN AT M2', 'WIN AT M3',
        'WIN AT INSTANT', 'WIN ✅', '✅ WIN', 'DIRECT WIN',
        'WIN IN', 'WIN AT',
        # ── Instant execution variants ──
        'AT INSTANT EXECUTION',
        'INSTANT EXECUTION',
        'WIN ✅ AT INSTANT',
    ]

    for line in lines:
        line_upper = line.upper()
        is_win_line = any(p in line_upper for p in WIN_PATTERNS)

        if is_win_line:
            # Check direction in the line itself first
            line_dir = get_direction(line)
            final_dir = line_dir or direction
            emoji = direction_emoji(final_dir)

            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Process full message text ──────────────────────────────────
def process_text(text, direction=None):
    """Apply all emoji processing to message text"""
    if not text:
        return text

    # Apply greeting emoji
    text = process_greeting(text)

    # Apply signal execution emoji
    text = process_signal_emojis(text)

    # Apply win result emoji (always run to catch all patterns)
    text = process_result_emojis(text, direction)

    return text

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
async def run_bot():
    logger.info("🚀 Starting Rex Signal Bot...")

    if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_GROUP, DEST_GROUP, SESSION_STRING]):
        logger.error("❌ Missing environment variables!")
        return False

    userbot = TelegramClient(
        StringSession(SESSION_STRING),
        API_ID, API_HASH,
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
    logger.info(f"✅ Userbot: {me.first_name} (@{me.username})")

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
        return False

    logger.info("📤 Finding destination group...")
    try:
        dest_entity = await bot.get_entity(int(DEST_GROUP))
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

        # ── Handle promotional messages ─────────────────────────
        if is_promo_message(text):
            try:
                replacement = extract_signal_time_from_promo(text)
                sent = await bot.send_message(dest_entity, replacement)
                message_map[message.id] = sent.id
                logger.info(f"🔄 Promo replaced with: {replacement}")
            except Exception as e:
                logger.error(f"❌ Promo replace error: {e}")
            return

        # ── Always forward media messages with WIN/result captions
        if message.media and text:
            text_upper = text.upper()
            # Force forward if caption contains WIN keywords
            force_forward = any(k in text_upper for k in [
                'WIN ✅', '✅ WIN', 'WIN AT', 'INSTANT EXECUTION',
                'WIN IN', 'DIRECT WIN', 'WIN AT M'
            ])
            if force_forward:
                logger.info("📸 Media with WIN caption — force forwarding!")
                try:
                    direction = get_direction(text)
                    processed_caption = process_text(text, direction)
                    sent = await bot.send_file(
                        dest_entity,
                        file=message.media,
                        caption=processed_caption
                    )
                    message_map[message.id] = sent.id
                    if direction:
                        signal_direction_map[message.id] = direction
                    logger.info(f"✅ Media WIN forwarded: {message.id} → {sent.id}")
                except Exception as e:
                    logger.error(f"❌ Media WIN forward error: {e}")
                return

        if not is_signal_message(text):
            logger.info("⏭️ Not a signal, skipping")
            return

        try:
            # Detect direction
            direction = get_direction(text)

            # Save direction for this message (for later result matching)
            if direction:
                signal_direction_map[message.id] = direction

            # If result message, get direction from original signal
            if message.reply_to_msg_id:
                orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                if orig_dir and not direction:
                    direction = orig_dir

            # Process text with emojis
            processed_text = process_text(text, direction)

            logger.info("🚨 Signal detected! Forwarding...")

            # Send message
            if message.media:
                # For media messages — get caption and process it
                caption     = message.caption or ''
                # Detect direction from caption if not found in text
                cap_dir = direction or get_direction(caption)
                # Process caption with emojis
                processed_caption = process_text(caption, cap_dir) if caption else ''
                sent = await bot.send_file(
                    dest_entity,
                    file=message.media,
                    caption=processed_caption or processed_text
                )
            else:
                sent = await bot.send_message(
                    dest_entity,
                    processed_text
                )

            # Save message ID mapping for edit sync
            message_map[message.id] = sent.id
            logger.info(f"✅ Forwarded: {message.id} → {sent.id}")

        except Exception as e:
            logger.error(f"❌ Forward error: {e}")

    # ── EDIT MESSAGE Handler ───────────────────────────────────
    @userbot.on(events.MessageEdited(chats=source_entity))
    async def edit_handler(event):
        message = event.message
        text    = message.text or message.caption or ''
        logger.info(f"✏️ Message edited in source: {message.id}")

        # Find corresponding dest message
        dest_msg_id = message_map.get(message.id)
        if not dest_msg_id:
            logger.info("⚠️ No mapping found — skipping edit")
            return

        if not is_signal_message(text):
            return

        try:
            # Get direction
            direction = get_direction(text) or \
                        signal_direction_map.get(message.id)

            # Check replied message direction
            if message.reply_to_msg_id:
                orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                if orig_dir and not direction:
                    direction = orig_dir

            # Update direction map
            if direction:
                signal_direction_map[message.id] = direction

            # Process text with emojis
            processed_text = process_text(text, direction)

            # Edit destination message
            await bot.edit_message(
                dest_entity,
                dest_msg_id,
                processed_text
            )
            logger.info(f"✅ Edit synced: {message.id} → {dest_msg_id}")

        except Exception as e:
            logger.error(f"❌ Edit sync error: {e}")

    logger.info("🤖 Rex Signal Bot LIVE!")
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
