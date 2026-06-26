#!/usr/bin/env python3
"""
XAUUSD Gold Price Alert Telegram Bot
Tracks live gold prices and sends alerts when your target is hit.

Setup:
  export BOT_TOKEN="your_token_from_BotFather"
  pip install -r requirements.txt
  python bot.py
"""

import logging
import sqlite3
import os
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yfinance as yf

# ── Configuration ─────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))   # seconds
DB_PATH        = os.getenv("DB_PATH", "alerts.db")

# Try spot gold first, fall back to Gold Futures
PRICE_SYMBOLS  = ["XAUUSD=X", "GC=F"]

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format  = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    level   = logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PRICE FEED
# ══════════════════════════════════════════════════════════════════════════════

def get_price() -> Optional[float]:
    """
    Fetch the current XAUUSD price.
    Tries XAUUSD=X (spot gold) first, then GC=F (Gold Futures) as fallback.
    Returns None if both fail.
    """
    for symbol in PRICE_SYMBOLS:
        try:
            ticker  = yf.Ticker(symbol)
            fast    = ticker.fast_info
            price   = fast.get("last_price") or fast.get("regularMarketPrice")

            if price and float(price) > 500:          # gold is always > $500/oz
                return round(float(price), 2)

            # Fallback: pull recent 5-minute bars
            hist = ticker.history(period="1d", interval="5m")
            if not hist.empty:
                p = float(hist["Close"].iloc[-1])
                if p > 500:
                    return round(p, 2)

        except Exception as exc:
            logger.warning("Price fetch failed (%s): %s", symbol, exc)

    return None

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE (SQLite — persists alerts across restarts)
# ══════════════════════════════════════════════════════════════════════════════

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL,
                target     REAL    NOT NULL,
                direction  TEXT    NOT NULL,   -- 'above' | 'below'
                note       TEXT    DEFAULT '',
                created_at TEXT    NOT NULL,
                active     INTEGER DEFAULT 1
            )
        """)
        c.commit()

def alert_add(chat_id: int, target: float, direction: str, note: str = "") -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO alerts (chat_id, target, direction, note, created_at)"
            " VALUES (?,?,?,?,?)",
            (chat_id, target, direction, note,
             datetime.utcnow().isoformat(timespec="seconds"))
        )
        c.commit()
        return cur.lastrowid

def alert_list(chat_id: int) -> list:
    with _conn() as c:
        return c.execute(
            "SELECT id, target, direction, note, created_at"
            " FROM alerts WHERE chat_id=? AND active=1 ORDER BY id",
            (chat_id,)
        ).fetchall()

def alert_cancel(alert_id: int, chat_id: int) -> bool:
    with _conn() as c:
        cur = c.execute(
            "UPDATE alerts SET active=0 WHERE id=? AND chat_id=? AND active=1",
            (alert_id, chat_id)
        )
        c.commit()
        return cur.rowcount > 0

def alert_cancel_all(chat_id: int) -> int:
    with _conn() as c:
        cur = c.execute(
            "UPDATE alerts SET active=0 WHERE chat_id=? AND active=1", (chat_id,)
        )
        c.commit()
        return cur.rowcount

def alert_all_active() -> list:
    with _conn() as c:
        return c.execute(
            "SELECT id, chat_id, target, direction FROM alerts WHERE active=1"
        ).fetchall()

def alert_deactivate(alert_id: int) -> None:
    with _conn() as c:
        c.execute("UPDATE alerts SET active=0 WHERE id=?", (alert_id,))
        c.commit()

# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fp(price: float) -> str:
    """Format dollar price: $2,345.67"""
    return f"${price:,.2f}"

def dir_emoji(direction: str) -> str:
    return "📈" if direction == "above" else "📉"

def utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

HELP_TEXT = """
❓ *Commands*

• /price — Live XAUUSD price
• /alert `<price>` `[note]` — Set a price alert
• /alerts — List your active alerts
• /cancel `<id>` — Remove one alert
• /cancelall — Remove all alerts

*Examples:*
`/alert 2500` → fires when gold ≥ $2,500
`/alert 2100 support zone` → with a note
`/cancel 3` → remove alert #3

*How it works:*
Bot checks price every {interval}s.  When price crosses your target you get a notification and the alert auto-removes.

*Price source:* Yahoo Finance (XAUUSD=X)
⚠️  Free feed may have ~15 min delay
""".strip()

# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏅 *XAUUSD Gold Price Alert Bot*\n\n"
        "I track live gold prices and alert you the moment they hit your target!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 /price       — Live price\n"
        "🔔 /alert `<$>` — Set alert\n"
        "📋 /alerts      — Your alerts\n"
        "❌ /cancel `<id>` — Remove alert\n"
        "❓ /help        — Full help\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "_Example:_ `/alert 2450` → notify me when gold hits $2,450"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /price ───────────────────────────────────────────────────────────────────

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Fetching live gold price…")
    price = get_price()
    if price:
        await msg.edit_text(
            f"📊 *XAUUSD Spot Price*\n\n"
            f"💰 `{fp(price)}`  per troy oz\n"
            f"🕐 `{utc_now()}`\n\n"
            f"_Set alert:_ `/alert {int(price + 50)}`",
            parse_mode="Markdown",
        )
    else:
        await msg.edit_text(
            "❌ Price temporarily unavailable.\n"
            "Markets may be closed (weekend) or API is slow. Try again soon."
        )

# ─── /alert ───────────────────────────────────────────────────────────────────

async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usage = (
        "Usage: `/alert <price>` `[optional note]`\n\n"
        "Examples:\n"
        "• `/alert 2500`\n"
        "• `/alert 2100 buy zone`\n"
        "• `/alert 1980 stop loss`"
    )
    args = context.args
    if not args:
        await update.message.reply_text(usage, parse_mode="Markdown")
        return

    # Parse price
    try:
        target = round(float(args[0].replace(",", "").replace("$", "")), 2)
    except ValueError:
        await update.message.reply_text(f"❌ Invalid price.\n\n{usage}", parse_mode="Markdown")
        return

    if not (100 < target < 50_000):
        await update.message.reply_text("❌ Price must be between $100 and $50,000.")
        return

    note = " ".join(args[1:]) if len(args) > 1 else ""

    # Get current price for direction
    current = get_price()
    if current is None:
        await update.message.reply_text(
            "❌ Could not fetch current price right now.\n"
            "Please try again in a moment."
        )
        return

    direction = "above" if target > current else "below"
    cid       = update.effective_chat.id
    aid       = alert_add(cid, target, direction, note)
    emoji     = dir_emoji(direction)
    diff      = abs(current - target)

    text = (
        f"✅ *Alert Created — ID `#{aid}`*\n\n"
        f"🎯 Target:   `{fp(target)}`\n"
        f"📊 Current:  `{fp(current)}`\n"
        f"↔️  Gap:      `{fp(diff)}`\n"
        f"{emoji} Fires when price goes *{direction}* `{fp(target)}`"
    )
    if note:
        text += f"\n📝 Note: _{note}_"
    text += f"\n\n_Check interval: every {CHECK_INTERVAL}s_"

    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /alerts ──────────────────────────────────────────────────────────────────

async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    rows  = alert_list(cid)
    current = get_price()

    if not rows:
        await update.message.reply_text(
            "📭 *No active alerts.*\n\n_Use /alert <price> to create one!_",
            parse_mode="Markdown",
        )
        return

    lines = ["📋 *Your Active Alerts*"]
    if current:
        lines.append(f"📊 Current: `{fp(current)}`\n")
    lines.append("━━━━━━━━━━━━━━━━━━")

    for aid, target, direction, note, created in rows:
        emoji   = dir_emoji(direction)
        gap_str = f"  ↔️ `{fp(abs(current - target))} away`" if current else ""
        note_str = f"\n      📝 _{note}_" if note else ""
        lines.append(f"{emoji} `#{aid}` → `{fp(target)}` ({direction}){gap_str}{note_str}")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"_{len(rows)} alert(s) active_  •  /cancel `<id>` to remove")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /cancel ──────────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/cancel <id>`\n\nSee /alerts for your IDs.",
            parse_mode="Markdown",
        )
        return

    try:
        aid = int(str(context.args[0]).lstrip("#"))
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Example: `/cancel 3`", parse_mode="Markdown")
        return

    cid = update.effective_chat.id
    if alert_cancel(aid, cid):
        await update.message.reply_text(f"✅ Alert `#{aid}` removed.", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Alert `#{aid}` not found or already inactive.\n"
            "Use /alerts to see your current alerts."
        )

# ─── /cancelall ───────────────────────────────────────────────────────────────

async def cmd_cancelall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    n   = alert_cancel_all(cid)
    if n:
        await update.message.reply_text(f"🗑 Removed *{n}* alert(s).", parse_mode="Markdown")
    else:
        await update.message.reply_text("📭 No active alerts to remove.")

# ─── /help ────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT.format(interval=CHECK_INTERVAL),
        parse_mode="Markdown",
    )

# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND JOB — Price checker
# ══════════════════════════════════════════════════════════════════════════════

async def job_check_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs every CHECK_INTERVAL seconds. Fires alerts whose targets are hit."""
    current = get_price()
    if current is None:
        logger.warning("Price check: fetch failed")
        return

    rows = alert_all_active()
    logger.info("Price check: XAUUSD=%s  |  Active alerts: %d", fp(current), len(rows))

    for aid, cid, target, direction in rows:
        triggered = (
            (direction == "above" and current >= target) or
            (direction == "below" and current <= target)
        )
        if not triggered:
            continue

        emoji = dir_emoji(direction)
        msg = (
            f"🚨 *PRICE ALERT FIRED!*\n\n"
            f"{emoji} XAUUSD moved *{direction}* your target!\n\n"
            f"💰 Current:  `{fp(current)}`\n"
            f"🎯 Target:   `{fp(target)}`\n"
            f"📏 Diff:     `{fp(abs(current - target))}`\n"
            f"🕐 `{utc_now()}`\n\n"
            f"_Alert `#{aid}` has been auto-removed._\n"
            f"_Use /alert to set a new one._"
        )
        try:
            await context.bot.send_message(chat_id=cid, text=msg, parse_mode="Markdown")
            alert_deactivate(aid)
            logger.info("🔔  Alert #%d fired for chat %d at %s", aid, cid, fp(current))
        except Exception as exc:
            logger.error("Failed to notify chat %d (alert #%d): %s", cid, aid, exc)

# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    if not BOT_TOKEN:
        print()
        print("❌  BOT_TOKEN is not set!")
        print("   Get one from @BotFather on Telegram, then run:")
        print()
        print("   export BOT_TOKEN='1234567890:ABCdef...'")
        print("   python bot.py")
        print()
        return

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Register all command handlers
    handlers = [
        ("start",     cmd_start),
        ("price",     cmd_price),
        ("alert",     cmd_alert),
        ("alerts",    cmd_alerts),
        ("cancel",    cmd_cancel),
        ("cancelall", cmd_cancelall),
        ("help",      cmd_help),
    ]
    for name, fn in handlers:
        app.add_handler(CommandHandler(name, fn))

    # Start background price-check job
    app.job_queue.run_repeating(
        job_check_prices,
        interval = CHECK_INTERVAL,
        first    = 15,
        name     = "xauusd_price_check",
    )

    logger.info("🤖  Bot started  |  Interval: %ds  |  DB: %s", CHECK_INTERVAL, DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
