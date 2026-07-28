from keep_alive import keep_alive
keep_alive()

from telethon import TelegramClient, events
from telethon import Button
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
SIGNAL_GROUPS_RAW = os.environ.get('SIGNAL_GROUPS', '')

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
    Uses the bot account (it must already be a member/admin of each group).
    Public groups resolve to their t.me/username link; private groups get
    a freshly exported invite link (requires the bot to have invite rights)."""
    global signal_groups_cache
    identifiers = [g.strip() for g in SIGNAL_GROUPS_RAW.split(',') if g.strip()]
    resolved = []
    for ident in identifiers:
        try:
            entity = await bot.get_entity(ident)
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', None) or ident
            username = getattr(entity, 'username', None)
            if username:
                link = f"https://t.me/{username}"
            else:
                invite = await bot(ExportChatInviteRequest(entity))
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
        await event.respond(
            "👋 *Welcome to Rex Signal Bot!*\n\nChoose an option below:",
            buttons=main_menu_buttons(),
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery(data=b"menu:main"))
    async def main_menu_callback(event):
        await event.edit(
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
GEMINI_MODEL   = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

class AgentLimitReached(Exception):
    """Raised when Gemini's free daily quota has been used up for the day."""
    pass

AGENT_SYSTEM_PROMPT = """You are Rex, a friendly and sharp binary options market \
analyst built into Pascal Brown's signal Telegram bot. You know binary options \
and OTC synthetic markets inside and out: candlestick reading, MACD, moving \
averages, oscillators, support/resistance, trend-vs-range analysis, martingale \
and risk management, and the Trending Strategy taught elsewhere in this bot.

STYLE
- Talk like a real, warm, sharp trader friend — not a corporate assistant. \
Casual, encouraging, clear, and conversational.
- Use emojis naturally and often (📈📉🟢🔴🎯💡⚠️🤔) to make things lively and easy \
to scan — but don't overdo it in every single sentence.
- Keep answers focused; use short paragraphs or bullet points for clarity.
- Actively ask follow-up or clarifying questions when it helps (e.g. their \
experience level, which pair/platform, what they've already tried) instead of \
just lecturing at them. A good conversation goes both ways.
- React to what the user shares — empathize with losses, celebrate wins, keep \
it human.
- If someone asks directly whether you're human or an AI, be honest that you're \
an AI assistant. Otherwise just talk naturally, no need to caveat every message.

SUBSTANCE RULES
- You can explain concepts, indicators, and strategies in depth, and discuss \
general market structure and risk management.
- Never promise or imply a guaranteed win, a "sure" signal, or certainty about \
future price direction. Markets are probabilistic — frame things as tendencies \
and probabilities, not certainties.
- Don't hand someone a specific "buy/sell right now, this amount" call as if it \
were financial advice to act on with real money. Instead help them learn to \
read the chart and decide for themselves.
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

async def get_agent_reply(user_id, user_text):
    """Calls Gemini with this user's running conversation history and
    returns Rex's reply text. Raises AgentLimitReached if the free daily
    quota has been used up."""
    history = agent_conversations.setdefault(user_id, [])
    history.append({"role": "user", "parts": [user_text]})
    del history[:-MAX_HISTORY_MESSAGES]  # keep only the most recent messages

    try:
        response = await gemini_model.generate_content_async(history)
    except ResourceExhausted:
        raise AgentLimitReached()

    reply_text = (response.text or "").strip()

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

    logger.info("✅ Market Analyst agent handler registered")

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

    # ── NEW: register the Strategy / Materials / Register / Signal Groups menu ────
    setup_menu_handlers(bot)
    # ── Market Analyst agent — now powered by Gemini's free tier ────
    setup_agent_handler(bot)
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
                    dest_entity,
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
