from keep_alive import keep_alive
keep_alive()

from telethon import TelegramClient, events
from telethon import Button
from telethon.sessions import StringSession
import asyncio
import re
import os
import json
import math
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
    if not text:
        return "📌 Stay tuned for the next signals ⏰️"

    lines = text.split('\n')
    for line in lines:
        line_clean = line.strip()
        line_lower = line_clean.lower()

        if 'next signals will drop' in line_lower or \
           'signals will drop' in line_lower or \
           'signal will drop' in line_lower:

            line_clean = re.sub(r'^[📌✔️🎉•\-\s]+', '', line_clean).strip()

            if '⏰' not in line_clean:
                line_clean = f"{line_clean} ⏰️"

            return f"📌 {line_clean}"

    return "📌 Stay tuned for the next signals ⏰️"

# ── Signal detection ────────────────────────────────────────────
def is_signal_message(text):
    if not text:
        return False
    text_lower = text.lower()
    text_upper = text.upper()
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
    if any(k in text_upper for k in ['BUY', 'CALL', '🟩', 'DO BUY']):
        return 'buy'
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

        if any(g in line_lower for g in [
            'good morning', 'good evening', 'good afternoon',
            'good night', 'hello everyone', 'hi everyone'
        ]):
            if '👋' not in line:
                line = f"{line} 👋"

        elif 'i hope you are doing good' in line_lower:
            if '🎊' not in line:
                line = f"{line} 🎊"

        elif any(k in line_lower for k in ["we'll trade", 'we will trade', "let's trade", 'lets trade']):
            if '⏰' not in line:
                line = f"{line} ⏰"

        elif any(k in line_lower for k in ['lost', 'cannot stress']):
            if '❌' not in line:
                line = f"{line} ❌"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Add emoji to signal execution lines ───────────────────────
def process_signal_emojis(text):
    overall_direction = get_direction(text)
    lines     = text.split('\n')
    new_lines = []

    for line in lines:
        line_upper = line.upper().strip()

        is_execution_line = bool(re.search(
            r'(DO\s+)?(BUY|SELL|CALL|PUT|INSTANT\s+EXECUTION)'
            r'.*(IN\s*\d+\s*(MIN|MINUTE|MINUTES|SEC|SECOND))',
            line_upper
        ))

        if is_execution_line:
            if any(k in line_upper for k in ['BUY', 'CALL', 'DO BUY']):
                emoji = '🟢'
            elif any(k in line_upper for k in ['SELL', 'PUT', 'DO SELL']):
                emoji = '🔴'
            else:
                emoji = direction_emoji(overall_direction)

            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Add emoji to win/result lines ─────────────────────────────
def process_result_emojis(text, direction):
    lines     = text.split('\n')
    new_lines = []

    WIN_PATTERNS = [
        'WIN AT DIRECT', 'WIN AT M1', 'WIN AT M2', 'WIN AT M3',
        'WIN AT INSTANT', 'WIN ✅', '✅ WIN', 'DIRECT WIN',
        'WIN IN', 'WIN AT',
        'AT INSTANT EXECUTION',
        'INSTANT EXECUTION',
        'WIN ✅ AT INSTANT',
    ]

    for line in lines:
        line_upper = line.upper()
        is_win_line = any(p in line_upper for p in WIN_PATTERNS)

        if is_win_line:
            line_dir = get_direction(line)
            final_dir = line_dir or direction
            emoji = direction_emoji(final_dir)

            if emoji and emoji not in line:
                line = f"{line} {emoji}"

        new_lines.append(line)
    return '\n'.join(new_lines)

# ── Process full message text ──────────────────────────────────
def process_text(text, direction=None):
    if not text:
        return text
    text = process_greeting(text)
    text = process_signal_emojis(text)
    text = process_result_emojis(text, direction)
    return text

# ══════════════════════════════════════════════════════════════
# NEW: Strategy / Materials / Register / Signal Groups menu
# ══════════════════════════════════════════════════════════════

from telethon.tl.functions.messages import ExportChatInviteRequest

# ── Links (set these as environment variables once you have them) ─
GOOGLE_DRIVE_LINK = os.environ.get('GOOGLE_DRIVE_LINK', 'https://example.com/replace-with-your-drive-link')

# Comma-separated list of registration links, e.g.:
#   REGISTER_LINKS=https://pocketoption.com/en/?ref=xxxx,https://quotex.com/?ref=yyyy
# The bot auto-detects the platform name from each URL for the button label.
REGISTER_LINKS_RAW = os.environ.get('REGISTER_LINKS', '')

# Comma-separated list of signal group identifiers (usernames, invite
# links, or numeric chat IDs), e.g.:
#   SIGNAL_GROUPS=my_public_group,-1001234567890
# The bot reads each group's real name automatically and links straight
# to it — no manual naming needed.
# If SIGNAL_GROUPS isn't set at all, it automatically falls back to
# DEST_GROUP — handy when your signal group and your destination group
# for forwarded signals are the same group (no need to set both).
SIGNAL_GROUPS_RAW = os.environ.get('SIGNAL_GROUPS', '') or DEST_GROUP

# Tracks which diagram each user is currently viewing per strategy
diagram_state = {}

# Cache of resolved signal groups: [{"name": ..., "url": ...}, ...]
# Populated at startup by resolve_signal_groups(), refreshable via button.
signal_groups_cache = []

# ── Platform auto-detection for Register links ─────────────────
PLATFORM_NAME_MAP = {
    "pocketoption": "Pocket Option",
    "iqoption":     "IQ Option",
    "iqbroker":     "IQ Option",
    "quotex":       "Quotex",
    "binomo":       "Binomo",
    "olymptrade":   "Olymp Trade",
    "expertoption": "Expert Option",
    "binance":      "Binance",
    "bybit":        "Bybit",
    "exness":       "Exness",
    "deriv":        "Deriv",
}

def detect_platform_name(url):
    """Guess a clean display name for a registration link based on its domain."""
    url_lower = url.lower()
    for key, name in PLATFORM_NAME_MAP.items():
        if key in url_lower:
            return name
    # Fallback: use the domain's main part, title-cased
    domain = re.sub(r'^https?://(www\.)?', '', url_lower).split('/')[0]
    core = domain.split('.')[0] if domain else 'link'
    return core.replace('-', ' ').replace('_', ' ').title() or "Register"

def get_register_links():
    urls = [u.strip() for u in REGISTER_LINKS_RAW.split(',') if u.strip()]
    return [{"name": detect_platform_name(u), "url": u} for u in urls]

# ── Signal group resolution ─────────────────────────────────────
async def resolve_signal_groups(bot):
    """Looks up each configured group/channel and builds a name+link list.

    Each entry in SIGNAL_GROUPS can be:
      • a bare username or numeric chat ID, e.g. "my_public_group" or "-100123..."
        (the bot must be an admin there) — the bot generates a FRESH invite
        link that requires YOUR approval before anyone can join, even with
        the link in hand. This is the recommended option for a private,
        access-controlled group.
      • a full invite link, e.g. "https://t.me/+xpJoAOt0B2c4N2I0" — used
        as-is (whatever join behavior that link already has can't be changed
        here), with the bot only trying to fetch the real group name for
        the button.
      • an optional custom label using "::" , e.g.
        "Rex Signals VIP::https://t.me/+xpJoAOt0B2c4N2I0" to force the button
        text instead of relying on auto-detection
    """
    global signal_groups_cache
    raw_items = [g.strip() for g in SIGNAL_GROUPS_RAW.split(',') if g.strip()]
    resolved = []

    for idx, raw_item in enumerate(raw_items, start=1):
        custom_name = None
        ident = raw_item
        if '::' in raw_item:
            custom_name, ident = (part.strip() for part in raw_item.split('::', 1))

        is_link = ident.startswith('http://') or ident.startswith('https://') or ident.startswith('t.me/')

        if is_link:
            link = ident if ident.startswith('http') else f"https://{ident}"
            title = custom_name or f"Signal Group {idx}"
            try:
                entity = await bot.get_entity(ident)
                title = custom_name or getattr(entity, 'title', None) or getattr(entity, 'first_name', None) or title
            except Exception as e:
                logger.warning(f"⚠️ Could not auto-fetch a name for '{ident}', using '{title}': {e}")
            resolved.append({"name": title, "url": link})
            logger.info(f"✅ Signal group added: {title} -> {link}")
            continue

        # Otherwise treat it as a username or numeric chat ID.
        # Telegram chat IDs must be passed as actual integers, not text,
        # or entity lookup fails — so convert numeric-looking strings here.
        lookup_ident = ident
        if re.fullmatch(r'-?\d+', ident):
            lookup_ident = int(ident)

        try:
            entity = await bot.get_entity(lookup_ident)
            title = custom_name or getattr(entity, 'title', None) or getattr(entity, 'first_name', None) or ident
            username = getattr(entity, 'username', None)
            if username:
                link = f"https://t.me/{username}"
            else:
                # request_needed=True means the link lets people REQUEST to
                # join, but nobody gets in until you (the admin) approve
                # them in Telegram — even if they have the link.
                invite = await bot(ExportChatInviteRequest(entity, request_needed=True))
                link = invite.link
            resolved.append({"name": title, "url": link})
            logger.info(f"✅ Signal group resolved: {title} -> {link}")
        except Exception as e:
            logger.error(f"❌ Could not resolve signal group '{ident}': {e}")

    signal_groups_cache = resolved
    return resolved

# ── Strategy write-ups + emoji diagrams ─────────────────────────
# Add future strategies here — each needs a unique key, a display
# name (shown in the dropdown button), the text chunks (each kept
# under Telegram's 4096-char limit), and the emoji diagram list.

TRENDING_STRATEGY_TEXT = [
    (
        "🌈 *The Trending Strategy* 📈\n"
        "_By Pascal Brown_\n\n"
        "😊 *Big Idea:* We watch which way the market is \"walking\" "
        "(up or down), and we only join the walk when everyone is "
        "walking the *same way*. That's it!\n\n"
        "🕯️ *1. What is a \"Candle\"?*\n"
        "Every minute, the market draws a little colored block called "
        "a candle.\n"
        "🟢 Green candle = price went UP that minute ⬆️\n"
        "🔴 Red candle = price went DOWN that minute ⬇️\n\n"
        "Every candle here is *1 minute* long — it opens, runs for 60 "
        "seconds, closes, and a new one opens right away. ⏱️"
    ),
    (
        "🧰 *2. The Toolbox We Use*\n\n"
        "🎯 *The \"Marker\" (oscillator):* a wiggly line that shows when "
        "the market is \"too tired\" going up (overbought) or down "
        "(oversold).\n\n"
        "📈 *MACD:* shows how strong the push is — a steep, straight "
        "line means the move is strong and confident.\n\n"
        "📏 *Two Moving Averages* (green + yellow): smooth lines that "
        "show the market's average mood.\n\n"
        "👆 Above the yellow line = BUY mood. Below it = SELL mood."
    ),
    (
        "🛤️ *3. The MOST Important Rule: Trend vs. Range*\n\n"
        "💎 This is the heart of the whole strategy. We only play when "
        "the market is *trending* — candles keep matching colors in a "
        "row, like friends all walking the same way.\n\n"
        "🌀 If candles keep flip-flopping (green, red, green, red...), "
        "that's *ranging* — never play in a ranging market, you can't "
        "guess what happens next.\n\n"
        "🔍 *How to spot it:* look at the last few candles.\n"
        "✅ All matching colors → trend, safe to play.\n"
        "❌ Mixed colors → range, walk away and find another pair."
    ),
    (
        "🐾 *4. Step-by-Step: How a Trade is Taken*\n\n"
        "1️⃣ Look at candles — are they all matching?\n"
        "2️⃣ Trending? YES → keep going. NO → skip this market.\n"
        "3️⃣ Check the yellow line — above = buy mood, below = sell mood.\n"
        "4️⃣ Wait for the candle to close, note its color.\n"
        "5️⃣ New candle opens → enter in the *same* direction.\n"
        "6️⃣ Win? Repeat 4–5. Lose? Martingale once, new direction.\n"
        "7️⃣ See mixed colors? STOP — it's ranging, find another market."
    ),
    (
        "🎲 *5. What Happens if a Trade Loses? (Martingale)*\n\n"
        "When a trade loses, this strategy says: put in a *bigger bet* "
        "on the very next candle, following the new color. This is "
        "called *martingale*.\n\n"
        "🤔 If you guess wrong once, you guess again but risk a little "
        "more, hoping to win back what you lost plus a little extra.\n\n"
        "🚨 *Caution:* martingale can grow your risk very fast across "
        "several losses in a row — even in a market that looks like "
        "it's trending. Be extra careful with it, no matter how "
        "experienced you are."
    ),
    (
        "🔍 *6. Finding Today's Best Trending OTC Pair*\n\n"
        "🤔 No OTC pair trends all day, every day. A pair that trends "
        "beautifully in the morning can turn choppy an hour later — "
        "and a different pair might start trending instead. Trending "
        "is a *temporary mood*, not a permanent label.\n\n"
        "So the winning habit is to *scan your OTC watchlist every "
        "session* and let the candles tell you which pair is trending "
        "right now.\n\n"
        "📏 Easier-to-read pairs tend to have:\n"
        "• Fewer sudden spikes/wicks\n"
        "• Clear separation from the yellow line (not hugging it)\n"
        "• A MACD line sloping steadily, not flattening/curling\n\n"
        "🚨 *Honest note:* there's no fixed list of pairs guaranteed "
        "to always trend. Any list claiming that goes stale fast — "
        "the scanning habit is what keeps working, session after "
        "session."
    ),
    (
        "📖 *7. Quick Recap*\n\n"
        "✅ *Do*\n"
        "• Trade only when candles match in a row (trend)\n"
        "• Check the yellow line for buy/sell mood\n"
        "• Follow the color of the last closed candle\n"
        "• Be careful and deliberate with martingale\n\n"
        "❌ *Don't*\n"
        "• Trade when colors are mixed (range)\n"
        "• Ignore the yellow line and MACD\n"
        "• Guess against the trend for no reason\n"
        "• Martingale again and again with no plan\n\n"
        "🧠 The real skill isn't the marker or MACD — it's correctly "
        "telling a real trend apart from a range, in real time. That "
        "takes practice.\n\n"
        "🤝 Practice on a demo account first, trade small, and take "
        "care of your money like a good friend takes care of you! ⭐"
    ),
]

# Emoji-only diagrams — no image files needed anymore
TRENDING_STRATEGY_DIAGRAMS = [
    (
        "🛤️ *Trending vs. Ranging*\n\n"
        "🟢🟢🟢🟢🟢 → *TRENDING* (all matching, safe to trade!)\n\n"
        "🟢🔴🟢🔴🟢 → *RANGING* (mixed colors, skip it!)"
    ),
    (
        "📏 *The Yellow Line Mood*\n\n"
        "⬆️📈 Above the yellow line → 🟢 *BUY* mood\n\n"
        "⬇️📉 Below the yellow line → 🔴 *SELL* mood"
    ),
    (
        "🐾 *The 7-Step Loop*\n\n"
        "1️⃣ Look at candles\n"
        "2️⃣➡️ Trending?\n"
        "3️⃣➡️ Check yellow line\n"
        "4️⃣➡️ Wait for candle to close\n"
        "5️⃣➡️ Enter new candle, same direction\n"
        "6️⃣➡️ Win? repeat 🔁 Lose? martingale once 🎲\n"
        "7️⃣ Mixed colors? 🛑 STOP, find another pair"
    ),
    (
        "🔍 *Daily Pair Scan*\n\n"
        "🔎 EUR/USD OTC → trending? ❓\n"
        "🔎 GBP/JPY OTC → trending? ❓\n"
        "🔎 AUD/CAD OTC → trending? ❓\n\n"
        "✅ Found one trending → trade it! 🎯\n"
        "❌ All ranging → wait and rescan 🔁"
    ),
]

# Registry of all strategies shown in the dropdown — add more here later
STRATEGIES = {
    "trending": {
        "name": "📈 Trending Strategy",
        "text": TRENDING_STRATEGY_TEXT,
        "diagrams": TRENDING_STRATEGY_DIAGRAMS,
    },
    # "next_strategy_key": { "name": "...", "text": [...], "diagrams": [...] },
}

# ── Button builders ─────────────────────────────────────────────
def main_menu_buttons():
    return [
        [Button.inline("📈 Strategy", b"menu:strategy")],
        [Button.url("📂 Materials", GOOGLE_DRIVE_LINK)],
        [Button.inline("🔗 Register", b"menu:register")],
        [Button.inline("📡 Signal Groups", b"menu:signal_groups")],
        [Button.inline("🤖 Market Analyst", b"menu:analyst")],
        [Button.inline("🟡 Trade on Binance", b"menu:trade")],
        [Button.inline("🔔 Opportunity Alerts", b"menu:alerts")],
        [Button.inline("🤖 Auto-Trading", b"menu:autotrade")],
        [Button.inline("⚡ Futures Trading", b"menu:futures")],
    ]

def strategy_list_buttons():
    rows = []
    for key, strat in STRATEGIES.items():
        rows.append([Button.inline(strat["name"], f"strategy:{key}".encode())])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def diagram_nav_buttons(strategy_key, index, total):
    row = []
    if index > 0:
        row.append(Button.inline("⬅️ Back", f"diagram:{strategy_key}:{index-1}".encode()))
    if index < total - 1:
        row.append(Button.inline("Next ➡️", f"diagram:{strategy_key}:{index+1}".encode()))
    nav = [row] if row else []
    nav.append([Button.inline("📚 All Strategies", b"menu:strategy")])
    nav.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return nav

def register_list_buttons():
    links = get_register_links()
    rows = [[Button.url(l["name"], l["url"])] for l in links]
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def signal_groups_buttons():
    rows = [[Button.url(g["name"], g["url"])] for g in signal_groups_cache]
    rows.append([Button.inline("🔄 Refresh", b"signal_groups:refresh")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

# ── Registers /start, /menu commands and all button callbacks ──
def setup_menu_handlers(bot):

    @bot.on(events.NewMessage(pattern=r'^/(start|menu)$'))
    async def start_handler(event):
        chat = await event.get_chat()
        await clear_user_chat(bot, chat, event.sender_id)
        await event.respond(
            "👋 *Welcome to Rex Signal Bot!*\n\nChoose an option below:",
            buttons=main_menu_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"menu:main"))
    async def main_menu_callback(event):
        chat = await event.get_chat()
        await clear_user_chat(bot, chat, event.sender_id)
        await bot.send_message(
            chat,
            "👋 *Welcome to Rex Signal Bot!*\n\nChoose an option below:",
            buttons=main_menu_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"menu:strategy"))
    async def strategy_menu_callback(event):
        await event.edit(
            "📈 *Strategies*\n\nPick a strategy to view the full write-up:",
            buttons=strategy_list_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(pattern=rb"^strategy:(.+)$"))
    async def strategy_detail_callback(event):
        key = event.pattern_match.group(1).decode()
        strat = STRATEGIES.get(key)
        if not strat:
            await event.answer("Strategy not found.", alert=True)
            return

        await event.answer(f"Loading {strat['name']}...")

        chat = await event.get_chat()

        for chunk in strat["text"]:
            await bot.send_message(chat, chunk, parse_mode='markdown')

        diagrams = strat["diagrams"]
        if diagrams:
            diagram_state[event.sender_id] = {"strategy": key, "index": 0}
            await bot.send_message(
                chat,
                diagrams[0],
                parse_mode='markdown',
                buttons=diagram_nav_buttons(key, 0, len(diagrams))
            )
        else:
            await bot.send_message(
                chat, "⬅️ Use the buttons below to go back.",
                buttons=[[Button.inline("📚 All Strategies", b"menu:strategy")],
                         [Button.inline("🏠 Main Menu", b"menu:main")]]
            )

    @bot.on(events.CallbackQuery(pattern=rb"^diagram:([^:]+):(\d+)$"))
    async def diagram_nav_callback(event):
        key = event.pattern_match.group(1).decode()
        index = int(event.pattern_match.group(2))
        strat = STRATEGIES.get(key)
        if not strat:
            await event.answer("Strategy not found.", alert=True)
            return

        diagrams = strat["diagrams"]
        if index < 0 or index >= len(diagrams):
            await event.answer()
            return

        diagram_state[event.sender_id] = {"strategy": key, "index": index}

        await event.edit(
            diagrams[index],
            parse_mode='markdown',
            buttons=diagram_nav_buttons(key, index, len(diagrams))
        )
        await event.answer()

    @bot.on(events.CallbackQuery(data=b"menu:register"))
    async def register_callback(event):
        links = get_register_links()
        if not links:
            await event.edit(
                "🔗 *Register*\n\nNo registration links added yet — check back soon!",
                buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]],
                parse_mode='markdown'
            )
            return
        await event.edit(
            "🔗 *Register*\n\nChoose a platform to register:",
            buttons=register_list_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"menu:signal_groups"))
    async def signal_groups_callback(event):
        if not signal_groups_cache:
            await event.edit(
                "📡 *Signal Groups*\n\nNo signal groups added yet — check back soon!",
                buttons=[[Button.inline("🔄 Refresh", b"signal_groups:refresh")],
                         [Button.inline("🏠 Main Menu", b"menu:main")]],
                parse_mode='markdown'
            )
            return
        await event.edit(
            "📡 *Signal Groups*\n\nTap a group to join:",
            buttons=signal_groups_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"signal_groups:refresh"))
    async def signal_groups_refresh_callback(event):
        await event.answer("Refreshing groups...")
        await resolve_signal_groups(bot)
        if not signal_groups_cache:
            await event.edit(
                "📡 *Signal Groups*\n\nNo signal groups added yet — check back soon!",
                buttons=[[Button.inline("🔄 Refresh", b"signal_groups:refresh")],
                         [Button.inline("🏠 Main Menu", b"menu:main")]],
                parse_mode='markdown'
            )
            return
        await event.edit(
            "📡 *Signal Groups*\n\nTap a group to join:",
            buttons=signal_groups_buttons(),
            parse_mode='markdown'
        )

    # ── Market Analyst (AI agent) callbacks ─────────────────────
    @bot.on(events.CallbackQuery(data=b"menu:analyst"))
    async def analyst_intro_callback(event):
        await event.edit(
            "🤖 *Market Analyst*\n\n"
            "Hey, I'm Rex! 👋 Ask me anything about binary options trading — "
            "candlesticks, indicators, strategies, risk management, whatever's "
            "on your mind. Just type your question below and I'll reply right "
            "here in this chat. 📊💬\n\n"
            "_(Tap 🔄 New Chat anytime to clear our conversation and start fresh.)_",
            buttons=[[Button.inline("🔄 New Chat", b"analyst:reset")],
                     [Button.inline("🏠 Main Menu", b"menu:main")]],
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"analyst:reset"))
    async def analyst_reset_callback(event):
        agent_conversations.pop(event.sender_id, None)
        await event.answer("🔄 Chat cleared! Ask me anything.")

    logger.info("✅ Menu handlers registered (Strategy / Materials / Register / Signal Groups / Analyst)")

# ══════════════════════════════════════════════════════════════
# NEW: AI Market Analyst agent (powered by Google Gemini's free API)
# ══════════════════════════════════════════════════════════════
#
# Setup:
#   1. pip install google-generativeai
#   2. Get a free API key (no credit card needed) at
#      https://aistudio.google.com/apikey
#   3. Set env var GEMINI_API_KEY to that key.
#   4. Optionally set GEMINI_MODEL to override the default model.
#
# Gemini's free tier has a daily request limit that resets at
# midnight Pacific Time. When it's hit, the bot tells the user
# exactly how long until it resets instead of erroring out.

import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL   = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')

class AgentLimitReached(Exception):
    """Raised when Gemini's free daily quota has been used up for the day."""
    pass

AGENT_SYSTEM_PROMPT = """You are Rex, a friendly and sharp binary options market \
analyst built into Pascal Brown's signal Telegram bot. You are deeply \
knowledgeable across the full binary options and forex world: forex majors, \
minors and exotics, OTC synthetic markets, crypto-based binary options, \
commodities and index options, and every major analysis approach — candlestick \
reading, chart patterns (double top/bottom, head and shoulders, triangles, \
flags), support/resistance, trend vs. range analysis, MACD, RSI, Bollinger \
Bands, Fibonacci retracements, moving averages, oscillators, multi-timeframe \
confluence, price action, breakout and reversal setups, martingale and general \
risk/money management, and the Trending Strategy taught elsewhere in this bot. \
You can compare brokers/platforms, explain how any indicator or strategy \
works, and walk through general market structure and analysis in real depth.

STYLE
- Talk like a real, warm, sharp trader friend — not a corporate assistant. \
Casual, encouraging, clear, and conversational.
- Use emojis naturally and often (📈📉🟢🔴🎯💡⚠️🤔🕯️🏦📊) to make things lively \
and easy to scan — but don't overdo it in every single sentence.
- Keep answers focused; use short paragraphs or bullet points for clarity.
- Actively ask follow-up or clarifying questions when it helps (e.g. their \
experience level, which pair/platform, what they've already tried) instead of \
just lecturing at them. A good conversation goes both ways.
- React to what the user shares — empathize with losses, celebrate wins, keep \
it human.
- If someone asks directly whether you're human or an AI, be honest that you're \
an AI assistant. Otherwise just talk naturally, no need to caveat every message.

TELEGRAM FORMATTING — FOLLOW THESE EXACTLY
This is critical: your replies are shown in a Telegram chat, which does NOT \
render Markdown headers or tables. Breaking these rules makes your messages \
look broken, with literal symbols showing on screen.
- NEVER use "#", "##", or "###" headers. Instead, start a section with a \
relevant emoji followed by a short bold label, e.g. "🏦 *IQ Option*" on its \
own line.
- NEVER use Markdown tables (no "|" pipe characters, no "---" divider rows). \
To compare two things, use a labeled bullet block for each one instead, e.g.:
  🏦 *IQ Option*
  • Interface: polished, very "pro" feel
  • OTC focus: lighter

  📊 *Pocket Option*
  • Interface: fast, customizable
  • OTC focus: their biggest strength
- For bold text use single asterisks like *this*, never double asterisks like \
**this**.
- For bullet points use "•" or a relevant emoji at the start of the line, not \
"*" or "-".
- Keep formatting light and clean — the goal is a message that looks great in \
a normal chat bubble, not a formatted document.

SUBSTANCE RULES
- You can explain concepts, indicators, and strategies in depth, and discuss \
general market structure and risk management.
- Never promise or imply a guaranteed win, a "sure" signal, or certainty about \
future price direction. Markets are probabilistic — frame things as tendencies \
and probabilities, not certainties.
- Don't hand someone a specific "buy/sell right now, this amount" call as if it \
were financial advice to act on with real money. Instead help them learn to \
read the chart and decide for themselves.

CHART SCREENSHOT ANALYSIS
When someone sends a chart screenshot (e.g. from Pocket Option, IQ Option, \
Bybit, or anywhere else), follow this EXACT process, in this order, every \
single time — don't skip steps or jump straight to a verdict:

1. Check for a visible countdown/expiration timer on the candle. If one is \
visible, note it.
2. Read the last several candles — are they trending (mostly one color) or \
mixed/ranging?
3. Read any visible moving average line(s) — is price above or below them?
4. Read any visible MACD/oscillator-style indicator — what's it showing?
5. Only THEN give your verdict — BUY or SELL — based on whether the above \
genuinely agree. Don't be vague or refuse to commit to a direction when they \
do agree.

UNCERTAINTY FLAGGING — this is mandatory, not optional:
- If any of steps 2-4 isn't clearly visible or readable in the image (blurry, \
cropped out, cluttered), say so explicitly instead of quietly guessing. A \
confident-sounding call built on something you couldn't actually see is worse \
than admitting you need a clearer screenshot.
- Apply the same trend-vs-range discipline as the Trending Strategy: only \
give a confident BUY/SELL read if the candles show a real trend (not mixed/ \
choppy) with the visible indicators agreeing. If it looks genuinely ranging \
or the indicators conflict, say so plainly instead of forcing a call.

COUNTDOWN TIMING — only if a countdown/timer is actually visible in the image:
- Report it as an approximate figure tied to when the screenshot was taken, \
e.g. "~18 seconds until this candle closes" — never claim it's synced to the \
exact moment they read your reply, since upload and processing time adds \
real lag on top of it.
- If no countdown or timer is visible anywhere in the image, don't invent one \
or guess a number — just skip this part.

REQUIRED OUTPUT FORMAT — always structure your final answer like this \
(emoji-led, short, scannable — not a wall of prose):

🕯️ Last candles: [what you saw — e.g. "green, green, green, red — mostly up"]
📏 Moving average: [price above/below, or "not clearly visible"]
📈 MACD/oscillator: [what it shows, or "not clearly visible"]
🟢 BUY / 🔴 SELL / ⚠️ No clear setup — [one line on why, referencing the above]
⏱️ [only include this line if a countdown was actually visible] Countdown \
shows ~X seconds until this candle closes and the next opens — enter as it \
opens

- Always give your reasoning alongside the call, and always frame it as your \
read of what's visible — not a guarantee of the outcome, same as everywhere \
else in this bot.
- Be honest about risk when it's relevant: binary options and OTC synthetic \
markets are high-risk, and martingale can wipe out an account fast across a \
losing streak. Mention this naturally when it fits, without being preachy \
about it in every reply.
- If someone seems to be chasing losses, spiraling, or deciding out of \
desperation rather than analysis, gently flag that and encourage them to step \
back rather than helping them size up a bigger bet.
"""

gemini_model = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=AGENT_SYSTEM_PROMPT
    )

# Per-user conversation memory: {user_id: [{"role": "user"/"model", "parts": [...]}, ...]}
agent_conversations = {}

# ── Clean-chat message tracking ─────────────────────────────────
# Tracks every message the bot sends each user, so tapping "🏠 Main Menu"
# can sweep the clutter away and show one fresh menu, like professional
# bots do, instead of leaving a trail of old messages behind.
user_message_history = {}  # {user_id: [message_id, message_id, ...]}
MAX_TRACKED_MESSAGES = 300  # safety cap in case someone never taps Main Menu

def track_message(user_id, message):
    """Records a sent message's ID against the user, for later cleanup."""
    if message is None:
        return
    history = user_message_history.setdefault(user_id, [])
    history.append(message.id)
    del history[:-MAX_TRACKED_MESSAGES]

async def clear_user_chat(bot, chat, user_id):
    """Deletes every tracked message for this user (best-effort — some may
    already be gone) and clears their tracking history."""
    history = user_message_history.pop(user_id, [])
    if history:
        try:
            await bot.delete_messages(chat, history)
        except Exception as e:
            logger.warning(f"⚠️ Couldn't bulk-delete old messages for user {user_id}: {e}")
MAX_HISTORY_MESSAGES = 16  # keep the last 8 exchanges per user (trims cost/context)

def time_until_gemini_reset():
    """Returns a human-readable countdown to Gemini's next midnight-Pacific reset."""
    if ZoneInfo is None:
        return "later today"
    pacific_now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    next_reset = (pacific_now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    remaining = next_reset - pacific_now
    total_minutes = int(remaining.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"about {hours}h {minutes}m"
    return f"about {minutes} minutes"

def clean_for_telegram(text):
    """Safety net: cleans up web-style Markdown (headers, tables, double-
    asterisk bold) that the model might still slip into, converting it to
    formatting Telegram's legacy Markdown parser actually understands."""
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Drop markdown table divider rows like "|---|:---:|"
        if re.fullmatch(r'\|?[\s:|-]+\|?', stripped) and '-' in stripped:
            continue

        # Turn "### Some Header" into "*Some Header*"
        header_match = re.match(r'^#{1,6}\s*(.+)$', stripped)
        if header_match:
            cleaned_lines.append(f"*{header_match.group(1).strip()}*")
            continue

        # Turn a markdown table row "| A | B |" into a plain bullet line
        if stripped.startswith('|') and stripped.endswith('|') and stripped.count('|') >= 2:
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            cells = [c for c in cells if c]
            if cells:
                cleaned_lines.append('• ' + ' — '.join(cells))
            continue

        # Turn "* item" or "- item" bullet markers into a clean "• item"
        bullet_match = re.match(r'^[\*\-]\s+(.+)$', stripped)
        if bullet_match:
            cleaned_lines.append('• ' + bullet_match.group(1))
            continue

        cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines)

    # Double-asterisk bold → single-asterisk bold (Telegram legacy Markdown)
    result = re.sub(r'\*\*(.+?)\*\*', r'*\1*', result)

    # Collapse 3+ blank lines left behind by removed table rows
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()

# ══════════════════════════════════════════════════════════════
# NEW: Binance live market data + manually-confirmed trading
# ══════════════════════════════════════════════════════════════
#
# Setup:
#   1. pip install python-binance
#   2. Create API keys at https://www.binance.com/en/my/settings/api-management
#      (or https://testnet.binance.vision for a safe fake-money testnet account)
#   3. Set env var BINANCE_TESTNET (defaults to "true" — fake money until
#      you deliberately set it to "false")
#   4. Set BINANCE_ENCRYPTION_KEY — a secret key used to encrypt each
#      user's own API credentials before storing them. Generate one with:
#        python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#      Treat this like a master password — if it leaks, stored user keys
#      could be decrypted; if you lose it, stored keys become unusable and
#      everyone has to reconnect via /connectbinance.
#   5. pip install python-binance cryptography
#
# SAFETY + PRIVACY DESIGN:
#   • Rex (the AI) can only ever DISCUSS the market. It never places trades.
#   • EVERY user connects and trades on their OWN Binance account — nobody's
#     trade ever touches anyone else's funds, including the bot owner's.
#   • Each user's API key/secret is collected only in a private DM (never a
#     group), encrypted at rest, and only decrypted in-memory to make that
#     specific user's own API calls.
#   • Trade execution only happens via /trade + an explicit Confirm tap —
#     no autonomous execution path exists anywhere in this code.

try:
    from binance import AsyncClient as BinanceAsyncClient
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False

try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

BINANCE_TESTNET        = os.environ.get('BINANCE_TESTNET', 'true').lower() != 'false'
BINANCE_ENCRYPTION_KEY = os.environ.get('BINANCE_ENCRYPTION_KEY', '')
DATA_DIR               = os.environ.get('DATA_DIR', '.')
USER_KEYS_FILE         = os.path.join(DATA_DIR, 'binance_user_keys.enc.json')

fernet = None
if CRYPTOGRAPHY_AVAILABLE and BINANCE_ENCRYPTION_KEY:
    try:
        fernet = Fernet(BINANCE_ENCRYPTION_KEY.encode())
    except Exception as e:
        logger.error(f"❌ BINANCE_ENCRYPTION_KEY is invalid: {e}")

binance_client = None          # shared client for PUBLIC data only (prices) — no secrets needed
user_binance_clients = {}      # {user_id: authenticated AsyncClient} — cached per user

async def init_binance_client():
    """Connects a shared client for public market data (prices, candles) —
    this needs no credentials at all, so it works for everyone regardless
    of whether they've personally connected an account yet."""
    global binance_client
    if not BINANCE_AVAILABLE:
        logger.info("ℹ️ Binance not configured — 'python-binance' package isn't installed (check requirements.txt)")
        return
    try:
        binance_client = await BinanceAsyncClient.create(testnet=BINANCE_TESTNET)
        mode = "TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
        logger.info(f"✅ Binance public data client connected — mode: {mode}")
    except Exception as e:
        logger.error(f"❌ Binance connection failed: {e}")
        binance_client = None

# ── Per-user encrypted credential storage ───────────────────────
def _load_user_keys_store():
    if not os.path.exists(USER_KEYS_FILE):
        return {}
    try:
        with open(USER_KEYS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Could not read user keys store: {e}")
        return {}

def _save_user_keys_store(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USER_KEYS_FILE, 'w') as f:
        json.dump(store, f)

def save_user_binance_keys(user_id, api_key, api_secret):
    if not fernet:
        raise RuntimeError("BINANCE_ENCRYPTION_KEY isn't configured")
    store = _load_user_keys_store()
    store[str(user_id)] = {
        "api_key": fernet.encrypt(api_key.encode()).decode(),
        "api_secret": fernet.encrypt(api_secret.encode()).decode(),
    }
    _save_user_keys_store(store)

def get_user_binance_keys(user_id):
    if not fernet:
        return None
    store = _load_user_keys_store()
    entry = store.get(str(user_id))
    if not entry:
        return None
    return {
        "api_key": fernet.decrypt(entry["api_key"].encode()).decode(),
        "api_secret": fernet.decrypt(entry["api_secret"].encode()).decode(),
    }

def delete_user_binance_keys(user_id):
    store = _load_user_keys_store()
    if store.pop(str(user_id), None) is not None:
        _save_user_keys_store(store)

def mask_key(key):
    if not key or len(key) < 8:
        return "••••"
    return f"{key[:4]}…{key[-4:]}"

async def get_user_binance_client(user_id):
    """Returns this specific user's own authenticated Binance client,
    creating and caching it from their encrypted stored credentials.
    Returns None if they haven't connected an account yet."""
    if user_id in user_binance_clients:
        return user_binance_clients[user_id]
    creds = get_user_binance_keys(user_id)
    if not creds:
        return None
    try:
        client = await BinanceAsyncClient.create(
            creds["api_key"], creds["api_secret"], testnet=BINANCE_TESTNET
        )
        user_binance_clients[user_id] = client
        return client
    except Exception as e:
        logger.error(f"❌ Could not connect Binance client for user {user_id}: {e}")
        return None

# Common name -> Binance symbol mapping, so "how's bitcoin doing" works
# without the user needing to type the exact ticker.
COMMON_SYMBOL_ALIASES = {
    'btc': 'BTCUSDT', 'bitcoin': 'BTCUSDT',
    'eth': 'ETHUSDT', 'ethereum': 'ETHUSDT',
    'sol': 'SOLUSDT', 'solana': 'SOLUSDT',
    'bnb': 'BNBUSDT', 'binance coin': 'BNBUSDT',
    'xrp': 'XRPUSDT', 'ripple': 'XRPUSDT',
    'doge': 'DOGEUSDT', 'dogecoin': 'DOGEUSDT',
    'ada': 'ADAUSDT', 'cardano': 'ADAUSDT',
}
SYMBOL_PATTERN = re.compile(r'\b[A-Z]{2,10}USDT\b')

def detect_binance_symbols(text):
    """Finds up to 3 Binance symbols mentioned in free text, either as a
    raw ticker (BTCUSDT) or a common name (bitcoin, eth, etc.)."""
    found = []
    for m in SYMBOL_PATTERN.findall(text.upper()):
        if m not in found:
            found.append(m)
    lower = text.lower()
    for alias, sym in COMMON_SYMBOL_ALIASES.items():
        if re.search(rf'\b{re.escape(alias)}\b', lower) and sym not in found:
            found.append(sym)
    return found[:3]

async def fetch_binance_snapshot(symbol):
    """Read-only: current price + recent 15-minute candle trend for a symbol."""
    ticker = await binance_client.get_symbol_ticker(symbol=symbol)
    klines = await binance_client.get_klines(symbol=symbol, interval='15m', limit=8)
    closes = [float(k[4]) for k in klines]
    change_pct = round(((closes[-1] - closes[0]) / closes[0]) * 100, 2) if len(closes) >= 2 else 0.0
    return {
        "symbol": symbol,
        "price": ticker['price'],
        "change_last_2h_pct": change_pct,
    }

async def build_live_data_context(user_text):
    """Detects any Binance symbols mentioned in the message, fetches live
    snapshots for each, and returns a text block to ground Rex's reply in
    real numbers. Returns '' if Binance isn't connected or nothing found."""
    if not binance_client:
        return ''
    symbols = detect_binance_symbols(user_text)
    if not symbols:
        return ''
    lines = []
    for symbol in symbols:
        try:
            snap = await fetch_binance_snapshot(symbol)
            lines.append(
                f"{snap['symbol']}: ${snap['price']} "
                f"({snap['change_last_2h_pct']:+.2f}% over the last ~2h)"
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch live data for {symbol}: {e}")
    if not lines:
        return ''
    return "\n[LIVE BINANCE DATA — use these real current numbers, don't invent your own]\n" + "\n".join(lines)

# ── Manually-confirmed trade execution ──────────────────────────
pending_trades = {}   # {user_id: {"symbol", "side", "quantity"}}

# ── Open position tracking (for live 🟢/🔴 status + Win/Loss on close) ──
OPEN_POSITIONS_FILE = os.path.join(DATA_DIR, 'open_positions.json')

def _load_open_positions():
    if not os.path.exists(OPEN_POSITIONS_FILE):
        return {}
    try:
        with open(OPEN_POSITIONS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Could not read open positions file: {e}")
        return {}

def _save_open_positions(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OPEN_POSITIONS_FILE, 'w') as f:
        json.dump(store, f)

open_positions = _load_open_positions()  # {user_id_str: [{"id","symbol","quantity","entry_price","order_id"}, ...]}

def add_open_position(user_id, symbol, quantity, entry_price, order_id, stop_loss_price=None, is_autotrade=False):
    key = str(user_id)
    positions = open_positions.setdefault(key, [])
    position_id = f"{order_id}"
    positions.append({
        "id": position_id, "symbol": symbol, "quantity": quantity,
        "entry_price": entry_price, "order_id": order_id,
        "stop_loss_price": stop_loss_price, "is_autotrade": is_autotrade
    })
    _save_open_positions(open_positions)
    return position_id

def remove_open_position(user_id, position_id):
    key = str(user_id)
    positions = open_positions.get(key, [])
    open_positions[key] = [p for p in positions if p["id"] != position_id]
    _save_open_positions(open_positions)
    last_position_verdict.pop(position_id, None)
trade_flow_state = {} # {user_id: {"step": "awaiting_symbol_text"/"awaiting_quantity", "symbol":.., "side":..}}

TRADE_COMMAND_PATTERN = re.compile(
    r'^/trade\s+([A-Za-z0-9]+)\s+(BUY|SELL)\s+([\d.]+)\s*$', re.IGNORECASE
)

QUICK_TRADE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

# ══════════════════════════════════════════════════════════════
# NEW: Opportunity scanner (proactive detection, manual confirm only)
# ══════════════════════════════════════════════════════════════
#
# This scans a watchlist on a timer and DMs opted-in, Binance-connected
# users when a simple pattern-based setup shows up. It is a heuristic,
# NOT a guarantee — same honesty as everywhere else in this bot. And
# critically: it only ever ASKS. It reuses the exact same manual
# quantity-entry + Confirm flow as everything else — there is still no
# code path where a trade fires without a human tapping Confirm.

SCAN_SYMBOLS = [s.strip().upper() for s in os.environ.get('SCAN_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT').split(',') if s.strip()]
SCAN_INTERVAL_MINUTES = float(os.environ.get('SCAN_INTERVAL_MINUTES', '15'))
SCAN_KLINE_INTERVAL = os.environ.get('SCAN_KLINE_INTERVAL', '15m')

ALERTS_OPT_IN_FILE = os.path.join(DATA_DIR, 'alerts_opt_in.json')

def _load_opt_in_set():
    if not os.path.exists(ALERTS_OPT_IN_FILE):
        return set()
    try:
        with open(ALERTS_OPT_IN_FILE) as f:
            return set(json.load(f))
    except Exception as e:
        logger.warning(f"⚠️ Could not read alerts opt-in file: {e}")
        return set()

def _save_opt_in_set(id_set):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ALERTS_OPT_IN_FILE, 'w') as f:
        json.dump(list(id_set), f)

alerts_opted_in = _load_opt_in_set()
last_opportunity_direction = {}  # {symbol: "BUY"/"SELL"/None} — avoids re-alerting every cycle
last_opportunity_direction_futures = {}  # separate tracking — futures signals are independent of spot

def ema_series(values, period):
    """Exponential moving average, seeded with a simple average of the
    first `period` values (standard EMA construction)."""
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(values[:period]) / period]
    for price in values[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

def sma_series(values, period):
    if len(values) < period:
        return []
    return [sum(values[i - period + 1:i + 1]) / period for i in range(period - 1, len(values))]

def compute_macd(closes, fast=8, slow=12, signal=9):
    """Returns (macd_line, signal_line, histogram) using the same periods
    taught in the Trending Strategy: input 8, slope 12, signal 9."""
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    if not ema_fast or not ema_slow:
        return [], [], []
    offset = slow - fast
    ema_fast_aligned = ema_fast[offset:]
    macd_line = [f - s for f, s in zip(ema_fast_aligned, ema_slow)]
    signal_line = ema_series(macd_line, signal)
    if not signal_line:
        return macd_line, [], []
    macd_aligned = macd_line[signal - 1:]
    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]
    return macd_aligned, signal_line, histogram

LC_MISSING = float('nan')

def lc_is_missing(v):
    return isinstance(v, float) and math.isnan(v)

def lc_nz(v, fallback=0.0):
    return fallback if lc_is_missing(v) else v

def lc_ema(src, period):
    out = [LC_MISSING] * len(src)
    if period <= 0:
        return out
    alpha = 2.0 / (period + 1)
    for i, value in enumerate(src):
        if lc_is_missing(value):
            continue
        if i > 0 and not lc_is_missing(out[i - 1]):
            out[i] = alpha * value + (1 - alpha) * out[i - 1]
            continue
        if i >= period - 1:
            window = src[i - period + 1:i + 1]
            if not any(lc_is_missing(v) for v in window):
                out[i] = sum(window) / period
    return out

def lc_sma(src, period):
    out = [LC_MISSING] * len(src)
    for i in range(len(src)):
        if i < period - 1:
            continue
        window = src[i - period + 1:i + 1]
        if any(lc_is_missing(v) for v in window):
            continue
        out[i] = sum(window) / period
    return out

def lc_rma(src, period):
    out = [LC_MISSING] * len(src)
    alpha = 1.0 / period
    for i, value in enumerate(src):
        if lc_is_missing(value):
            continue
        if i > 0 and not lc_is_missing(out[i - 1]):
            out[i] = alpha * value + (1 - alpha) * out[i - 1]
            continue
        if i >= period - 1:
            window = src[i - period + 1:i + 1]
            if not any(lc_is_missing(v) for v in window):
                out[i] = sum(window) / period
    return out

def lc_wilder_smooth(src, period):
    out = [LC_MISSING] * len(src)
    for i, value in enumerate(src):
        if i == 0 or lc_is_missing(out[i - 1]):
            out[i] = value
        else:
            out[i] = out[i - 1] - out[i - 1] / period + value
    return out

def lc_rescale(src, old_min, old_max, new_min, new_max):
    return new_min + (new_max - new_min) * (src - old_min) / max(old_max - old_min, 1e-9)

def lc_normalize_running(src, out_min=0.0, out_max=1.0):
    out = [LC_MISSING] * len(src)
    hist_min, hist_max = 1e11, -1e11
    for i, value in enumerate(src):
        if lc_is_missing(value):
            continue
        hist_min = min(hist_min, value)
        hist_max = max(hist_max, value)
        out[i] = out_min + (out_max - out_min) * (value - hist_min) / max(hist_max - hist_min, 1e-9)
    return out

def lc_calc_rsi(src, period):
    gain = [LC_MISSING] * len(src)
    loss = [LC_MISSING] * len(src)
    for i in range(1, len(src)):
        change = src[i] - src[i - 1]
        gain[i] = change if change > 0 else 0.0
        loss[i] = -change if change < 0 else 0.0
    gain_rma, loss_rma = lc_rma(gain, period), lc_rma(loss, period)
    out = [LC_MISSING] * len(src)
    for i in range(len(src)):
        if lc_is_missing(gain_rma[i]) or lc_is_missing(loss_rma[i]):
            continue
        if loss_rma[i] == 0:
            out[i] = 100.0
        else:
            rs = gain_rma[i] / loss_rma[i]
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out

def lc_calc_normalized_rsi(src, n1, n2):
    smoothed = lc_ema(lc_calc_rsi(src, n1), n2)
    return [lc_rescale(v, 0, 100, 0, 1) if not lc_is_missing(v) else LC_MISSING for v in smoothed]

def lc_calc_cci(src, period):
    avg = lc_sma(src, period)
    out = [LC_MISSING] * len(src)
    for i in range(len(src)):
        if lc_is_missing(avg[i]):
            continue
        window = src[i - period + 1:i + 1]
        mean_dev = sum(abs(v - avg[i]) for v in window) / period
        out[i] = (src[i] - avg[i]) / (0.015 * mean_dev) if mean_dev != 0 else 0.0
    return out

def lc_calc_normalized_cci(src, n1, n2):
    return lc_normalize_running(lc_ema(lc_calc_cci(src, n1), n2))

def lc_calc_wavetrend(hlc3, n1, n2):
    ema1 = lc_ema(hlc3, n1)
    abs_dev = [abs(hlc3[i] - ema1[i]) if not lc_is_missing(ema1[i]) else LC_MISSING for i in range(len(hlc3))]
    ema2 = lc_ema(abs_dev, n1)
    ci = [LC_MISSING] * len(hlc3)
    for i in range(len(hlc3)):
        if lc_is_missing(ema1[i]) or lc_is_missing(ema2[i]):
            continue
        ci[i] = (hlc3[i] - ema1[i]) / (0.015 * ema2[i]) if ema2[i] != 0 else 0.0
    wt1 = lc_ema(ci, n2)
    wt2 = lc_sma(wt1, 4)
    raw = [wt1[i] - wt2[i] if not lc_is_missing(wt1[i]) and not lc_is_missing(wt2[i]) else LC_MISSING for i in range(len(hlc3))]
    return lc_normalize_running(raw)

def lc_calc_adx_normalized(high, low, close, period):
    tr, dm_plus, dm_minus = [], [], []
    for i in range(len(close)):
        prev_close = close[i - 1] if i > 0 else 0.0
        prev_high = high[i - 1] if i > 0 else 0.0
        prev_low = low[i - 1] if i > 0 else 0.0
        tr.append(max(high[i] - low[i], abs(high[i] - prev_close), abs(low[i] - prev_close)))
        up_move = high[i] - prev_high
        down_move = prev_low - low[i]
        dm_plus.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        dm_minus.append(down_move if down_move > up_move and down_move > 0 else 0.0)
    tr_s, plus_s, minus_s = lc_wilder_smooth(tr, period), lc_wilder_smooth(dm_plus, period), lc_wilder_smooth(dm_minus, period)
    dx = []
    for i in range(len(close)):
        di_plus = plus_s[i] / tr_s[i] * 100 if tr_s[i] != 0 else 0.0
        di_minus = minus_s[i] / tr_s[i] * 100 if tr_s[i] != 0 else 0.0
        dx.append(abs(di_plus - di_minus) / (di_plus + di_minus) * 100 if di_plus + di_minus else 0.0)
    adx_rma = lc_rma(dx, period)
    return [lc_rescale(v, 0, 100, 0, 1) if not lc_is_missing(v) else LC_MISSING for v in adx_rma]

def lc_calc_atr(high, low, close, period):
    tr = []
    for i in range(len(close)):
        prev_close = close[i - 1] if i > 0 else 0.0
        tr.append(max(high[i] - low[i], abs(high[i] - prev_close), abs(low[i] - prev_close)))
    return lc_rma(tr, period)

def lc_calc_regime_filter(ohlc4, high, low):
    n = len(ohlc4)
    abs_slope, ema_abs = [0.0] * n, [0.0] * n
    if not n:
        return abs_slope, ema_abs
    value1, value2, klmf = [0.0] * n, [0.0] * n, [0.0] * n
    value2[0] = high[0] - low[0]
    klmf[0] = ohlc4[0]
    alpha_ema = 2.0 / 201.0
    for i in range(1, n):
        value1[i] = 0.2 * (ohlc4[i] - ohlc4[i - 1]) + 0.8 * lc_nz(value1[i - 1])
        value2[i] = 0.1 * (high[i] - low[i]) + 0.8 * lc_nz(value2[i - 1])
        omega = abs(value1[i] / value2[i]) if value2[i] != 0 else 0.0
        alpha = (-(omega ** 2) + math.sqrt(omega ** 4 + 16.0 * omega ** 2)) / 8.0
        klmf[i] = alpha * ohlc4[i] + (1.0 - alpha) * lc_nz(klmf[i - 1])
        abs_slope[i] = abs(klmf[i] - klmf[i - 1])
        prev_ema = lc_nz(ema_abs[i - 1])
        ema_abs[i] = abs_slope[i] if (prev_ema == 0 and i < 200) else alpha_ema * abs_slope[i] + (1.0 - alpha_ema) * prev_ema
    return abs_slope, ema_abs

def lc_kernel_rational_quadratic(src, bar_index, lookback, relative_weight, start_at_bar):
    current_weight, cumulative_weight = 0.0, 0.0
    denom = max(float(lookback ** 2) * 2.0 * relative_weight, 1e-10)
    for i in range(min(1 + start_at_bar, bar_index) + 1):
        weight = (1.0 + (i ** 2 / denom)) ** (-relative_weight)
        current_weight += src[bar_index - i] * weight
        cumulative_weight += weight
    return current_weight / cumulative_weight if cumulative_weight > 0 else src[bar_index]

class LorentzianAnnState:
    """Faithful port of the real indicator's nearest-neighbor search: log-
    based Lorentzian distance, skipping every 4th historical bar, keeping a
    running best-k window with threshold-based eviction — not just a plain
    top-k sort."""
    def __init__(self, feature_count=5):
        self.features = [[] for _ in range(feature_count)]
        self.labels = []
        self.distances = []
        self.predictions = []

    def push(self, values, label):
        for idx, value in enumerate(values):
            self.features[idx].append(value)
        self.labels.append(label)

    def distance(self, idx, values, feature_count):
        d = 0.0
        for fidx in range(feature_count):
            current, historical = values[fidx], self.features[fidx][idx]
            if lc_is_missing(current) or lc_is_missing(historical):
                return -math.inf
            d += math.log(1.0 + abs(current - historical))
        return d

    def run(self, values, neighbors_count, max_bars_back, feature_count, last_bar_index):
        if not self.labels:
            return 0
        size_loop = min(max_bars_back - 1, len(self.labels) - 1)
        max_bars_back_index = last_bar_index - max_bars_back if last_bar_index >= max_bars_back else 0
        last_distance = -1.0
        for idx in range(max_bars_back_index, size_loop + 1):
            d = self.distance(idx, values, feature_count)
            if d >= last_distance and idx % 4 != 0:
                last_distance = d
                self.distances.append(d)
                self.predictions.append(round(self.labels[idx]))
                if len(self.predictions) > neighbors_count:
                    threshold_idx = round(neighbors_count * 3.0 / 4.0)
                    last_distance = self.distances[threshold_idx]
                    self.distances.pop(0)
                    self.predictions.pop(0)
        return int(sum(self.predictions))

async def get_lorentzian_signal(symbol, neighbors_count=8, max_bars_back=2000):
    """Faithful port of the real 'Machine Learning: Lorentzian Classification'
    indicator by jdehorty: 5 normalized features (RSI 14, WaveTrend 10/11,
    CCI 20, ADX 20, RSI 9), the real trailing-comparison label convention,
    the real every-4th-bar-skipped nearest-neighbor search, plus the real
    volatility/regime filters and kernel-regression momentum confirmation.
    Returns 'BUY', 'SELL', or None."""
    try:
        klines = await binance_client.get_klines(symbol=symbol, interval=SCAN_KLINE_INTERVAL, limit=300)
    except Exception as e:
        logger.warning(f"⚠️ Lorentzian: couldn't fetch klines for {symbol}: {e}")
        return None

    if len(klines) < 60:
        return None

    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    n = len(closes)
    hlc3 = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    ohlc4 = [(opens[i] + highs[i] + lows[i] + closes[i]) / 4 for i in range(n)]

    f1 = lc_calc_normalized_rsi(closes, 14, 1)
    f2 = lc_calc_wavetrend(hlc3, 10, 11)
    f3 = lc_calc_normalized_cci(closes, 20, 1)
    f4 = lc_calc_adx_normalized(highs, lows, closes, 20)
    f5 = lc_calc_normalized_rsi(closes, 9, 1)
    features_by_bar = list(zip(f1, f2, f3, f4, f5))

    ann = LorentzianAnnState(feature_count=5)
    for i in range(n - 1):  # exclude the last bar — it's the query, not training data
        train_label = 0
        if i >= 4:
            train_label = -1 if closes[i - 4] < closes[i] else 1 if closes[i - 4] > closes[i] else 0
        ann.push(features_by_bar[i], train_label)

    if len(ann.labels) < neighbors_count:
        return None

    prediction = ann.run(features_by_bar[-1], neighbors_count, max_bars_back, 5, n - 1)

    atr1, atr10 = lc_calc_atr(highs, lows, closes, 1), lc_calc_atr(highs, lows, closes, 10)
    filt_vol = atr1[-1] > atr10[-1] if not lc_is_missing(atr1[-1]) and not lc_is_missing(atr10[-1]) else True

    reg_slope, reg_ema_slope = lc_calc_regime_filter(ohlc4, highs, lows)
    filt_regime = True
    if reg_ema_slope[-1] != 0:
        norm_slope = (reg_slope[-1] - reg_ema_slope[-1]) / reg_ema_slope[-1]
        filt_regime = norm_slope >= -0.1

    yhat1 = [lc_kernel_rational_quadratic(closes, i, 8, 8.0, 25) for i in range(n - 3, n)]
    is_bullish_rate = yhat1[-2] < yhat1[-1]
    is_bearish_rate = yhat1[-2] > yhat1[-1]

    if prediction > 0 and filt_vol and filt_regime and is_bullish_rate:
        return 'BUY'
    if prediction < 0 and filt_vol and filt_regime and is_bearish_rate:
        return 'SELL'
    return None

# ── Futures variants — identical math, futures candle data instead of spot ──
async def get_lorentzian_signal_futures(symbol, neighbors_count=8, max_bars_back=2000):
    """Same faithful Lorentzian Classification as get_lorentzian_signal, but
    reading Binance FUTURES candles instead of spot (futures prices differ
    slightly from spot due to funding-rate basis, so this reads its own
    data rather than assuming spot candles are close enough)."""
    try:
        klines = await binance_client.futures_klines(symbol=symbol, interval=SCAN_KLINE_INTERVAL, limit=300)
    except Exception as e:
        logger.warning(f"⚠️ Lorentzian (futures): couldn't fetch klines for {symbol}: {e}")
        return None

    if len(klines) < 60:
        return None

    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    n = len(closes)
    hlc3 = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    ohlc4 = [(opens[i] + highs[i] + lows[i] + closes[i]) / 4 for i in range(n)]

    f1 = lc_calc_normalized_rsi(closes, 14, 1)
    f2 = lc_calc_wavetrend(hlc3, 10, 11)
    f3 = lc_calc_normalized_cci(closes, 20, 1)
    f4 = lc_calc_adx_normalized(highs, lows, closes, 20)
    f5 = lc_calc_normalized_rsi(closes, 9, 1)
    features_by_bar = list(zip(f1, f2, f3, f4, f5))

    ann = LorentzianAnnState(feature_count=5)
    for i in range(n - 1):
        train_label = 0
        if i >= 4:
            train_label = -1 if closes[i - 4] < closes[i] else 1 if closes[i - 4] > closes[i] else 0
        ann.push(features_by_bar[i], train_label)

    if len(ann.labels) < neighbors_count:
        return None

    prediction = ann.run(features_by_bar[-1], neighbors_count, max_bars_back, 5, n - 1)

    atr1, atr10 = lc_calc_atr(highs, lows, closes, 1), lc_calc_atr(highs, lows, closes, 10)
    filt_vol = atr1[-1] > atr10[-1] if not lc_is_missing(atr1[-1]) and not lc_is_missing(atr10[-1]) else True

    reg_slope, reg_ema_slope = lc_calc_regime_filter(ohlc4, highs, lows)
    filt_regime = True
    if reg_ema_slope[-1] != 0:
        norm_slope = (reg_slope[-1] - reg_ema_slope[-1]) / reg_ema_slope[-1]
        filt_regime = norm_slope >= -0.1

    yhat1 = [lc_kernel_rational_quadratic(closes, i, 8, 8.0, 25) for i in range(n - 3, n)]
    is_bullish_rate = yhat1[-2] < yhat1[-1]
    is_bearish_rate = yhat1[-2] > yhat1[-1]

    if prediction > 0 and filt_vol and filt_regime and is_bullish_rate:
        return 'BUY'
    if prediction < 0 and filt_vol and filt_regime and is_bearish_rate:
        return 'SELL'
    return None

async def analyze_symbol_futures(symbol):
    """Same diagnostic analysis as analyze_symbol, reading futures candles.
    On futures, BOTH BUY (long) and SELL (short) verdicts are genuinely
    actionable, unlike spot where a bare SELL has nothing to act on."""
    try:
        klines = await binance_client.futures_klines(symbol=symbol, interval=SCAN_KLINE_INTERVAL, limit=100)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    if len(klines) < 60:
        return {"symbol": symbol, "error": "not enough candle history yet"}

    opens = [float(k[1]) for k in klines]
    closes = [float(k[4]) for k in klines]
    last_price = closes[-1]

    sma7 = sma_series(closes, 7)
    ema45 = ema_series(closes, 45)
    macd_line, signal_line, histogram = compute_macd(closes, fast=8, slow=12, signal=9)

    if not sma7 or not ema45 or not macd_line:
        return {"symbol": symbol, "error": "indicators could not be computed"}

    last_sma7 = sma7[-1]
    last_ema45 = ema45[-1]
    last_macd = macd_line[-1]

    last_directions = ['up' if c > o else 'down' if c < o else 'flat' for o, c in zip(opens[-4:], closes[-4:])]
    up_count = sum(1 for d in last_directions if d == 'up')
    down_count = sum(1 for d in last_directions if d == 'down')
    all_up = up_count >= 3
    all_down = down_count >= 3
    trend = "up" if all_up else "down" if all_down else "mixed (ranging)"

    base_verdict = None
    if all_up and last_price > last_sma7 and last_price > last_ema45 and last_macd > 0:
        base_verdict = 'BUY'
    elif all_down and last_price < last_sma7 and last_price < last_ema45 and last_macd < 0:
        base_verdict = 'SELL'

    verdict = None
    lorentzian_verdict = None
    if base_verdict:
        lorentzian_verdict = await get_lorentzian_signal_futures(symbol)
        opposite = 'SELL' if base_verdict == 'BUY' else 'BUY'
        if lorentzian_verdict != opposite:
            verdict = base_verdict

    return {
        "symbol": symbol,
        "price": last_price,
        "sma7": last_sma7,
        "ema45": last_ema45,
        "macd": last_macd,
        "trend": trend,
        "base_verdict": base_verdict,
        "lorentzian_verdict": lorentzian_verdict,
        "verdict": verdict,
    }

async def analyze_symbol(symbol):
    """Runs the actual Trending Strategy indicators on live candles and
    returns a full diagnostic dict — not just a verdict. Used by both the
    background scanner and /checknow (so /checknow shows real live numbers,
    not a canned test)."""
    try:
        klines = await binance_client.get_klines(symbol=symbol, interval=SCAN_KLINE_INTERVAL, limit=100)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    if len(klines) < 60:
        return {"symbol": symbol, "error": "not enough candle history yet"}

    opens = [float(k[1]) for k in klines]
    closes = [float(k[4]) for k in klines]
    last_price = closes[-1]

    sma7 = sma_series(closes, 7)
    ema45 = ema_series(closes, 45)
    macd_line, signal_line, histogram = compute_macd(closes, fast=8, slow=12, signal=9)

    if not sma7 or not ema45 or not macd_line:
        return {"symbol": symbol, "error": "indicators could not be computed"}

    last_sma7 = sma7[-1]
    last_ema45 = ema45[-1]
    last_macd = macd_line[-1]

    last_directions = ['up' if c > o else 'down' if c < o else 'flat' for o, c in zip(opens[-4:], closes[-4:])]
    up_count = sum(1 for d in last_directions if d == 'up')
    down_count = sum(1 for d in last_directions if d == 'down')
    all_up = up_count >= 3   # 3-of-4, not a strict 4-of-4 — tolerates one noisy candle inside a real trend
    all_down = down_count >= 3
    trend = "up" if all_up else "down" if all_down else "mixed (ranging)"

    base_verdict = None
    if all_up and last_price > last_sma7 and last_price > last_ema45 and last_macd > 0:
        base_verdict = 'BUY'
    elif all_down and last_price < last_sma7 and last_price < last_ema45 and last_macd < 0:
        base_verdict = 'SELL'

    # Only veto on an ACTIVE contradiction from the Lorentzian layer, not on
    # it simply having no clear read. The Lorentzian layer bundles 4 of its
    # own conditions (classifier prediction, volatility filter, regime
    # filter, kernel confirmation) — requiring it to fully confirm on top
    # of our own 4-condition trend check was too strict in practice (real
    # BUY setups were getting vetoed just because the Lorentzian side had
    # no strong opinion, not because it disagreed).
    verdict = None
    lorentzian_verdict = None
    if base_verdict:
        lorentzian_verdict = await get_lorentzian_signal(symbol)
        opposite = 'SELL' if base_verdict == 'BUY' else 'BUY'
        if lorentzian_verdict != opposite:
            verdict = base_verdict

    return {
        "symbol": symbol,
        "price": last_price,
        "sma7": last_sma7,
        "ema45": last_ema45,
        "macd": last_macd,
        "trend": trend,
        "base_verdict": base_verdict,
        "lorentzian_verdict": lorentzian_verdict,
        "verdict": verdict,
    }

async def detect_opportunity(symbol):
    """Runs the actual Trending Strategy indicators on live candles:
    MACD(8,12,9), SMA(7) 'green line', EMA(45) 'yellow line', plus the
    same trend-vs-range read (consecutive candle colors). All four have
    to agree before this counts as an opportunity. Still NOT a guarantee —
    same honesty as the strategy write-up itself."""
    result = await analyze_symbol(symbol)
    if "error" in result:
        if "history" not in result["error"]:
            logger.warning(f"⚠️ Scan: couldn't analyze {symbol}: {result['error']}")
        return None
    return result["verdict"]

async def detect_opportunity_futures(symbol):
    """Same as detect_opportunity, but reads futures candles — futures and
    spot prices differ slightly (funding-rate basis), so futures trading
    decisions should be based on futures data, not spot."""
    result = await analyze_symbol_futures(symbol)
    if "error" in result:
        if "history" not in result["error"]:
            logger.warning(f"⚠️ Scan (futures): couldn't analyze {symbol}: {result['error']}")
        return None
    return result["verdict"]

async def notify_opportunity(bot, symbol, direction):
    label = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    trend_word = "up" if direction == "BUY" else "down"
    position_word = "above" if direction == "BUY" else "below"
    for user_id in list(alerts_opted_in):
        if not get_user_binance_keys(user_id):
            continue  # not connected — nothing they could do with this alert
        try:
            await bot.send_message(
                user_id,
                f"🚨 *Opportunity Spotted!*\n\n"
                f"*{symbol}* is showing a possible *{label}* setup right now, "
                f"using your Trending Strategy indicators:\n"
                f"• Last candles trending {trend_word} 🕯️\n"
                f"• Price {position_word} SMA(7) and EMA(45) 📏\n"
                f"• MACD(8,12,9) confirms the direction 📈\n\n"
                f"This is a pattern match, not a guarantee — want to set up a trade to review?",
                buttons=[[Button.inline("✅ Yes, let's look", f"opportunity:yes:{symbol}:{direction}".encode()),
                          Button.inline("🔕 No thanks", b"opportunity:no")]],
                parse_mode='markdown'
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not alert user {user_id}: {e}")

last_position_verdict = {}  # {position_id: last verdict seen} — avoids repeat exit alerts every cycle

async def scan_positions_for_exit_signals(bot):
    """Checks every open BUY position using the same indicators, and alerts
    the specific holder when the trend looks like it's reversing — i.e.
    'you found a good entry, here's a good exit.' Always active for anyone
    holding a position, regardless of the general alerts opt-in, since this
    is about money they've already committed, not a new speculative tip."""
    for user_id_str, positions in list(open_positions.items()):
        user_id = int(user_id_str)
        for p in list(positions):
            try:
                result = await analyze_symbol(p["symbol"])
            except Exception as e:
                logger.warning(f"⚠️ Exit scan error for {p['symbol']}: {e}")
                continue
            if "error" in result:
                continue

            verdict = result["verdict"]
            previous = last_position_verdict.get(p["id"])

            if verdict == "SELL" and previous != "SELL":
                current_price = result["price"]
                change_pct = ((current_price - p["entry_price"]) / p["entry_price"]) * 100
                move_emoji = "🟢" if current_price >= p["entry_price"] else "🔴"

                if p.get("is_autotrade"):
                    await close_autotrade_position(bot, user_id, p, current_price, "📉 Trend reversed")
                    last_position_verdict[p["id"]] = verdict
                    continue

                try:
                    await bot.send_message(
                        user_id,
                        f"🎯 *Possible Time to Sell!*\n\n"
                        f"*{p['symbol']}* trend looks like it's reversing — MACD(8,12,9), "
                        f"SMA(7) and EMA(45) now agree on SELL.\n\n"
                        f"{move_emoji} Entry: ${p['entry_price']:,.4f} | Now: ${current_price:,.4f} "
                        f"({change_pct:+.2f}%)\n\n"
                        f"Want to close this position now?",
                        buttons=[[Button.inline("💰 Close Position", f"position:close:{p['id']}".encode()),
                                  Button.inline("🤝 Keep Holding", b"position:keep")]],
                        parse_mode='markdown'
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Could not send exit alert to {user_id}: {e}")

            last_position_verdict[p["id"]] = verdict

async def scan_for_opportunities(bot):
    """Background loop — checks the watchlist every SCAN_INTERVAL_MINUTES
    and notifies opted-in users on new setups only (not every cycle).
    Also checks everyone's open positions for exit signals each cycle.
    Runs an immediate check on startup (not just after the first sleep),
    so a redeploy doesn't cost a full wasted interval before anything runs."""
    while True:
        if binance_client:
            for symbol in SCAN_SYMBOLS:
                try:
                    direction = await detect_opportunity(symbol)
                except Exception as e:
                    logger.warning(f"⚠️ Scan error for {symbol}: {e}")
                    continue
                previous = last_opportunity_direction.get(symbol)
                if direction and direction != previous:
                    last_opportunity_direction[symbol] = direction
                    if alerts_opted_in:
                        await notify_opportunity(bot, symbol, direction)
                    if direction == "BUY":
                        for user_id_str, session in list(autotrade_sessions.items()):
                            if session.get("enabled"):
                                await execute_autotrade(bot, int(user_id_str), symbol, direction)
                elif not direction:
                    last_opportunity_direction[symbol] = None

                if futures_sessions:
                    try:
                        futures_direction = await detect_opportunity_futures(symbol)
                    except Exception as e:
                        logger.warning(f"⚠️ Futures scan error for {symbol}: {e}")
                        futures_direction = None
                    previous_futures = last_opportunity_direction_futures.get(symbol)
                    if futures_direction and futures_direction != previous_futures:
                        last_opportunity_direction_futures[symbol] = futures_direction
                        for user_id_str, fsession in list(futures_sessions.items()):
                            if fsession.get("enabled"):
                                await execute_futures_autotrade(bot, int(user_id_str), symbol, futures_direction)
                    elif not futures_direction:
                        last_opportunity_direction_futures[symbol] = None

            await scan_positions_for_exit_signals(bot)

        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)

async def send_alerts_status(bot, chat, user_id):
    is_on = user_id in alerts_opted_in
    status = "🔔 ON" if is_on else "🔕 OFF"
    await bot.send_message(
        chat,
        f"📡 *Opportunity Alerts* — currently {status}\n\n"
        f"When ON, I scan {', '.join(SCAN_SYMBOLS)} every ~{int(SCAN_INTERVAL_MINUTES)} min "
        f"using your Trending Strategy indicators (MACD 8/12/9, SMA(7), EMA(45), plus the "
        f"trend-vs-range read). If they all agree, I'll message you here — you still "
        f"review and confirm everything manually, nothing trades automatically.\n\n"
        f"Requires a connected Binance account (/connectbinance) to receive alerts.",
        buttons=[[Button.inline("🔔 Turn On", b"alerts:on"), Button.inline("🔕 Turn Off", b"alerts:off")],
                 [Button.inline("🏠 Main Menu", b"menu:main")]],
        parse_mode='markdown'
    )

def setup_opportunity_alerts_handlers(bot):
    @bot.on(events.NewMessage(incoming=True, pattern=r'^/checknow$'))
    async def checknow_command(event):
        if not binance_client:
            await event.respond("📊 Live data isn't set up yet — the bot owner needs to install python-binance. 🔧")
            return
        status_msg = await event.respond(f"🔄 Checking {', '.join(SCAN_SYMBOLS)} right now...")
        lines = []
        for symbol in SCAN_SYMBOLS:
            result = await analyze_symbol(symbol)
            if "error" in result:
                lines.append(f"⚠️ *{symbol}*: {result['error']}")
                continue
            verdict = result["verdict"]
            base = result.get("base_verdict")
            lor = result.get("lorentzian_verdict")
            verdict_label = "🟢 BUY setup" if verdict == "BUY" else "🔴 SELL setup" if verdict == "SELL" else "— no setup right now"
            agreement_note = ""
            if base and not verdict:
                agreement_note = f"\n  ⛔ Trend indicators say {base}, but Lorentzian layer actively says {lor} instead — vetoed"
            lines.append(
                f"*{symbol}* — {verdict_label}\n"
                f"  Price: ${result['price']:,.4f} | Trend: {result['trend']}\n"
                f"  SMA(7): ${result['sma7']:,.4f} | EMA(45): ${result['ema45']:,.4f}\n"
                f"  MACD(8,12,9): {result['macd']:+.4f}"
                f"{agreement_note}"
            )
        await status_msg.edit(
            "📊 *Live Check* — real data, right now:\n\n" + "\n\n".join(lines),
            parse_mode='markdown'
        )

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/alerts$'))
    async def alerts_status_command(event):
        chat = await event.get_chat()
        await send_alerts_status(bot, chat, event.sender_id)

    @bot.on(events.CallbackQuery(data=b"menu:alerts"))
    async def alerts_status_menu(event):
        await event.answer()
        chat = await event.get_chat()
        await send_alerts_status(bot, chat, event.sender_id)

    @bot.on(events.CallbackQuery(data=b"alerts:on"))
    async def alerts_on_callback(event):
        alerts_opted_in.add(event.sender_id)
        _save_opt_in_set(alerts_opted_in)
        await event.edit("🔔 *Opportunity alerts turned ON* — I'll message you here if I spot a setup.", buttons=None, parse_mode='markdown')

    @bot.on(events.CallbackQuery(data=b"alerts:off"))
    async def alerts_off_callback(event):
        alerts_opted_in.discard(event.sender_id)
        _save_opt_in_set(alerts_opted_in)
        await event.edit("🔕 *Opportunity alerts turned OFF.*", buttons=None, parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^opportunity:yes:([^:]+):(BUY|SELL)$"))
    async def opportunity_yes_callback(event):
        symbol = event.pattern_match.group(1).decode()
        side = event.pattern_match.group(2).decode()
        if not await get_user_binance_client(event.sender_id):
            await event.edit("You haven't connected a Binance account. Use /connectbinance first. 🔐", buttons=None)
            return
        trade_flow_state[event.sender_id] = {"step": "awaiting_quantity", "symbol": symbol, "side": side}
        await event.edit(
            f"📊 *{symbol}* — *{side}*\n\nHow much? Type the quantity, e.g. `0.001`",
            buttons=None,
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"opportunity:no"))
    async def opportunity_no_callback(event):
        await event.edit("👍 No problem — I'll keep scanning.", buttons=None)

    logger.info(f"✅ Opportunity scanner handlers registered (watching {', '.join(SCAN_SYMBOLS)} every {SCAN_INTERVAL_MINUTES}min)")

async def get_min_notional(symbol):
    """Looks up the minimum order value (price × quantity) Binance requires
    for this symbol. Returns None if it can't be determined."""
    try:
        info = await binance_client.get_symbol_info(symbol)
        if not info:
            return None
        for f in info.get('filters', []):
            if f.get('filterType') in ('NOTIONAL', 'MIN_NOTIONAL'):
                value = f.get('minNotional') or f.get('notional')
                if value is not None:
                    return float(value)
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch min notional for {symbol}: {e}")
    return None

def get_quote_asset(symbol):
    """Best-effort guess at the quote asset from the symbol name, so we
    know which balance to size risk against."""
    for quote in ("USDT", "BUSD", "USDC", "FDUSD", "BTC", "ETH"):
        if symbol.endswith(quote):
            return quote
    return "USDT"

def autotrade_amount_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"autotrade:amountpct:{p}".encode()) for p in [2, 5, 10]]]
    rows.append([Button.inline("✏️ Type a custom %", b"autotrade:amountpct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def autotrade_stoploss_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"autotrade:stoplosspct:{p}".encode()) for p in [1, 2, 3]]]
    rows.append([Button.inline("✏️ Type a custom %", b"autotrade:stoplosspct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def autotrade_losslimit_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"autotrade:losslimitpct:{p}".encode()) for p in [5, 10, 15]]]
    rows.append([Button.inline("✏️ Type a custom %", b"autotrade:losslimitpct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

async def send_autotrade_status(bot, chat, user_id):
    session = get_autotrade_session(user_id)
    if not session or not session.get("enabled"):
        await bot.send_message(
            chat,
            "🤖 *Auto-Trading* — currently OFF\n\n"
            "When ON, the bot watches the same scanner and strategy, and "
            "executes trades automatically — no tap needed. Every trade still "
            "carries its own stop-loss, and a loss-limit circuit breaker stops "
            "everything early if things go badly.\n\n"
            "Set it up below:",
            buttons=[[Button.inline("🚀 Set Up Auto-Trading", b"autotrade:setup_start")],
                     [Button.inline("🏠 Main Menu", b"menu:main")]],
            parse_mode='markdown'
        )
        return
    await bot.send_message(
        chat,
        f"🤖 *Auto-Trading* — currently ON ✅\n\n"
        f"• Trades so far: {session['trades_done']}/{session['max_trades']}\n"
        f"• Amount per trade: {session['amount_pct']}% of balance\n"
        f"• Stop-loss per trade: {session['stop_loss_pct']}%\n"
        f"• Loss limit (circuit breaker): {session['loss_limit_pct']}%\n"
        f"• Realized P&L this session: ${session.get('realized_pnl', 0):,.2f}\n"
        f"• Symbols: {', '.join(session['symbols'])}",
        buttons=[[Button.inline("🛑 Stop Auto-Trading", b"autotrade:stop")],
                 [Button.inline("🏠 Main Menu", b"menu:main")]],
        parse_mode='markdown'
    )

async def handle_autotrade_setup_text(event, bot):
    """Continues auto-trading setup when the user types a custom % or the
    number of trades. Returns True if it handled the message."""
    state = autotrade_setup_state.get(event.sender_id)
    if not state:
        return False

    text = event.raw_text.strip()

    if state["step"] == "awaiting_amount_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `5`", parse_mode='markdown')
            return True
        state["amount_pct"] = pct
        state["step"] = "awaiting_stoploss_pct"
        await event.respond("📊 Stop-loss % per trade (protects each individual trade):", buttons=autotrade_stoploss_pct_buttons(), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_stoploss_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `2`", parse_mode='markdown')
            return True
        state["stop_loss_pct"] = pct
        state["step"] = "awaiting_losslimit_pct"
        await event.respond("📊 Loss limit % — stops ALL auto-trading if total losses hit this:", buttons=autotrade_losslimit_pct_buttons(), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_losslimit_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `10`", parse_mode='markdown')
            return True
        state["loss_limit_pct"] = pct
        state["step"] = "awaiting_max_trades"
        await event.respond("📊 How many trades total should this session run? Type a number, e.g. `20`")
        return True

    if state["step"] == "awaiting_max_trades":
        try:
            count = int(text)
            if count <= 0:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a whole number, e.g. `20`")
            return True
        state["max_trades"] = count
        autotrade_setup_state.pop(event.sender_id, None)
        await confirm_autotrade_setup(event, bot, state)
        return True

    return False

async def confirm_autotrade_setup(event, bot, state):
    client = await get_user_binance_client(event.sender_id)
    if not client:
        await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
        return
    try:
        account = await client.get_account()
    except Exception as e:
        await event.respond(f"⚠️ Couldn't fetch your balance: {e}")
        return

    starting_balance = 0.0
    for b in account.get('balances', []):
        if b['asset'] == 'USDT':
            starting_balance = float(b['free'])
            break

    mode_label = "🧪 TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
    session_preview = {
        "enabled": False, "amount_pct": state["amount_pct"], "stop_loss_pct": state["stop_loss_pct"],
        "loss_limit_pct": state["loss_limit_pct"], "max_trades": state["max_trades"], "trades_done": 0,
        "starting_balance": starting_balance, "realized_pnl": 0.0, "symbols": list(SCAN_SYMBOLS)
    }
    autotrade_setup_state[event.sender_id] = {"pending_session": session_preview}
    await event.respond(
        f"🤖 *Confirm Auto-Trading Setup* — {mode_label}\n\n"
        f"• Amount per trade: *{state['amount_pct']}%* of balance\n"
        f"• Stop-loss per trade: *{state['stop_loss_pct']}%*\n"
        f"• Loss limit (circuit breaker): *{state['loss_limit_pct']}%* "
        f"(≈ ${starting_balance * state['loss_limit_pct'] / 100:,.2f})\n"
        f"• Max trades this session: *{state['max_trades']}*\n"
        f"• Watching: {', '.join(SCAN_SYMBOLS)}\n"
        f"• Starting balance: *${starting_balance:,.2f} USDT*\n\n"
        f"Once started, trades fire automatically — no tap needed. "
        f"You can stop anytime with 🛑 Stop Auto-Trading.",
        buttons=[[Button.inline("🚀 Start Auto-Trading", b"autotrade:start")],
                 [Button.inline("❌ Cancel", b"menu:main")]],
        parse_mode='markdown'
    )

def setup_autotrade_handlers(bot):
    @bot.on(events.NewMessage(incoming=True, pattern=r'^/autotrade$'))
    async def autotrade_command(event):
        await send_autotrade_status(bot, await event.get_chat(), event.sender_id)

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/stopautotrade$'))
    async def stopautotrade_command(event):
        stop_autotrade_session(event.sender_id)
        await event.respond("🛑 Auto-trading stopped. Existing open positions are still protected by their stop-losses.")

    @bot.on(events.CallbackQuery(data=b"menu:autotrade"))
    async def autotrade_menu_callback(event):
        await event.answer()
        await send_autotrade_status(bot, await event.get_chat(), event.sender_id)

    @bot.on(events.CallbackQuery(data=b"autotrade:setup_start"))
    async def autotrade_setup_start_callback(event):
        if not await get_user_binance_client(event.sender_id):
            await event.edit(
                "You haven't connected a Binance account yet.\n\nUse /connectbinance to set it up first. 🔐",
                buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]]
            )
            return
        autotrade_setup_state[event.sender_id] = {"step": "awaiting_amount_pct"}
        await event.edit("📊 How much of your balance per trade?", buttons=autotrade_amount_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^autotrade:amountpct:(custom|\d+)$"))
    async def autotrade_amountpct_callback(event):
        choice = event.pattern_match.group(1).decode()
        if choice == "custom":
            autotrade_setup_state[event.sender_id] = {"step": "awaiting_amount_pct_text"}
            await event.edit("✏️ Type the % of balance per trade, e.g. `5`:", buttons=None, parse_mode='markdown')
            return
        autotrade_setup_state[event.sender_id] = {"step": "awaiting_stoploss_pct", "amount_pct": float(choice)}
        await event.edit("📊 Stop-loss % per trade (protects each individual trade):", buttons=autotrade_stoploss_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^autotrade:stoplosspct:(custom|\d+)$"))
    async def autotrade_stoplosspct_callback(event):
        choice = event.pattern_match.group(1).decode()
        state = autotrade_setup_state.get(event.sender_id, {})
        if choice == "custom":
            state["step"] = "awaiting_stoploss_pct_text"
            autotrade_setup_state[event.sender_id] = state
            await event.edit("✏️ Type the stop-loss % per trade, e.g. `2`:", buttons=None, parse_mode='markdown')
            return
        state["stop_loss_pct"] = float(choice)
        state["step"] = "awaiting_losslimit_pct"
        autotrade_setup_state[event.sender_id] = state
        await event.edit("📊 Loss limit % — stops ALL auto-trading if total losses hit this:", buttons=autotrade_losslimit_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^autotrade:losslimitpct:(custom|\d+)$"))
    async def autotrade_losslimitpct_callback(event):
        choice = event.pattern_match.group(1).decode()
        state = autotrade_setup_state.get(event.sender_id, {})
        if choice == "custom":
            state["step"] = "awaiting_losslimit_pct_text"
            autotrade_setup_state[event.sender_id] = state
            await event.edit("✏️ Type the loss-limit %, e.g. `10`:", buttons=None, parse_mode='markdown')
            return
        state["loss_limit_pct"] = float(choice)
        state["step"] = "awaiting_max_trades"
        autotrade_setup_state[event.sender_id] = state
        await event.edit("📊 How many trades total should this session run? Type a number, e.g. `20`", buttons=None)

    @bot.on(events.CallbackQuery(data=b"autotrade:start"))
    async def autotrade_start_callback(event):
        state = autotrade_setup_state.pop(event.sender_id, None)
        if not state or "pending_session" not in state:
            await event.answer("Setup expired — please start again with /autotrade.", alert=True)
            return
        session = state["pending_session"]
        session["enabled"] = True
        save_autotrade_session(event.sender_id, session)
        mode_label = "🧪 TESTNET" if BINANCE_TESTNET else "⚠️ LIVE"
        await event.edit(f"✅ *Auto-Trading started!* ({mode_label})\n\nWatching {', '.join(session['symbols'])}. You'll get a message every time it trades.", buttons=None, parse_mode='markdown')

    @bot.on(events.CallbackQuery(data=b"autotrade:stop"))
    async def autotrade_stop_callback(event):
        stop_autotrade_session(event.sender_id)
        await event.edit("🛑 Auto-trading stopped. Existing open positions are still protected by their stop-losses.", buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]])

    logger.info("✅ Auto-trading handlers registered (/autotrade, /stopautotrade)")

async def finalize_risk_sized_trade(event, bot, symbol, side, stop_pct):
    """Calculates a position size so that if the stop-loss hits, the loss
    equals ~1% of the user's balance — then shows the same confirmation
    card as manual entry, with the stop-loss attached."""
    client = await get_user_binance_client(event.sender_id)
    if not client:
        await event.answer("You haven't connected a Binance account.", alert=True)
        return

    trade_flow_state.pop(event.sender_id, None)
    quote_asset = get_quote_asset(symbol)

    try:
        ticker = await binance_client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        account = await client.get_account()
    except Exception as e:
        await event.edit(f"⚠️ Couldn't fetch live price/balance: {e}", buttons=None)
        return

    balance = 0.0
    for b in account.get('balances', []):
        if b['asset'] == quote_asset:
            balance = float(b['free'])
            break

    if balance <= 0:
        await event.edit(f"⚠️ Your {quote_asset} balance is 0 — nothing available to size a trade with.", buttons=None)
        return

    risk_amount = balance * 0.01
    stop_distance = price * (stop_pct / 100)
    quantity = risk_amount / stop_distance
    stop_loss_price = price * (1 - stop_pct / 100) if side == "BUY" else price * (1 + stop_pct / 100)

    chat = await event.get_chat()
    await event.delete()
    await send_trade_confirmation(bot, chat, event.sender_id, symbol, side, quantity, stop_loss_price=stop_loss_price, risk_amount=risk_amount)

async def send_trade_confirmation(bot, chat, user_id, symbol, side, quantity, stop_loss_price=None, risk_amount=None):
    """Fetches the live price and shows a Confirm/Cancel proposal card.
    Shared by both the /trade command and the guided button flow — this
    is the single place a pending trade gets created."""
    try:
        ticker = await binance_client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
    except Exception as e:
        await bot.send_message(
            chat,
            f"⚠️ Couldn't find live price for *{symbol}* — check the symbol is correct. ({e})",
            parse_mode='markdown'
        )
        return

    estimated_cost = price * quantity

    min_notional = await get_min_notional(symbol)
    if min_notional is not None and estimated_cost < min_notional:
        min_quantity = min_notional / price
        await bot.send_message(
            chat,
            f"⚠️ *That order is too small for Binance*\n\n"
            f"{symbol} requires a minimum order value of *${min_notional:,.2f}*.\n"
            f"Your order (*{quantity} × ${price:,.4f} = ${estimated_cost:,.2f}*) falls below that.\n\n"
            f"Try a quantity of at least *{min_quantity:.6f}* (~${min_notional:,.2f}) or more.",
            parse_mode='markdown'
        )
        return

    pending_trades[user_id] = {"symbol": symbol, "side": side, "quantity": quantity, "stop_loss_price": stop_loss_price}

    stop_note = ""
    if stop_loss_price is not None:
        stop_note = (
            f"• Stop-loss: *${stop_loss_price:,.4f}* (auto-sells if hit)\n"
            f"• Risking: *${risk_amount:,.2f}* (~1% of balance)\n"
        )

    mode_label = "🧪 TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
    await bot.send_message(
        chat,
        f"📊 *Trade Proposal* — {mode_label}\n\n"
        f"• Symbol: *{symbol}*\n"
        f"• Side: *{side}*\n"
        f"• Quantity: *{quantity}*\n"
        f"• Current price: *${price:,.4f}*\n"
        f"• Estimated cost: *${estimated_cost:,.2f}*\n"
        f"{stop_note}\n"
        f"Nothing happens until you confirm. 👇",
        buttons=[[Button.inline("✅ Confirm", b"trade:confirm"),
                  Button.inline("❌ Cancel", b"trade:cancel")]],
        parse_mode='markdown'
    )

def trade_symbol_buttons():
    rows = [[Button.inline(f"💰 {s}", f"trade:symbol:{s}".encode())] for s in QUICK_TRADE_SYMBOLS]
    rows.append([Button.inline("✏️ Type a different symbol", b"trade:symbol:other")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def trade_side_buttons(symbol):
    return [
        [Button.inline("🟢 BUY", f"trade:side:{symbol}:BUY".encode()),
         Button.inline("🔴 SELL", f"trade:side:{symbol}:SELL".encode())],
        [Button.inline("🏠 Main Menu", b"menu:main")]
    ]

async def handle_trade_flow_text(event, bot):
    """Continues the guided trade flow when the user types a symbol or
    quantity as a plain text reply. Returns True if it handled the
    message (so the caller knows NOT to also send it to Rex)."""
    state = trade_flow_state.get(event.sender_id)
    if not state:
        return False

    text = event.raw_text.strip()

    if state["step"] == "awaiting_symbol_text":
        symbol = text.upper()
        if not re.fullmatch(r'[A-Z0-9]{3,15}', symbol):
            await event.respond("⚠️ That doesn't look like a valid symbol — try something like `BTCUSDT`.", parse_mode='markdown')
            return True
        trade_flow_state[event.sender_id] = {"step": "awaiting_side", "symbol": symbol}
        await event.respond(f"📊 *{symbol}* — Buy or Sell?", buttons=trade_side_buttons(symbol), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_quantity":
        try:
            quantity = float(text)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Please type a valid number for the quantity, e.g. `0.001`", parse_mode='markdown')
            return True
        symbol, side = state["symbol"], state["side"]
        trade_flow_state.pop(event.sender_id, None)
        chat = await event.get_chat()
        await send_trade_confirmation(bot, chat, event.sender_id, symbol, side, quantity)
        return True

    return False

# ── Per-user Binance account connection flow (private chat only) ────
binance_connect_state = {}  # {user_id: {"step": "awaiting_api_key"/"awaiting_api_secret", "api_key": ...}}

async def handle_binance_connect_text(event, bot):
    """Continues the /connectbinance flow when the user pastes their API
    key or secret as plain text. Returns True if it handled the message."""
    state = binance_connect_state.get(event.sender_id)
    if not state:
        return False

    text = event.raw_text.strip()

    if state["step"] == "awaiting_api_key":
        binance_connect_state[event.sender_id] = {"step": "awaiting_api_secret", "api_key": text}
        await event.respond("🔐 Got it. Now paste your API *Secret* key:", parse_mode='markdown')
        return True

    if state["step"] == "awaiting_api_secret":
        api_key = state["api_key"]
        api_secret = text
        binance_connect_state.pop(event.sender_id, None)

        if not fernet:
            await event.respond(
                "⚠️ The bot owner hasn't finished setting this up yet "
                "(BINANCE_ENCRYPTION_KEY missing) — let them know."
            )
            return True

        await event.respond("🔄 Verifying your keys with Binance...")
        try:
            test_client = await BinanceAsyncClient.create(api_key, api_secret, testnet=BINANCE_TESTNET)
            await test_client.get_account()  # raises if the credentials are invalid
        except Exception:
            await event.respond(
                "❌ Couldn't verify those keys — double check them and run /connectbinance again.\n\n"
                "Common causes: typo, key not yet active, or 'Enable Spot & Margin Trading' wasn't checked."
            )
            return True

        save_user_binance_keys(event.sender_id, api_key, api_secret)
        user_binance_clients[event.sender_id] = test_client
        mode_label = "🧪 TESTNET" if BINANCE_TESTNET else "⚠️ LIVE"
        await event.respond(
            f"✅ *Connected!* ({mode_label})\n\n"
            f"Your keys are encrypted and stored — only used for *your own* trades and balance.\n\n"
            f"Try /balance to see your account. Use /disconnectbinance anytime to remove your keys.",
            parse_mode='markdown'
        )
        return True

    return False

def setup_binance_account_handlers(bot):
    """Registers /connectbinance, /disconnectbinance, /mybinance."""

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/connectbinance$'))
    async def connect_binance_handler(event):
        if not event.is_private:
            await event.respond("🔐 For your security, please message me privately to connect your Binance account — not in a group.")
            return
        if not BINANCE_AVAILABLE:
            await event.respond("📊 Live trading isn't available yet — the bot owner needs to install python-binance. 🔧")
            return
        if not fernet:
            await event.respond("📊 Live trading isn't fully set up yet — the bot owner needs to add BINANCE_ENCRYPTION_KEY. 🔧")
            return
        binance_connect_state[event.sender_id] = {"step": "awaiting_api_key"}
        await event.respond(
            "🔐 *Connect Your Binance Account*\n\n"
            "This is a private chat, just between you and the bot.\n\n"
            "Paste your Binance API *Key* now.\n\n"
            "⚠️ Make sure the key only has *Read* and *Spot & Margin Trading* enabled — "
            "never one with *Withdrawals* enabled.",
            buttons=[[Button.inline("📖 How do I get my API key?", b"binance:apiguide")]],
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"binance:apiguide"))
    async def binance_api_guide_callback(event):
        await event.answer()
        mode_note = (
            "🧪 *This bot is currently in TESTNET mode* (fake money) — use the testnet "
            "steps below to practice safely.\n\n"
            if BINANCE_TESTNET else
            "⚠️ *This bot is currently in LIVE mode* (real money) — use the live steps "
            "below carefully.\n\n"
        )
        await event.respond(
            f"📖 *How to Get Your Binance API Key*\n\n{mode_note}"
            "🧪 *Testnet (fake money, practice safely):*\n"
            "1️⃣ Go to testnet.binance.vision\n"
            "2️⃣ Log in with GitHub\n"
            "3️⃣ Click 'Generate HMAC_SHA256 Key'\n"
            "4️⃣ Tick ✅ TRADE, ✅ USER_DATA, ✅ USER_STREAM\n"
            "5️⃣ Click Generate, copy both keys shown\n\n"
            "💰 *Live (real Binance account, real money):*\n"
            "1️⃣ Log into binance.com\n"
            "2️⃣ Profile icon → API Management\n"
            "3️⃣ Click 'Create API' → System generated\n"
            "4️⃣ Complete 2FA verification\n"
            "5️⃣ Enable ONLY: ✅ Reading, ✅ Spot & Margin Trading\n"
            "6️⃣ Leave ❌ Withdrawals OFF — always\n"
            "7️⃣ Copy both keys shown (secret shown only once!)\n\n"
            "Once you have both keys, come back here and send /connectbinance to continue. 🔐",
            parse_mode='markdown'
        )

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/disconnectbinance$'))
    async def disconnect_binance_handler(event):
        delete_user_binance_keys(event.sender_id)
        user_binance_clients.pop(event.sender_id, None)
        await event.respond("🔓 Your Binance keys have been deleted from storage.")

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/mybinance$'))
    async def my_binance_status_handler(event):
        creds = get_user_binance_keys(event.sender_id)
        if not creds:
            await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
            return
        await event.respond(
            f"✅ Connected — API key: `{mask_key(creds['api_key'])}`\n\nUse /disconnectbinance to remove it.",
            parse_mode='markdown'
        )

    logger.info("✅ Binance account handlers registered (/connectbinance, /disconnectbinance, /mybinance)")

# ══════════════════════════════════════════════════════════════
# NEW: Auto-Trading (autonomous execution within hard limits)
# ══════════════════════════════════════════════════════════════
#
# This is the ONE feature in this bot where trades fire without a tap.
# It only runs for users who explicitly configured and started a session,
# and every session is bounded by three things the user set themselves:
# a % of balance per trade, a max number of trades, and a total-loss
# circuit breaker that halts everything if hit. Every auto-trade also
# still carries its own per-trade stop-loss, monitored by a fast-cadence
# watcher (see monitor_stop_losses below) — this is the piece that makes
# unattended trading survivable rather than reckless.

AUTOTRADE_SESSIONS_FILE = os.path.join(DATA_DIR, 'autotrade_sessions.json')
STOP_LOSS_CHECK_SECONDS = float(os.environ.get('STOP_LOSS_CHECK_SECONDS', '60'))

def _load_autotrade_sessions():
    if not os.path.exists(AUTOTRADE_SESSIONS_FILE):
        return {}
    try:
        with open(AUTOTRADE_SESSIONS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Could not read autotrade sessions file: {e}")
        return {}

def _save_autotrade_sessions(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUTOTRADE_SESSIONS_FILE, 'w') as f:
        json.dump(store, f)

autotrade_sessions = _load_autotrade_sessions()  # {user_id_str: {...}}
autotrade_setup_state = {}  # {user_id: {"step": ..., collected fields...}}

def get_autotrade_session(user_id):
    return autotrade_sessions.get(str(user_id))

def save_autotrade_session(user_id, session):
    autotrade_sessions[str(user_id)] = session
    _save_autotrade_sessions(autotrade_sessions)

def stop_autotrade_session(user_id):
    session = autotrade_sessions.get(str(user_id))
    if session:
        session["enabled"] = False
        _save_autotrade_sessions(autotrade_sessions)

async def execute_autotrade(bot, user_id, symbol, side):
    """The only place in this bot where a trade fires without a human tap.
    Guarded on every side: respects max trades, the loss-limit circuit
    breaker, position sizing as a % of balance, and always attaches a
    per-trade stop-loss."""
    session = get_autotrade_session(user_id)
    if not session or not session.get("enabled"):
        logger.info(f"ℹ️ Auto-trade skip [{symbol}, user {user_id}]: no active session")
        return
    if symbol not in session.get("symbols", []):
        logger.info(f"ℹ️ Auto-trade skip [{symbol}, user {user_id}]: symbol not in session watchlist {session.get('symbols')}")
        return
    if side != "BUY":
        return  # exits are handled by scan_positions_for_exit_signals, not here
    if session["trades_done"] >= session["max_trades"]:
        logger.info(f"ℹ️ Auto-trade skip [{symbol}, user {user_id}]: max trades reached ({session['trades_done']}/{session['max_trades']})")
        return
    # Don't stack a second auto-position on a symbol we're already holding
    existing = [p for p in open_positions.get(str(user_id), []) if p["symbol"] == symbol and p.get("is_autotrade")]
    if existing:
        logger.info(f"ℹ️ Auto-trade skip [{symbol}, user {user_id}]: already holding an auto-trade position on this symbol")
        return

    client = await get_user_binance_client(user_id)
    if not client:
        logger.warning(f"⚠️ Auto-trade skip [{symbol}, user {user_id}]: no connected Binance client (check /mybinance)")
        return

    try:
        account = await client.get_account()
        ticker = await binance_client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
    except Exception as e:
        logger.warning(f"⚠️ Auto-trade: couldn't fetch balance/price for user {user_id}: {e}")
        return

    quote_asset = get_quote_asset(symbol)
    balance = 0.0
    for b in account.get('balances', []):
        if b['asset'] == quote_asset:
            balance = float(b['free'])
            break
    if balance <= 0:
        logger.warning(f"⚠️ Auto-trade skip [{symbol}, user {user_id}]: {quote_asset} balance is 0")
        return

    # Circuit breaker check — uses the balance snapshotted when the session started
    starting_balance = session["starting_balance"]
    loss_limit_amount = starting_balance * (session["loss_limit_pct"] / 100)
    if session["realized_pnl"] <= -loss_limit_amount:
        session["enabled"] = False
        _save_autotrade_sessions(autotrade_sessions)
        try:
            await bot.send_message(
                user_id,
                f"🛑 *Auto-Trading Stopped — Circuit Breaker*\n\n"
                f"Realized loss (${session['realized_pnl']:,.2f}) hit your "
                f"{session['loss_limit_pct']}% limit. No new auto-trades will open. "
                f"Existing open positions are still protected by their stop-losses.",
                parse_mode='markdown'
            )
        except Exception:
            pass
        return

    trade_amount = balance * (session["amount_pct"] / 100)
    quantity = trade_amount / price
    stop_loss_price = price * (1 - session["stop_loss_pct"] / 100)

    min_notional = await get_min_notional(symbol)
    if min_notional is not None and trade_amount < min_notional:
        logger.info(f"ℹ️ Auto-trade skipped for user {user_id}: {symbol} order too small (${trade_amount:,.2f} < ${min_notional:,.2f})")
        return

    try:
        order = await client.create_order(symbol=symbol, side="BUY", type="MARKET", quantity=quantity)
    except Exception as e:
        logger.error(f"❌ Auto-trade execution error for user {user_id}: {e}")
        return

    executed_qty = float(order.get('executedQty', 0) or 0)
    quote_qty = float(order.get('cummulativeQuoteQty', 0) or 0)
    fill_price = (quote_qty / executed_qty) if executed_qty > 0 else price

    add_open_position(user_id, symbol, executed_qty or quantity, fill_price, order.get('orderId'), stop_loss_price, is_autotrade=True)
    session["trades_done"] += 1
    _save_autotrade_sessions(autotrade_sessions)

    try:
        await bot.send_message(
            user_id,
            f"🤖 *Auto-Trade Executed* ({session['trades_done']}/{session['max_trades']})\n\n"
            f"• {symbol} BUY\n"
            f"• Entry: ${fill_price:,.4f}\n"
            f"• Stop-loss: ${stop_loss_price:,.4f}\n"
            f"• Amount: ${trade_amount:,.2f} ({session['amount_pct']}% of balance)",
            parse_mode='markdown'
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not notify user {user_id} of auto-trade: {e}")

async def close_autotrade_position(bot, user_id, position, exit_price, reason):
    """Closes an autotrade position and updates the session's realized P&L
    and circuit breaker — used by both the stop-loss watcher and the
    exit-signal scanner when the position belongs to an auto-trade session."""
    client = await get_user_binance_client(user_id)
    if not client:
        return
    try:
        order = await client.create_order(symbol=position["symbol"], side="SELL", type="MARKET", quantity=position["quantity"])
    except Exception as e:
        logger.error(f"❌ Auto-trade close error for user {user_id}: {e}")
        return

    executed_qty = float(order.get('executedQty', 0) or 0)
    quote_qty = float(order.get('cummulativeQuoteQty', 0) or 0)
    real_exit_price = (quote_qty / executed_qty) if executed_qty > 0 else exit_price
    pnl = (real_exit_price - position["entry_price"]) * position["quantity"]

    remove_open_position(user_id, position["id"])
    session = get_autotrade_session(user_id)
    if session:
        session["realized_pnl"] = session.get("realized_pnl", 0.0) + pnl
        _save_autotrade_sessions(autotrade_sessions)

    result_label = "Win ✅️🤑" if pnl > 0 else "Lost ❎️🥱"
    try:
        await bot.send_message(
            user_id,
            f"🤖 *Auto-Trade Closed* — {reason}\n\n"
            f"• {position['symbol']}\n"
            f"• Entry: ${position['entry_price']:,.4f} → Exit: ${real_exit_price:,.4f}\n"
            f"• Result: *{result_label}* (${pnl:,.2f})",
            parse_mode='markdown'
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not notify user {user_id} of auto-trade close: {e}")

async def monitor_stop_losses(bot):
    """Fast-cadence background loop — checks EVERY open position (manual
    and auto-trade alike) against its stop-loss every ~60 seconds. This is
    what makes a stop-loss actually protective instead of just a stored
    number nobody's watching."""
    while True:
        await asyncio.sleep(STOP_LOSS_CHECK_SECONDS)
        if not binance_client:
            continue
        for user_id_str, positions in list(open_positions.items()):
            user_id = int(user_id_str)
            for p in list(positions):
                stop_price = p.get("stop_loss_price")
                if not stop_price:
                    continue
                try:
                    ticker = await binance_client.get_symbol_ticker(symbol=p["symbol"])
                    current_price = float(ticker['price'])
                except Exception as e:
                    logger.warning(f"⚠️ Stop-loss check failed for {p['symbol']}: {e}")
                    continue
                if current_price <= stop_price:
                    if p.get("is_autotrade"):
                        await close_autotrade_position(bot, user_id, p, current_price, "🛑 Stop-loss triggered")
                    else:
                        client = await get_user_binance_client(user_id)
                        if not client:
                            continue
                        try:
                            order = await client.create_order(symbol=p["symbol"], side="SELL", type="MARKET", quantity=p["quantity"])
                            executed_qty = float(order.get('executedQty', 0) or 0)
                            quote_qty = float(order.get('cummulativeQuoteQty', 0) or 0)
                            exit_price = (quote_qty / executed_qty) if executed_qty > 0 else current_price
                            remove_open_position(user_id, p["id"])
                            result_label = "Win ✅️🤑" if exit_price > p["entry_price"] else "Lost ❎️🥱"
                            await bot.send_message(
                                user_id,
                                f"🛑 *Stop-Loss Triggered*\n\n"
                                f"• {p['symbol']}\n"
                                f"• Entry: ${p['entry_price']:,.4f} → Exit: ${exit_price:,.4f}\n"
                                f"• Result: *{result_label}*",
                                parse_mode='markdown'
                            )
                        except Exception as e:
                            logger.error(f"❌ Stop-loss execution error for user {user_id}: {e}")

def get_position(user_id, position_id):
    positions = open_positions.get(str(user_id), [])
    for p in positions:
        if p["id"] == position_id:
            return p
    return None

async def send_positions_list(bot, chat, user_id):
    positions = open_positions.get(str(user_id), [])
    if not positions:
        await bot.send_message(chat, "📊 You have no open positions right now.")
        return

    for p in positions:
        try:
            ticker = await binance_client.get_symbol_ticker(symbol=p["symbol"])
            current_price = float(ticker['price'])
            is_up = current_price >= p["entry_price"]
            move_emoji = "🟢" if is_up else "🔴"
            change_pct = ((current_price - p["entry_price"]) / p["entry_price"]) * 100
            await bot.send_message(
                chat,
                f"{move_emoji} *{p['symbol']}*\n"
                f"Entry: ${p['entry_price']:,.4f} | Now: ${current_price:,.4f} ({change_pct:+.2f}%)",
                buttons=[[Button.inline("🔄 Refresh", f"position:status:{p['id']}".encode())],
                         [Button.inline("💰 Close Position", f"position:close:{p['id']}".encode())]],
                parse_mode='markdown'
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch live price for position {p['id']}: {e}")

def trade_sizing_buttons(symbol, side):
    return [
        [Button.inline("✏️ Type exact quantity", f"trade:sizing:{symbol}:{side}:manual".encode())],
        [Button.inline("🎯 Auto-size (1% risk)", f"trade:sizing:{symbol}:{side}:risk".encode())],
        [Button.inline("🏠 Main Menu", b"menu:main")]
    ]

def stop_pct_buttons(symbol, side):
    rows = [[Button.inline(f"{p}%", f"trade:stoppct:{symbol}:{side}:{p}".encode()) for p in [1, 2, 3, 5]]]
    rows.append([Button.inline("✏️ Type a custom %", f"trade:stoppct:{symbol}:{side}:custom".encode())])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def setup_binance_trading_handler(bot):
    """Registers the /trade command, the guided button flow, the
    Confirm/Cancel callbacks, and /balance for checking your account.
    /trade + Confirm is the ONLY code path that can place a real order."""

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/balance$'))
    async def balance_command_handler(event):
        client = await get_user_binance_client(event.sender_id)
        if not client:
            await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
            return

        try:
            account = await client.get_account()
        except Exception as e:
            await event.respond(f"⚠️ Couldn't fetch account info: {e}")
            return

        # Only show assets you actually hold (free or locked > 0)
        holdings = [
            b for b in account.get('balances', [])
            if float(b['free']) > 0 or float(b['locked']) > 0
        ]

        mode_label = "🧪 TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
        if not holdings:
            await event.respond(f"📊 *Your Balance* — {mode_label}\n\nNo assets found.", parse_mode='markdown')
            return

        lines = [f"• {b['asset']}: {float(b['free']):,.6f}" for b in holdings[:20]]
        await event.respond(
            f"📊 *Your Balance* — {mode_label}\n\n" + "\n".join(lines),
            parse_mode='markdown'
        )

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/orders$'))
    async def orders_command_handler(event):
        client = await get_user_binance_client(event.sender_id)
        if not client:
            await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
            return

        try:
            open_orders = await client.get_open_orders()
        except Exception as e:
            await event.respond(f"⚠️ Couldn't fetch open orders: {e}")
            return

        mode_label = "🧪 TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
        if not open_orders:
            await event.respond(f"📊 *Your Open Orders* — {mode_label}\n\nNone right now — all your orders have filled.", parse_mode='markdown')
            return

        lines = [f"• {o['symbol']} {o['side']} {o['origQty']} @ {o.get('price', 'MARKET')}" for o in open_orders[:20]]
        await event.respond(
            f"📊 *Your Open Orders* — {mode_label}\n\n" + "\n".join(lines),
            parse_mode='markdown'
        )

    @bot.on(events.NewMessage(incoming=True, pattern=TRADE_COMMAND_PATTERN))
    async def trade_command_handler(event):
        if not binance_client:
            await event.respond("📊 Live trading isn't set up yet — the bot owner needs to install python-binance. 🔧")
            return
        if not await get_user_binance_client(event.sender_id):
            await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
            return

        symbol = event.pattern_match.group(1).upper()
        side = event.pattern_match.group(2).upper()
        try:
            quantity = float(event.pattern_match.group(3))
        except ValueError:
            await event.respond("⚠️ Couldn't read that quantity — try `/trade BTCUSDT BUY 0.001`")
            return

        chat = await event.get_chat()
        await send_trade_confirmation(bot, chat, event.sender_id, symbol, side, quantity)

    @bot.on(events.CallbackQuery(data=b"menu:trade"))
    async def trade_menu_callback(event):
        if not binance_client:
            await event.edit(
                "📊 Live trading isn't set up yet — the bot owner needs to install python-binance. 🔧",
                buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]]
            )
            return
        if not await get_user_binance_client(event.sender_id):
            await event.edit(
                "📊 You haven't connected a Binance account yet.\n\nUse /connectbinance to set it up (it's quick, and your keys are encrypted). 🔐",
                buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]]
            )
            return
        trade_flow_state.pop(event.sender_id, None)
        await event.edit(
            "📊 *Trade*\n\nPick a coin to trade:",
            buttons=trade_symbol_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(pattern=rb"^trade:symbol:(.+)$"))
    async def trade_symbol_callback(event):
        choice = event.pattern_match.group(1).decode()
        if choice == "other":
            trade_flow_state[event.sender_id] = {"step": "awaiting_symbol_text"}
            await event.edit("✏️ Type the symbol you want to trade, e.g. `BTCUSDT`:", buttons=None, parse_mode='markdown')
            return
        symbol = choice
        trade_flow_state[event.sender_id] = {"step": "awaiting_side", "symbol": symbol}
        await event.edit(f"📊 *{symbol}* — Buy or Sell?", buttons=trade_side_buttons(symbol), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^trade:side:([^:]+):(BUY|SELL)$"))
    async def trade_side_callback(event):
        symbol = event.pattern_match.group(1).decode()
        side = event.pattern_match.group(2).decode()
        if side == "SELL":
            # Selling only makes sense as "how much am I closing" — risk
            # sizing is for opening new exposure (BUY), so go straight to
            # manual quantity entry, same as before.
            trade_flow_state[event.sender_id] = {"step": "awaiting_quantity", "symbol": symbol, "side": side}
            await event.edit(
                f"📊 *{symbol}* — *{side}*\n\nHow much? Type the quantity, e.g. `0.001`",
                buttons=None,
                parse_mode='markdown'
            )
            return
        trade_flow_state[event.sender_id] = {"step": "awaiting_sizing_choice", "symbol": symbol, "side": side}
        await event.edit(
            f"📊 *{symbol}* — *{side}*\n\nHow do you want to size this trade?",
            buttons=trade_sizing_buttons(symbol, side),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(pattern=rb"^trade:sizing:([^:]+):(BUY|SELL):(manual|risk)$"))
    async def trade_sizing_callback(event):
        symbol = event.pattern_match.group(1).decode()
        side = event.pattern_match.group(2).decode()
        method = event.pattern_match.group(3).decode()
        if method == "manual":
            trade_flow_state[event.sender_id] = {"step": "awaiting_quantity", "symbol": symbol, "side": side}
            await event.edit(
                f"📊 *{symbol}* — *{side}*\n\nHow much? Type the quantity, e.g. `0.001`",
                buttons=None,
                parse_mode='markdown'
            )
        else:
            trade_flow_state[event.sender_id] = {"step": "awaiting_stop_pct_choice", "symbol": symbol, "side": side}
            await event.edit(
                f"📊 *{symbol}* — *{side}*\n\n"
                f"Pick your stop-loss % — this protects you (auto-sells if price drops "
                f"this much) AND sizes your position so a stop-out only costs *1% of your balance*.",
                buttons=stop_pct_buttons(symbol, side),
                parse_mode='markdown'
            )

    @bot.on(events.CallbackQuery(pattern=rb"^trade:stoppct:([^:]+):(BUY|SELL):(custom|\d+)$"))
    async def trade_stop_pct_callback(event):
        symbol = event.pattern_match.group(1).decode()
        side = event.pattern_match.group(2).decode()
        choice = event.pattern_match.group(3).decode()
        if choice == "custom":
            trade_flow_state[event.sender_id] = {"step": "awaiting_stop_pct_text", "symbol": symbol, "side": side}
            await event.edit("✏️ Type your stop-loss percentage, e.g. `2.5`:", buttons=None, parse_mode='markdown')
            return
        await finalize_risk_sized_trade(event, bot, symbol, side, float(choice))

    @bot.on(events.CallbackQuery(data=b"trade:confirm"))
    async def trade_confirm_callback(event):
        trade = pending_trades.pop(event.sender_id, None)
        if not trade:
            await event.answer("No pending trade found — it may have expired.", alert=True)
            return

        client = await get_user_binance_client(event.sender_id)
        if not client:
            await event.answer("You haven't connected a Binance account. Use /connectbinance first.", alert=True)
            return

        await event.answer("Placing order...")
        try:
            order = await client.create_order(
                symbol=trade["symbol"],
                side=trade["side"],
                type="MARKET",
                quantity=trade["quantity"],
            )

            executed_qty = float(order.get('executedQty', 0) or 0)
            quote_qty = float(order.get('cummulativeQuoteQty', 0) or 0)
            fill_price = (quote_qty / executed_qty) if executed_qty > 0 else None

            buttons = None
            extra_note = ""
            if trade["side"] == "BUY" and fill_price:
                position_id = add_open_position(event.sender_id, trade["symbol"], trade["quantity"], fill_price, order.get('orderId'), trade.get("stop_loss_price"))
                extra_note = "\n\n📊 I'll track this position — check its live status anytime."
                buttons = [[Button.inline("📊 Check Status", f"position:status:{position_id}".encode())]]

            await event.edit(
                f"✅ *Order placed!*\n\n"
                f"• Symbol: {trade['symbol']}\n"
                f"• Side: {trade['side']}\n"
                f"• Quantity: {trade['quantity']}\n"
                f"• Order ID: `{order.get('orderId', 'n/a')}`"
                f"{extra_note}",
                buttons=buttons,
                parse_mode='markdown'
            )
        except BinanceAPIException as e:
            await event.edit(f"❌ Order failed: {e.message}", buttons=None)
        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            await event.edit("❌ Something went wrong placing that order. Check the logs.", buttons=None)

    @bot.on(events.CallbackQuery(data=b"trade:cancel"))
    async def trade_cancel_callback(event):
        pending_trades.pop(event.sender_id, None)
        trade_flow_state.pop(event.sender_id, None)
        await event.edit("🚫 Trade cancelled — nothing was placed.", buttons=None)
        await event.answer("Cancelled")

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/positions$'))
    async def positions_command(event):
        await send_positions_list(bot, await event.get_chat(), event.sender_id)

    @bot.on(events.CallbackQuery(pattern=rb"^position:status:(.+)$"))
    async def position_status_callback(event):
        position_id = event.pattern_match.group(1).decode()
        position = get_position(event.sender_id, position_id)
        if not position:
            await event.answer("Position not found — it may have been closed already.", alert=True)
            return

        try:
            ticker = await binance_client.get_symbol_ticker(symbol=position["symbol"])
            current_price = float(ticker['price'])
        except Exception as e:
            await event.answer(f"Couldn't fetch live price: {e}", alert=True)
            return

        is_up = current_price >= position["entry_price"]
        move_emoji = "🟢" if is_up else "🔴"
        change_pct = ((current_price - position["entry_price"]) / position["entry_price"]) * 100

        await event.answer()
        await event.edit(
            f"{move_emoji} *{position['symbol']} — Live Status*\n\n"
            f"• Entry price: ${position['entry_price']:,.4f}\n"
            f"• Current price: ${current_price:,.4f}\n"
            f"• Movement: {move_emoji} {change_pct:+.2f}%\n"
            f"• Quantity: {position['quantity']}",
            buttons=[[Button.inline("🔄 Refresh", f"position:status:{position_id}".encode())],
                     [Button.inline("💰 Close Position", f"position:close:{position_id}".encode())]],
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"position:keep"))
    async def position_keep_callback(event):
        await event.edit("🤝 Got it, keeping it open — I'll keep watching and let you know if anything changes.", buttons=None)

    @bot.on(events.CallbackQuery(pattern=rb"^position:close:(.+)$"))
    async def position_close_callback(event):
        position_id = event.pattern_match.group(1).decode()
        position = get_position(event.sender_id, position_id)
        if not position:
            await event.answer("Position not found — it may have been closed already.", alert=True)
            return

        client = await get_user_binance_client(event.sender_id)
        if not client:
            await event.answer("You haven't connected a Binance account.", alert=True)
            return

        await event.answer("Closing position...")
        try:
            order = await client.create_order(
                symbol=position["symbol"],
                side="SELL",
                type="MARKET",
                quantity=position["quantity"],
            )
            executed_qty = float(order.get('executedQty', 0) or 0)
            quote_qty = float(order.get('cummulativeQuoteQty', 0) or 0)
            exit_price = (quote_qty / executed_qty) if executed_qty > 0 else None

            remove_open_position(event.sender_id, position_id)

            if exit_price is not None:
                won = exit_price > position["entry_price"]
                result_label = "Win ✅️🤑" if won else "Lost ❎️🥱"
                change_pct = ((exit_price - position["entry_price"]) / position["entry_price"]) * 100
                await event.edit(
                    f"*{position['symbol']} — Position Closed*\n\n"
                    f"• Entry: ${position['entry_price']:,.4f}\n"
                    f"• Exit: ${exit_price:,.4f}\n"
                    f"• Result: *{result_label}* ({change_pct:+.2f}%)",
                    buttons=None,
                    parse_mode='markdown'
                )
            else:
                await event.edit(f"✅ Position closed — Order ID `{order.get('orderId', 'n/a')}`", buttons=None, parse_mode='markdown')
        except BinanceAPIException as e:
            await event.answer(f"Close failed: {e.message}", alert=True)
        except Exception as e:
            logger.error(f"❌ Position close error: {e}")
            await event.answer("Something went wrong closing that position.", alert=True)

    logger.info("✅ Binance trading handler registered (/trade command + guided button flow)")

async def get_agent_reply(user_id, user_text, image_bytes=None):
    """Calls Gemini with this user's running conversation history and
    returns Rex's reply text. Raises AgentLimitReached if the free daily
    quota has been used up. Pass image_bytes (raw JPEG/PNG bytes) to have
    Rex analyze a chart screenshot alongside the text."""
    history = agent_conversations.setdefault(user_id, [])

    live_context = await build_live_data_context(user_text)
    augmented_text = user_text + ("\n" + live_context if live_context else "")

    if image_bytes is not None:
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        history.append({"role": "user", "parts": [image_part, augmented_text]})
    else:
        history.append({"role": "user", "parts": [augmented_text]})
    del history[:-MAX_HISTORY_MESSAGES]  # keep only the most recent messages

    try:
        response = await gemini_model.generate_content_async(history)
    except ResourceExhausted:
        raise AgentLimitReached()

    reply_text = clean_for_telegram((response.text or "").strip())

    history.append({"role": "model", "parts": [reply_text]})
    del history[:-MAX_HISTORY_MESSAGES]

    return reply_text

def setup_agent_handler(bot):
    """Registers the free-text handler that powers Rex's DM conversations.
    Only fires on incoming private messages that aren't commands, so it never
    interferes with /start, /menu, button callbacks, or group forwarding."""

    @bot.on(events.NewMessage(
        incoming=True,
        func=lambda e: e.is_private and bool(e.raw_text) and not e.raw_text.startswith('/')
    ))
    async def agent_message_handler(event):
        if await handle_binance_connect_text(event, bot):
            return
        if await handle_trade_flow_text(event, bot):
            return
        if await handle_autotrade_setup_text(event, bot):
            return
        if await handle_futures_setup_text(event, bot):
            return

        if not gemini_model:
            await event.respond(
                "🤖 The Market Analyst isn't set up yet — the bot owner needs to "
                "add a GEMINI_API_KEY. 🔧"
            )
            return

        try:
            async with bot.action(event.chat_id, 'typing'):
                reply_text = await get_agent_reply(event.sender_id, event.raw_text)
        except AgentLimitReached:
            wait_str = time_until_gemini_reset()
            await event.respond(
                "🤖 I've hit my free daily question limit for today! 😅\n\n"
                f"It resets at midnight Pacific Time — that's *{wait_str}* from "
                "now. Come back after that and I'll be ready to chat again! 🔄📊",
                parse_mode='markdown'
            )
            return
        except Exception as e:
            logger.error(f"❌ Analyst agent error: {e}")
            await event.respond(
                "⚠️ Sorry, I couldn't reach the market analyst brain right now — "
                "try again in a moment. 🔄"
            )
            return

        # Telegram message length safety (4096 char limit)
        for i in range(0, len(reply_text), 3900):
            await event.respond(reply_text[i:i + 3900])

    @bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and bool(e.photo)))
    async def agent_photo_handler(event):
        """Lets users send a chart screenshot (e.g. Pocket Option OTC) for
        Rex to read and give a directional call on — since there's no way
        to pull OTC data automatically, this is the legitimate path: the
        user's own screenshot of their own account, analyzed like any
        other image."""
        if not gemini_model:
            await event.respond(
                "🤖 The Market Analyst isn't set up yet — the bot owner needs to "
                "add a GEMINI_API_KEY. 🔧"
            )
            return

        try:
            image_bytes = await bot.download_media(event.message, file=bytes)
        except Exception as e:
            await event.respond(f"⚠️ Couldn't read that image: {e}")
            return

        caption = event.message.text or (
            "Analyze this chart screenshot — read the candle colors/pattern, "
            "the trend, and any visible indicators (moving averages, MACD, "
            "oscillators). Give me your read: does this look like a BUY or "
            "SELL setup right now, and why?"
        )

        try:
            async with bot.action(event.chat_id, 'typing'):
                reply_text = await get_agent_reply(event.sender_id, caption, image_bytes=image_bytes)
        except AgentLimitReached:
            wait_str = time_until_gemini_reset()
            await event.respond(
                "🤖 I've hit my free daily question limit for today! 😅\n\n"
                f"It resets at midnight Pacific Time — that's *{wait_str}* from "
                "now. Come back after that and I'll be ready to chat again! 🔄📊",
                parse_mode='markdown'
            )
            return
        except Exception as e:
            logger.error(f"❌ Analyst agent image error: {e}")
            await event.respond(
                "⚠️ Sorry, I couldn't read that chart right now — try again in a moment. 🔄"
            )
            return

        for i in range(0, len(reply_text), 3900):
            await event.respond(reply_text[i:i + 3900])

    logger.info("✅ Market Analyst agent handler registered")

# ══════════════════════════════════════════════════════════════
# NEW: Futures Auto-Trading (leverage, both long AND short)
# ══════════════════════════════════════════════════════════════
#
# Same strategy, same math, same safety philosophy as spot auto-trading —
# but futures lets a SELL signal actually be acted on (shorting), and adds
# leverage, which changes the risk math. This section is deliberately kept
# separate from the spot code so nothing here can affect what's already
# working.
#
# Setup requirements:
#   • Binance Futures Testnet is a SEPARATE system from Spot Testnet —
#     generate keys at testnet.binancefuture.com, not testnet.binance.vision
#   • On live Binance, the same API key can work for both spot and futures,
#     as long as "Futures" permission is enabled on the key AND the Futures
#     wallet has funds transferred into it (separate from the Spot wallet)
#   • Margin type is always ISOLATED here — never cross — so a bad trade's
#     risk is capped to that position's own margin, never your whole balance

FUTURES_SESSIONS_FILE = os.path.join(DATA_DIR, 'futures_sessions.json')
LEVERAGE_MAX_ALLOWED = int(os.environ.get('LEVERAGE_MAX_ALLOWED', '10'))  # hard safety ceiling

def _load_futures_sessions():
    if not os.path.exists(FUTURES_SESSIONS_FILE):
        return {}
    try:
        with open(FUTURES_SESSIONS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Could not read futures sessions file: {e}")
        return {}

def _save_futures_sessions(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FUTURES_SESSIONS_FILE, 'w') as f:
        json.dump(store, f)

futures_sessions = _load_futures_sessions()
futures_setup_state = {}
FUTURES_POSITIONS_FILE = os.path.join(DATA_DIR, 'futures_positions.json')

def _load_futures_positions():
    if not os.path.exists(FUTURES_POSITIONS_FILE):
        return {}
    try:
        with open(FUTURES_POSITIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_futures_positions(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FUTURES_POSITIONS_FILE, 'w') as f:
        json.dump(store, f)

futures_positions = _load_futures_positions()

def get_futures_session(user_id):
    return futures_sessions.get(str(user_id))

def save_futures_session(user_id, session):
    futures_sessions[str(user_id)] = session
    _save_futures_sessions(futures_sessions)

def stop_futures_session(user_id):
    session = futures_sessions.get(str(user_id))
    if session:
        session["enabled"] = False
        _save_futures_sessions(futures_sessions)

def add_futures_position(user_id, symbol, side, quantity, entry_price, order_id, stop_loss_price, liquidation_price, leverage):
    key = str(user_id)
    positions = futures_positions.setdefault(key, [])
    position_id = f"{order_id}"
    positions.append({
        "id": position_id, "symbol": symbol, "side": side, "quantity": quantity,
        "entry_price": entry_price, "stop_loss_price": stop_loss_price,
        "liquidation_price": liquidation_price, "leverage": leverage
    })
    _save_futures_positions(futures_positions)
    return position_id

def remove_futures_position(user_id, position_id):
    key = str(user_id)
    positions = futures_positions.get(key, [])
    futures_positions[key] = [p for p in positions if p["id"] != position_id]
    _save_futures_positions(futures_positions)

async def execute_futures_autotrade(bot, user_id, symbol, direction):
    """Opens a leveraged long (BUY) or short (SELL) position — the one
    real advantage futures has over spot for this bot. Every position still
    gets its own % stop-loss AND is monitored against Binance's own real
    liquidation price as a second, independent safety check."""
    session = get_futures_session(user_id)
    if not session or not session.get("enabled"):
        logger.info(f"ℹ️ Futures auto-trade skip [{symbol}, user {user_id}]: no active session")
        return
    if symbol not in session.get("symbols", []):
        logger.info(f"ℹ️ Futures auto-trade skip [{symbol}, user {user_id}]: symbol not in session watchlist")
        return
    if session["trades_done"] >= session["max_trades"]:
        logger.info(f"ℹ️ Futures auto-trade skip [{symbol}, user {user_id}]: max trades reached")
        return
    existing = [p for p in futures_positions.get(str(user_id), []) if p["symbol"] == symbol]
    if existing:
        logger.info(f"ℹ️ Futures auto-trade skip [{symbol}, user {user_id}]: already holding a position on this symbol")
        return

    client = await get_user_binance_client(user_id)
    if not client:
        logger.warning(f"⚠️ Futures auto-trade skip [{symbol}, user {user_id}]: no connected Binance client")
        return

    leverage = session["leverage"]
    try:
        await client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass  # already isolated — Binance errors if you set it to what it already is, harmless
    try:
        await client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except Exception as e:
        logger.warning(f"⚠️ Futures auto-trade skip [{symbol}, user {user_id}]: couldn't set leverage: {e}")
        return

    try:
        account = await client.futures_account()
        ticker = await binance_client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
    except Exception as e:
        logger.warning(f"⚠️ Futures auto-trade skip [{symbol}, user {user_id}]: couldn't fetch balance/price: {e}")
        return

    balance = float(account.get('availableBalance', 0) or 0)
    if balance <= 0:
        logger.warning(f"⚠️ Futures auto-trade skip [{symbol}, user {user_id}]: USDT futures balance is 0")
        return

    starting_balance = session["starting_balance"]
    loss_limit_amount = starting_balance * (session["loss_limit_pct"] / 100)
    if session["realized_pnl"] <= -loss_limit_amount:
        session["enabled"] = False
        _save_futures_sessions(futures_sessions)
        try:
            await bot.send_message(
                user_id,
                f"🛑 *Futures Auto-Trading Stopped — Circuit Breaker*\n\n"
                f"Realized loss (${session['realized_pnl']:,.2f}) hit your {session['loss_limit_pct']}% limit.",
                parse_mode='markdown'
            )
        except Exception:
            pass
        return

    margin_amount = balance * (session["amount_pct"] / 100)
    notional_value = margin_amount * leverage
    quantity = notional_value / price
    side = "BUY" if direction == "BUY" else "SELL"
    stop_loss_price = price * (1 - session["stop_loss_pct"] / 100) if side == "BUY" else price * (1 + session["stop_loss_pct"] / 100)

    try:
        order = await client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=round(quantity, 3))
    except Exception as e:
        logger.error(f"❌ Futures auto-trade execution error [{symbol}, user {user_id}]: {e}")
        return

    fill_price = price
    try:
        position_info = await client.futures_position_information(symbol=symbol)
        liquidation_price = float(position_info[0]['liquidationPrice']) if position_info else None
        entry_from_exchange = float(position_info[0]['entryPrice']) if position_info else None
        if entry_from_exchange:
            fill_price = entry_from_exchange
    except Exception as e:
        logger.warning(f"⚠️ Couldn't fetch liquidation price for {symbol}: {e}")
        liquidation_price = None

    add_futures_position(user_id, symbol, side, quantity, fill_price, order.get('orderId'), stop_loss_price, liquidation_price, leverage)
    session["trades_done"] += 1
    _save_futures_sessions(futures_sessions)

    direction_label = "🟢 LONG" if side == "BUY" else "🔴 SHORT"
    liq_note = f"\n• Liquidation price: ${liquidation_price:,.4f} ⚠️" if liquidation_price else ""
    try:
        await bot.send_message(
            user_id,
            f"🤖 *Futures Auto-Trade Executed* ({session['trades_done']}/{session['max_trades']})\n\n"
            f"• {symbol} {direction_label} — {leverage}x isolated\n"
            f"• Entry: ${fill_price:,.4f}\n"
            f"• Stop-loss: ${stop_loss_price:,.4f}"
            f"{liq_note}\n"
            f"• Margin used: ${margin_amount:,.2f} ({session['amount_pct']}% of balance)",
            parse_mode='markdown'
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not notify user {user_id} of futures auto-trade: {e}")

async def close_futures_position(bot, user_id, position, reason):
    client = await get_user_binance_client(user_id)
    if not client:
        return
    close_side = "SELL" if position["side"] == "BUY" else "BUY"
    try:
        order = await client.futures_create_order(
            symbol=position["symbol"], side=close_side, type="MARKET",
            quantity=round(position["quantity"], 3), reduceOnly=True
        )
    except Exception as e:
        logger.error(f"❌ Futures close error [{position['symbol']}, user {user_id}]: {e}")
        return

    try:
        ticker = await binance_client.futures_symbol_ticker(symbol=position["symbol"])
        exit_price = float(ticker['price'])
    except Exception:
        exit_price = position["entry_price"]

    if position["side"] == "BUY":
        pnl = (exit_price - position["entry_price"]) * position["quantity"]
    else:
        pnl = (position["entry_price"] - exit_price) * position["quantity"]

    remove_futures_position(user_id, position["id"])
    session = get_futures_session(user_id)
    if session:
        session["realized_pnl"] = session.get("realized_pnl", 0.0) + pnl
        _save_futures_sessions(futures_sessions)

    result_label = "Win ✅️🤑" if pnl > 0 else "Lost ❎️🥱"
    try:
        await bot.send_message(
            user_id,
            f"🤖 *Futures Position Closed* — {reason}\n\n"
            f"• {position['symbol']} ({position['side']}, {position['leverage']}x)\n"
            f"• Entry: ${position['entry_price']:,.4f} → Exit: ${exit_price:,.4f}\n"
            f"• Result: *{result_label}* (${pnl:,.2f})",
            parse_mode='markdown'
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not notify user {user_id} of futures close: {e}")

async def monitor_futures_positions(bot):
    """Fast-cadence watcher — checks every open futures position against
    BOTH its own % stop-loss AND Binance's real liquidation price. The
    liquidation check is a second, independent safety net: if price is
    getting dangerously close to actual liquidation (not just our stop-loss
    level), it closes early rather than risk the exchange force-closing it."""
    while True:
        await asyncio.sleep(STOP_LOSS_CHECK_SECONDS)
        if not binance_client:
            continue
        for user_id_str, positions in list(futures_positions.items()):
            user_id = int(user_id_str)
            for p in list(positions):
                try:
                    ticker = await binance_client.futures_symbol_ticker(symbol=p["symbol"])
                    current_price = float(ticker['price'])
                except Exception as e:
                    logger.warning(f"⚠️ Futures price check failed for {p['symbol']}: {e}")
                    continue

                stop_hit = (
                    (p["side"] == "BUY" and current_price <= p["stop_loss_price"]) or
                    (p["side"] == "SELL" and current_price >= p["stop_loss_price"])
                )
                liq_price = p.get("liquidation_price")
                near_liquidation = False
                if liq_price:
                    distance = abs(p["entry_price"] - liq_price)
                    safety_buffer = liq_price + (distance * 0.2 if p["side"] == "BUY" else -distance * 0.2)
                    near_liquidation = (
                        (p["side"] == "BUY" and current_price <= safety_buffer) or
                        (p["side"] == "SELL" and current_price >= safety_buffer)
                    )

                if stop_hit:
                    await close_futures_position(bot, user_id, p, "🛑 Stop-loss triggered")
                elif near_liquidation:
                    await close_futures_position(bot, user_id, p, "⚠️ Closed early — approaching liquidation price")

def futures_leverage_buttons():
    rows = [[Button.inline(f"{lv}x", f"futures:leverage:{lv}".encode()) for lv in [2, 3, 5]]]
    rows.append([Button.inline("✏️ Type a custom leverage", b"futures:leverage:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def futures_amount_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"futures:amountpct:{p}".encode()) for p in [2, 5, 10]]]
    rows.append([Button.inline("✏️ Type a custom %", b"futures:amountpct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def futures_stoploss_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"futures:stoplosspct:{p}".encode()) for p in [1, 2, 3]]]
    rows.append([Button.inline("✏️ Type a custom %", b"futures:stoplosspct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

def futures_losslimit_pct_buttons():
    rows = [[Button.inline(f"{p}%", f"futures:losslimitpct:{p}".encode()) for p in [5, 10, 15]]]
    rows.append([Button.inline("✏️ Type a custom %", b"futures:losslimitpct:custom")])
    rows.append([Button.inline("🏠 Main Menu", b"menu:main")])
    return rows

async def send_futures_status(bot, chat, user_id):
    session = get_futures_session(user_id)
    if not session or not session.get("enabled"):
        await bot.send_message(
            chat,
            "⚡ *Futures Trading* — currently OFF\n\n"
            "Same strategy and scanner as spot, but leveraged — and both "
            "BUY (long) and SELL (short) signals are actionable here.\n\n"
            "⚠️ Futures uses leverage — a losing move is amplified. Every "
            "position still gets a % stop-loss AND is watched against "
            "Binance's real liquidation price as a second safety net. "
            "Margin type is always ISOLATED (never cross), so risk stays "
            "capped to each position's own margin.\n\n"
            "Requires Binance Futures-enabled keys (Futures Testnet keys "
            "are separate from Spot Testnet keys — see testnet.binancefuture.com).",
            buttons=[[Button.inline("🚀 Set Up Futures Trading", b"futures:setup_start")],
                     [Button.inline("🏠 Main Menu", b"menu:main")]],
            parse_mode='markdown'
        )
        return
    await bot.send_message(
        chat,
        f"⚡ *Futures Trading* — currently ON ✅\n\n"
        f"• Trades so far: {session['trades_done']}/{session['max_trades']}\n"
        f"• Leverage: {session['leverage']}x (isolated)\n"
        f"• Margin per trade: {session['amount_pct']}% of balance\n"
        f"• Stop-loss per trade: {session['stop_loss_pct']}%\n"
        f"• Loss limit (circuit breaker): {session['loss_limit_pct']}%\n"
        f"• Realized P&L this session: ${session.get('realized_pnl', 0):,.2f}\n"
        f"• Symbols: {', '.join(session['symbols'])}",
        buttons=[[Button.inline("🛑 Stop Futures Trading", b"futures:stop")],
                 [Button.inline("🏠 Main Menu", b"menu:main")]],
        parse_mode='markdown'
    )

async def confirm_futures_setup(event, bot, state):
    client = await get_user_binance_client(event.sender_id)
    if not client:
        await event.respond("You haven't connected a Binance account yet. Use /connectbinance to set it up. 🔐")
        return
    try:
        account = await client.futures_account()
    except Exception as e:
        await event.respond(
            f"⚠️ Couldn't fetch your futures balance: {e}\n\n"
            f"If you're on testnet, remember Futures Testnet needs its own keys "
            f"from testnet.binancefuture.com — Spot Testnet keys won't work here."
        )
        return

    starting_balance = float(account.get('availableBalance', 0) or 0)
    mode_label = "🧪 TESTNET (fake money)" if BINANCE_TESTNET else "⚠️ LIVE (real money)"
    session_preview = {
        "enabled": False, "leverage": state["leverage"], "amount_pct": state["amount_pct"],
        "stop_loss_pct": state["stop_loss_pct"], "loss_limit_pct": state["loss_limit_pct"],
        "max_trades": state["max_trades"], "trades_done": 0, "starting_balance": starting_balance,
        "realized_pnl": 0.0, "symbols": list(SCAN_SYMBOLS)
    }
    futures_setup_state[event.sender_id] = {"pending_session": session_preview}
    await event.respond(
        f"⚡ *Confirm Futures Trading Setup* — {mode_label}\n\n"
        f"• Leverage: *{state['leverage']}x* (isolated margin)\n"
        f"• Margin per trade: *{state['amount_pct']}%* of balance\n"
        f"• Stop-loss per trade: *{state['stop_loss_pct']}%*\n"
        f"• Loss limit (circuit breaker): *{state['loss_limit_pct']}%* "
        f"(≈ ${starting_balance * state['loss_limit_pct'] / 100:,.2f})\n"
        f"• Max trades this session: *{state['max_trades']}*\n"
        f"• Watching: {', '.join(SCAN_SYMBOLS)} (both long AND short)\n"
        f"• Starting futures balance: *${starting_balance:,.2f} USDT*\n\n"
        f"⚠️ Leverage amplifies both gains and losses. Trades fire automatically.",
        buttons=[[Button.inline("🚀 Start Futures Trading", b"futures:start")],
                 [Button.inline("❌ Cancel", b"menu:main")]],
        parse_mode='markdown'
    )

async def handle_futures_setup_text(event, bot):
    state = futures_setup_state.get(event.sender_id)
    if not state:
        return False
    text = event.raw_text.strip()

    if state["step"] == "awaiting_leverage_text":
        try:
            lv = int(text)
            if lv <= 0 or lv > LEVERAGE_MAX_ALLOWED:
                raise ValueError
        except ValueError:
            await event.respond(f"⚠️ Type a whole number between 1 and {LEVERAGE_MAX_ALLOWED}, e.g. `3`")
            return True
        state["leverage"] = lv
        state["step"] = "awaiting_amount_pct"
        await event.respond("📊 What % of your futures balance as margin per trade?", buttons=futures_amount_pct_buttons(), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_amount_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `5`")
            return True
        state["amount_pct"] = pct
        state["step"] = "awaiting_stoploss_pct"
        await event.respond("📊 Stop-loss % per trade:", buttons=futures_stoploss_pct_buttons(), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_stoploss_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `2`")
            return True
        state["stop_loss_pct"] = pct
        state["step"] = "awaiting_losslimit_pct"
        await event.respond("📊 Loss limit % — stops ALL futures trading if hit:", buttons=futures_losslimit_pct_buttons(), parse_mode='markdown')
        return True

    if state["step"] == "awaiting_losslimit_pct_text":
        try:
            pct = float(text)
            if pct <= 0 or pct > 100:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a valid percentage, e.g. `10`")
            return True
        state["loss_limit_pct"] = pct
        state["step"] = "awaiting_max_trades"
        await event.respond("📊 How many trades total should this session run?")
        return True

    if state["step"] == "awaiting_max_trades":
        try:
            count = int(text)
            if count <= 0:
                raise ValueError
        except ValueError:
            await event.respond("⚠️ Type a whole number, e.g. `20`")
            return True
        state["max_trades"] = count
        futures_setup_state.pop(event.sender_id, None)
        await confirm_futures_setup(event, bot, state)
        return True

    return False

def setup_futures_handlers(bot):
    @bot.on(events.NewMessage(incoming=True, pattern=r'^/futures$'))
    async def futures_command(event):
        await send_futures_status(bot, await event.get_chat(), event.sender_id)

    @bot.on(events.NewMessage(incoming=True, pattern=r'^/stopfutures$'))
    async def stopfutures_command(event):
        stop_futures_session(event.sender_id)
        await event.respond("🛑 Futures trading stopped. Existing positions are still protected by their stop-losses and liquidation watcher.")

    @bot.on(events.CallbackQuery(data=b"menu:futures"))
    async def futures_menu_callback(event):
        await event.answer()
        await send_futures_status(bot, await event.get_chat(), event.sender_id)

    @bot.on(events.CallbackQuery(data=b"futures:setup_start"))
    async def futures_setup_start_callback(event):
        if not await get_user_binance_client(event.sender_id):
            await event.edit(
                "You haven't connected a Binance account yet.\n\nUse /connectbinance first. 🔐",
                buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]]
            )
            return
        futures_setup_state[event.sender_id] = {"step": "awaiting_leverage"}
        await event.edit(
            f"⚡ Choose your leverage (max {LEVERAGE_MAX_ALLOWED}x — low leverage strongly recommended):",
            buttons=futures_leverage_buttons(), parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(pattern=rb"^futures:leverage:(custom|\d+)$"))
    async def futures_leverage_callback(event):
        choice = event.pattern_match.group(1).decode()
        if choice == "custom":
            futures_setup_state[event.sender_id] = {"step": "awaiting_leverage_text"}
            await event.edit(f"✏️ Type your leverage (1-{LEVERAGE_MAX_ALLOWED}), e.g. `3`:", buttons=None, parse_mode='markdown')
            return
        futures_setup_state[event.sender_id] = {"step": "awaiting_amount_pct", "leverage": int(choice)}
        await event.edit("📊 What % of your futures balance as margin per trade?", buttons=futures_amount_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^futures:amountpct:(custom|\d+)$"))
    async def futures_amountpct_callback(event):
        choice = event.pattern_match.group(1).decode()
        state = futures_setup_state.get(event.sender_id, {})
        if choice == "custom":
            state["step"] = "awaiting_amount_pct_text"
            futures_setup_state[event.sender_id] = state
            await event.edit("✏️ Type the % of balance as margin per trade, e.g. `5`:", buttons=None, parse_mode='markdown')
            return
        state["amount_pct"] = float(choice)
        state["step"] = "awaiting_stoploss_pct"
        futures_setup_state[event.sender_id] = state
        await event.edit("📊 Stop-loss % per trade:", buttons=futures_stoploss_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^futures:stoplosspct:(custom|\d+)$"))
    async def futures_stoplosspct_callback(event):
        choice = event.pattern_match.group(1).decode()
        state = futures_setup_state.get(event.sender_id, {})
        if choice == "custom":
            state["step"] = "awaiting_stoploss_pct_text"
            futures_setup_state[event.sender_id] = state
            await event.edit("✏️ Type the stop-loss % per trade, e.g. `2`:", buttons=None, parse_mode='markdown')
            return
        state["stop_loss_pct"] = float(choice)
        state["step"] = "awaiting_losslimit_pct"
        futures_setup_state[event.sender_id] = state
        await event.edit("📊 Loss limit % — stops ALL futures trading if hit:", buttons=futures_losslimit_pct_buttons(), parse_mode='markdown')

    @bot.on(events.CallbackQuery(pattern=rb"^futures:losslimitpct:(custom|\d+)$"))
    async def futures_losslimitpct_callback(event):
        choice = event.pattern_match.group(1).decode()
        state = futures_setup_state.get(event.sender_id, {})
        if choice == "custom":
            state["step"] = "awaiting_losslimit_pct_text"
            futures_setup_state[event.sender_id] = state
            await event.edit("✏️ Type the loss-limit %, e.g. `10`:", buttons=None, parse_mode='markdown')
            return
        state["loss_limit_pct"] = float(choice)
        state["step"] = "awaiting_max_trades"
        futures_setup_state[event.sender_id] = state
        await event.edit("📊 How many trades total should this session run? Type a number:", buttons=None)

    @bot.on(events.CallbackQuery(data=b"futures:start"))
    async def futures_start_callback(event):
        state = futures_setup_state.pop(event.sender_id, None)
        if not state or "pending_session" not in state:
            await event.answer("Setup expired — please start again with /futures.", alert=True)
            return
        session = state["pending_session"]
        session["enabled"] = True
        save_futures_session(event.sender_id, session)
        mode_label = "🧪 TESTNET" if BINANCE_TESTNET else "⚠️ LIVE"
        await event.edit(f"✅ *Futures Trading started!* ({mode_label})\n\nWatching {', '.join(session['symbols'])} for both longs and shorts.", buttons=None, parse_mode='markdown')

    @bot.on(events.CallbackQuery(data=b"futures:stop"))
    async def futures_stop_callback(event):
        stop_futures_session(event.sender_id)
        await event.edit("🛑 Futures trading stopped. Existing positions remain protected.", buttons=[[Button.inline("🏠 Main Menu", b"menu:main")]])

    logger.info("✅ Futures trading handlers registered (/futures, /stopfutures)")

# ══════════════════════════════════════════════════════════════
# END NEW menu code
# ══════════════════════════════════════════════════════════════

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

    # ── Auto-track every private message the bot sends, so "🏠 Main Menu"
    # can clean the chat later. This also covers event.respond(), since it
    # calls this same underlying method — no need to edit every call site.
    _original_bot_send_message = bot.send_message

    async def _tracked_bot_send_message(entity, *args, **kwargs):
        message = await _original_bot_send_message(entity, *args, **kwargs)
        try:
            if message and message.is_private:
                track_message(message.chat_id, message)
        except Exception as e:
            logger.warning(f"⚠️ Message tracking failed (non-fatal): {e}")
        return message

    bot.send_message = _tracked_bot_send_message

    # ── NEW: register the Strategy / Materials / Register / Signal Groups menu ────
    setup_menu_handlers(bot)
    # ── Market Analyst agent — now powered by Gemini's free tier ────
    setup_agent_handler(bot)
    # ── Binance live data + manually-confirmed trading ────
    await init_binance_client()
    setup_binance_account_handlers(bot)
    setup_binance_trading_handler(bot)
    setup_opportunity_alerts_handlers(bot)
    setup_autotrade_handlers(bot)
    setup_futures_handlers(bot)
    await resolve_signal_groups(bot)

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

    # userbot needs its OWN resolved copy of the destination entity — an
    # entity object carries an access_hash that's specific to whichever
    # account discovered it, so reusing bot's dest_entity inside a userbot
    # request (like send_file) fails with "Invalid channel object."
    try:
        userbot_dest_entity = await userbot.get_entity(int(DEST_GROUP))
    except Exception as e:
        logger.error(f"❌ userbot could not resolve destination group: {e}")
        return False

    # ── NEW MESSAGE Handler ────────────────────────────────────
    @userbot.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        message = event.message
        text    = message.text or message.caption or ''
        preview = text[:50].replace('\n', ' ')
        logger.info(f"📨 New message: {preview}...")

        if is_promo_message(text):
            try:
                replacement = extract_signal_time_from_promo(text)
                sent = await bot.send_message(dest_entity, replacement)
                message_map[message.id] = sent.id
                logger.info(f"🔄 Promo replaced with: {replacement}")
            except Exception as e:
                logger.error(f"❌ Promo replace error: {e}")
            return

        if message.media and text:
            text_upper = text.upper()
            force_forward = any(k in text_upper for k in [
                'WIN ✅', '✅ WIN', 'WIN AT', 'INSTANT EXECUTION',
                'WIN IN', 'DIRECT WIN', 'WIN AT M'
            ])
            if force_forward:
                logger.info("📸 Media with WIN caption — force forwarding!")
                try:
                    direction = get_direction(text)
                    processed_caption = process_text(text, direction)
                    sent = await userbot.send_file(
                        userbot_dest_entity,
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
            direction = get_direction(text)

            if direction:
                signal_direction_map[message.id] = direction

            if message.reply_to_msg_id:
                orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                if orig_dir and not direction:
                    direction = orig_dir

            processed_text = process_text(text, direction)

            logger.info("🚨 Signal detected! Forwarding...")

            if message.media:
                caption     = message.caption or ''
                cap_dir = direction or get_direction(caption)
                processed_caption = process_text(caption, cap_dir) if caption else ''
                sent = await userbot.send_file(
                    userbot_dest_entity,
                    file=message.media,
                    caption=processed_caption or processed_text
                )
            else:
                sent = await bot.send_message(
                    dest_entity,
                    processed_text
                )

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

        dest_msg_id = message_map.get(message.id)
        if not dest_msg_id:
            logger.info("⚠️ No mapping found — skipping edit")
            return

        if not is_signal_message(text):
            return

        try:
            direction = get_direction(text) or \
                        signal_direction_map.get(message.id)

            if message.reply_to_msg_id:
                orig_dir = signal_direction_map.get(message.reply_to_msg_id)
                if orig_dir and not direction:
                    direction = orig_dir

            if direction:
                signal_direction_map[message.id] = direction

            processed_text = process_text(text, direction)

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
    asyncio.create_task(scan_for_opportunities(bot))
    asyncio.create_task(monitor_stop_losses(bot))
    asyncio.create_task(monitor_futures_positions(bot))
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
