import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pybit.unified_trading import HTTP

# ─── Variables d'environnement ───────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
BYBIT_API_KEY   = os.environ["BYBIT_API_KEY"]
BYBIT_API_SECRET = os.environ["BYBIT_API_SECRET"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
TESTNET         = False

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Client Bybit ─────────────────────────────────────────────────────────────
session = HTTP(
    testnet=TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
)

# ─── Sécurité ─────────────────────────────────────────────────────────────────
def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    msg = (
        "🤖 *Bot de Trading Bybit*\n\n"
        "*Commandes disponibles:*\n"
        "`/buy SYMBOL MONTANT` — Achat Market\n"
        "`/sell SYMBOL QTE` — Vente Market\n"
        "`/balance` — Solde du wallet\n"
        "`/price SYMBOL` — Prix actuel\n"
        "`/orders` — Ordres ouverts\n"
        "`/cancel ORDER_ID SYMBOL` — Annuler un ordre"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── /balance ─────────────────────────────────────────────────────────────────
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    try:
        result = session.get_wallet_balance(accountType="UNIFIED")
        coins = result["result"]["list"][0]["coin"]
        lines = ["💼 *Solde:*\n"]
        for coin in coins:
            wallet_bal = float(coin.get("walletBalance", 0))
            if wallet_bal > 0:
                available = float(coin.get("availableToWithdraw", 0))
                lines.append(
                    f"  • *{coin['coin']}*: `{wallet_bal:.4f}`"
                    f"  (dispo: `{available:.4f}`)"
                )
        if len(lines) == 1:
            lines.append("  Aucun actif.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error("balance: %s", e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── /price ───────────────────────────────────────────────────────────────────
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/price BTCUSDT`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper()
    try:
        result = session.get_tickers(category="spot", symbol=symbol)
        ticker = result["result"]["list"][0]
        last   = float(ticker["lastPrice"])
        high   = float(ticker["highPrice24h"])
        low    = float(ticker["lowPrice24h"])
        vol    = float(ticker["volume24h"])
        msg = (
            f"📊 *{symbol}*\n"
            f"  Prix : `${last:,.2f}`\n"
            f"  24h ↑ : `${high:,.2f}`\n"
            f"  24h ↓ : `${low:,.2f}`\n"
            f"  Volume : `{vol:,.2f}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error("price(%s): %s", symbol, e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── /buy ─────────────────────────────────────────────────────────────────────
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/buy BTCUSDT 100`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper()
    qty    = context.args[1]
    try:
        result = session.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=qty,
        )
        order_id = result["result"]["orderId"]
        await update.message.reply_text(
            f"✅ *Achat placé!*\n  Paire: `{symbol}`\n  Qté: `{qty}`\n  ID: `{order_id}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("buy(%s, %s): %s", symbol, qty, e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── /sell ────────────────────────────────────────────────────────────────────
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/sell BTCUSDT 0.001`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper()
    qty    = context.args[1]
    try:
        result = session.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=qty,
        )
        order_id = result["result"]["orderId"]
        await update.message.reply_text(
            f"✅ *Vente placée!*\n  Paire: `{symbol}`\n  Qté: `{qty}`\n  ID: `{order_id}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("sell(%s, %s): %s", symbol, qty, e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── /orders ──────────────────────────────────────────────────────────────────
async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    try:
        result = session.get_open_orders(category="spot")
        order_list = result["result"]["list"]
        if not order_list:
            await update.message.reply_text("📭 Aucun ordre ouvert.")
            return
        lines = ["📋 *Ordres ouverts:*\n"]
        for o in order_list:
            lines.append(
                f"  • `{o['orderId'][:8]}...`"
                f"  {o['symbol']} {o['side']} `{o['qty']}`"
                f"  @ `{o.get('price', 'Market')}`"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error("orders: %s", e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── /cancel ──────────────────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/cancel ORDER_ID BTCUSDT`", parse_mode="Markdown"
        )
        return
    order_id = context.args[0]
    symbol   = context.args[1].upper()
    try:
        session.cancel_order(category="spot", symbol=symbol, orderId=order_id)
        await update.message.reply_text(
            f"🗑️ Ordre annulé: `{order_id}`", parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("cancel(%s, %s): %s", order_id, symbol, e)
        await update.message.reply_text(f"❌ Erreur: `{e}`", parse_mode="Markdown")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("Démarrage du bot (testnet=%s)", TESTNET)
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("price",   price))
    app.add_handler(CommandHandler("buy",     buy))
    app.add_handler(CommandHandler("sell",    sell))
    app.add_handler(CommandHandler("orders",  orders))
    app.add_handler(CommandHandler("cancel",  cancel))

    logger.info("Bot en écoute...")
    app.run_polling()

if __name__ == "__main__":
    main()
