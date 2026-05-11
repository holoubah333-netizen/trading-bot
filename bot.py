"""
Bot de Trading Telegram pour Bybit
====================================
Variables d'environnement requises (.env):
  TELEGRAM_TOKEN       - Token du bot Telegram (@BotFather)
  TELEGRAM_CHAT_ID     - Ton Chat ID Telegram
  BYBIT_API_KEY        - Clé API Bybit
  BYBIT_API_SECRET     - Secret API Bybit
  BYBIT_TESTNET        - "true" pour le testnet, "false" pour le mainnet

Installation:
  pip install python-telegram-bot pybit python-dotenv

Lancement:
  python bybit_telegram_bot.py
"""

import os
import logging
import asyncio
from decimal import Decimal
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from pybit.unified_trading import HTTP

# ─── Chargement des variables d'environnement ────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID  = os.environ["TELEGRAM_CHAT_ID"]
BYBIT_API_KEY     = os.environ["BYBIT_API_KEY"]
BYBIT_API_SECRET  = os.environ["BYBIT_API_SECRET"]
BYBIT_TESTNET     = os.environ.get("BYBIT_TESTNET", "false").lower() == "true"

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Client Bybit ─────────────────────────────────────────────────────────────
session = HTTP(
    testnet=BYBIT_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
)

# ─── États ConversationHandler ────────────────────────────────────────────────
(
    CHOOSE_ACTION,
    ENTER_SYMBOL,
    ENTER_QTY,
    ENTER_PRICE,
    CONFIRM_ORDER,
) = range(5)

# Stockage temporaire de l'ordre en cours
pending_orders: dict = {}


# ─── Sécurité : seul l'owner peut utiliser le bot ─────────────────────────────
def restricted(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        if user_id != TELEGRAM_CHAT_ID:
            await update.message.reply_text("⛔ Accès refusé.")
            logger.warning("Accès refusé pour user_id=%s", user_id)
            return
        return await func(update, context, *args, **kwargs)
    wrapped.__name__ = func.__name__
    return wrapped


# ─── Helpers Bybit ────────────────────────────────────────────────────────────
def get_balance() -> str:
    try:
        r = session.get_wallet_balance(accountType="UNIFIED")
        coins = r["result"]["list"][0]["coin"]
        lines = []
        for c in coins:
            if float(c.get("walletBalance", 0)) > 0:
                lines.append(
                    f"  • {c['coin']}: {float(c['walletBalance']):.4f}"
                    f"  (dispo: {float(c.get('availableToWithdraw', 0)):.4f})"
                )
        return "💼 *Solde du portefeuille:*\n" + ("\n".join(lines) if lines else "  Aucun actif")
    except Exception as e:
        logger.error("get_balance: %s", e)
        return f"❌ Erreur solde: {e}"


def get_price(symbol: str) -> str:
    try:
        r = session.get_tickers(category="linear", symbol=symbol.upper())
        t = r["result"]["list"][0]
        return (
            f"📊 *{symbol.upper()}*\n"
            f"  Prix: `{t['lastPrice']}`\n"
            f"  24h Haut: `{t['highPrice24h']}`\n"
            f"  24h Bas: `{t['lowPrice24h']}`\n"
            f"  Volume 24h: `{float(t['volume24h']):.2f}`"
        )
    except Exception as e:
        logger.error("get_price(%s): %s", symbol, e)
        return f"❌ Symbole introuvable: {symbol}"


def get_positions() -> str:
    try:
        r = session.get_positions(category="linear", settleCoin="USDT")
        positions = [p for p in r["result"]["list"] if float(p.get("size", 0)) > 0]
        if not positions:
            return "📭 Aucune position ouverte."
        lines = ["📈 *Positions ouvertes:*"]
        for p in positions:
            pnl = float(p.get("unrealisedPnl", 0))
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(
                f"\n  {emoji} *{p['symbol']}* ({p['side']})\n"
                f"     Taille: `{p['size']}`  |  PNL: `{pnl:+.2f} USDT`\n"
                f"     Entrée: `{p['avgPrice']}`  |  Liq: `{p['liqPrice']}`"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("get_positions: %s", e)
        return f"❌ Erreur positions: {e}"


def place_order(symbol: str, side: str, qty: str, price: str | None = None) -> str:
    try:
        params = dict(
            category="linear",
            symbol=symbol.upper(),
            side=side,          # "Buy" ou "Sell"
            orderType="Market" if not price else "Limit",
            qty=qty,
        )
        if price:
            params["price"] = price
            params["timeInForce"] = "GTC"

        r = session.place_order(**params)
        oid = r["result"]["orderId"]
        return (
            f"✅ Ordre passé!\n"
            f"  ID: `{oid}`\n"
            f"  {side} {qty} {symbol.upper()}"
            + (f" @ {price}" if price else " (Market)")
        )
    except Exception as e:
        logger.error("place_order: %s", e)
        return f"❌ Erreur ordre: {e}"


def cancel_all(symbol: str = "") -> str:
    try:
        params = dict(category="linear")
        if symbol:
            params["symbol"] = symbol.upper()
        r = session.cancel_all_orders(**params)
        count = len(r["result"].get("list", []))
        return f"🗑️ {count} ordre(s) annulé(s)" + (f" sur {symbol.upper()}" if symbol else "")
    except Exception as e:
        logger.error("cancel_all: %s", e)
        return f"❌ Erreur annulation: {e}"


# ─── Commandes Telegram ───────────────────────────────────────────────────────

@restricted
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💼 Solde",      callback_data="balance"),
         InlineKeyboardButton("📈 Positions",  callback_data="positions")],
        [InlineKeyboardButton("🟢 Acheter",    callback_data="buy"),
         InlineKeyboardButton("🔴 Vendre",     callback_data="sell")],
        [InlineKeyboardButton("📊 Prix",       callback_data="price"),
         InlineKeyboardButton("🗑️ Annuler tout", callback_data="cancel_all")],
        [InlineKeyboardButton("❓ Aide",        callback_data="help")],
    ]
    await update.message.reply_text(
        "🤖 *Bybit Trading Bot*\n\nChoisissez une action:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@restricted
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_balance(), parse_mode="Markdown")


@restricted
async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_positions(), parse_mode="Markdown")


@restricted
async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/price BTCUSDT`", parse_mode="Markdown")
        return
    await update.message.reply_text(get_price(args[0]), parse_mode="Markdown")


@restricted
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else ""
    await update.message.reply_text(cancel_all(symbol), parse_mode="Markdown")


@restricted
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commandes disponibles:*\n\n"
        "`/start`   – Menu principal\n"
        "`/balance` – Solde du portefeuille\n"
        "`/positions` – Positions ouvertes\n"
        "`/price BTCUSDT` – Prix d'une paire\n"
        "`/buy BTCUSDT 0.001` – Ordre Market Achat\n"
        "`/sell BTCUSDT 0.001` – Ordre Market Vente\n"
        "`/limit buy BTCUSDT 0.001 60000` – Ordre Limit\n"
        "`/cancel [SYMBOL]` – Annuler ordres\n",
        parse_mode="Markdown",
    )


@restricted
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /buy BTCUSDT 0.001"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/buy BTCUSDT 0.001`", parse_mode="Markdown")
        return
    symbol, qty = args[0], args[1]
    result = place_order(symbol, "Buy", qty)
    await update.message.reply_text(result, parse_mode="Markdown")


@restricted
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /sell BTCUSDT 0.001"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/sell BTCUSDT 0.001`", parse_mode="Markdown")
        return
    symbol, qty = args[0], args[1]
    result = place_order(symbol, "Sell", qty)
    await update.message.reply_text(result, parse_mode="Markdown")


@restricted
async def cmd_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /limit buy BTCUSDT 0.001 60000"""
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Usage: `/limit buy BTCUSDT 0.001 60000`", parse_mode="Markdown"
        )
        return
    side_raw, symbol, qty, price = args[0], args[1], args[2], args[3]
    side = "Buy" if side_raw.lower() == "buy" else "Sell"
    result = place_order(symbol, side, qty, price)
    await update.message.reply_text(result, parse_mode="Markdown")


# ─── Callbacks boutons inline ─────────────────────────────────────────────────

@restricted
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "balance":
        await query.edit_message_text(get_balance(), parse_mode="Markdown")

    elif data == "positions":
        await query.edit_message_text(get_positions(), parse_mode="Markdown")

    elif data in ("buy", "sell"):
        context.user_data["side"] = "Buy" if data == "buy" else "Sell"
        await query.edit_message_text(
            f"{'🟢 Achat' if data == 'buy' else '🔴 Vente'}\n\nEntrez le symbole (ex: `BTCUSDT`):",
            parse_mode="Markdown",
        )
        return ENTER_SYMBOL

    elif data == "price":
        await query.edit_message_text("Entrez le symbole (ex: `BTCUSDT`):", parse_mode="Markdown")
        context.user_data["action"] = "price"
        return ENTER_SYMBOL

    elif data == "cancel_all":
        await query.edit_message_text(cancel_all(), parse_mode="Markdown")

    elif data == "help":
        await query.edit_message_text(
            "📖 *Commandes:*\n`/buy` `/sell` `/limit` `/price` `/balance` `/positions` `/cancel`",
            parse_mode="Markdown",
        )

    elif data == "confirm_yes":
        od = context.user_data.get("order", {})
        result = place_order(od["symbol"], od["side"], od["qty"], od.get("price"))
        await query.edit_message_text(result, parse_mode="Markdown")
        return ConversationHandler.END

    elif data == "confirm_no":
        await query.edit_message_text("❌ Ordre annulé.", parse_mode="Markdown")
        return ConversationHandler.END


# ─── ConversationHandler steps ────────────────────────────────────────────────

async def step_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip().upper()
    context.user_data["symbol"] = symbol

    if context.user_data.get("action") == "price":
        await update.message.reply_text(get_price(symbol), parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(f"Quantité pour *{symbol}* :", parse_mode="Markdown")
    return ENTER_QTY


async def step_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qty = update.message.text.strip()
    context.user_data["qty"] = qty
    await update.message.reply_text(
        "Prix limite (laisser vide pour ordre *Market*):",
        parse_mode="Markdown",
    )
    return ENTER_PRICE


async def step_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text.strip()
    price = price_text if price_text.lower() not in ("", "market", "/") else None
    context.user_data["price"] = price

    od = context.user_data
    order_type = f"Limit @ {price}" if price else "Market"
    summary = (
        f"📋 *Confirmation de l'ordre*\n\n"
        f"  Paire : `{od['symbol']}`\n"
        f"  Côté  : `{od['side']}`\n"
        f"  Qté   : `{od['qty']}`\n"
        f"  Type  : `{order_type}`\n\n"
        "Confirmer ?"
    )
    context.user_data["order"] = {
        "symbol": od["symbol"],
        "side": od["side"],
        "qty": od["qty"],
        "price": price,
    }
    kb = [[
        InlineKeyboardButton("✅ Oui", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Non", callback_data="confirm_no"),
    ]]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return CONFIRM_ORDER


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Opération annulée.")
    return ConversationHandler.END


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("Démarrage du bot (testnet=%s)", BYBIT_TESTNET)
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^(buy|sell|price)$")],
        states={
            ENTER_SYMBOL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, step_symbol)],
            ENTER_QTY:     [MessageHandler(filters.TEXT & ~filters.COMMAND, step_qty)],
            ENTER_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, step_price)],
            CONFIRM_ORDER: [CallbackQueryHandler(button_callback, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("balance",   cmd_balance))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("price",     cmd_price))
    app.add_handler(CommandHandler("buy",       cmd_buy))
    app.add_handler(CommandHandler("sell",      cmd_sell))
    app.add_handler(CommandHandler("limit",     cmd_limit))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot en écoute...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
