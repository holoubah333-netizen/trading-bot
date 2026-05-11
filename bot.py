import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pybit.unified_trading import HTTP

# ============================================================

# CONFIGURATION — Remplace par tes vraies clés

# ============================================================

import os
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BYBIT_API_KEY = os.environ["BYBIT_API_KEY"]
BYBIT_API_SECRET = os.environ["BYBIT_API_SECRET"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
TESTNET = True
  # Mets False pour le vrai trading !

# ============================================================

logging.basicConfig(
format=”%(asctime)s - %(name)s - %(levelname)s - %(message)s”,
level=logging.INFO
)

# Connexion Bybit

session = HTTP(
testnet=TESTNET,
api_key=BYBIT_API_KEY,
api_secret=BYBIT_API_SECRET,
)

def is_authorized(update: Update) -> bool:
“”“Vérifie que c’est bien toi qui commandes le bot.”””
return update.effective_user.id == ALLOWED_USER_ID

# ============================================================

# COMMANDES

# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
msg = (
“🤖 *Bot de Trading Bybit*\n\n”
“Commandes disponibles :\n”
“/buy `SYMBOL MONTANT` — Acheter\n”
“/sell `SYMBOL MONTANT` — Vendre\n”
“/balance — Voir ton solde\n”
“/price `SYMBOL` — Prix en temps réel\n”
“/orders — Ordres ouverts\n”
“/cancel `ORDER_ID SYMBOL` — Annuler un ordre\n\n”
“Exemple : `/buy BTCUSDT 100`”
)
await update.message.reply_text(msg, parse_mode=“Markdown”)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
try:
result = session.get_wallet_balance(accountType=“UNIFIED”)
coins = result[“result”][“list”][0][“coin”]
lines = [“💰 *Solde du compte :*\n”]
for coin in coins:
if float(coin.get(“walletBalance”, 0)) > 0:
lines.append(
f”• *{coin[‘coin’]}* : {float(coin[‘walletBalance’]):.4f}”
f” (≈ ${float(coin.get(‘usdValue’, 0)):.2f})”
)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
if not context.args:
await update.message.reply_text(“Usage : /price BTCUSDT”)
return
symbol = context.args[0].upper()
try:
result = session.get_tickers(category=“spot”, symbol=symbol)
ticker = result[“result”][“list”][0]
msg = (
f”📊 *{symbol}*\n”
f”Prix : `${float(ticker['lastPrice']):,.2f}`\n”
f”24h : `{float(ticker['price24hPcnt'])*100:.2f}%`\n”
f”Haut 24h : `${float(ticker['highPrice24h']):,.2f}`\n”
f”Bas 24h : `${float(ticker['lowPrice24h']):,.2f}`”
)
await update.message.reply_text(msg, parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage : /buy BTCUSDT 100”)
return
symbol = context.args[0].upper()
qty = context.args[1]
try:
result = session.place_order(
category=“spot”,
symbol=symbol,
side=“Buy”,
orderType=“Market”,
qty=qty,
)
order_id = result[“result”][“orderId”]
await update.message.reply_text(
f”✅ *Ordre d’achat placé !*\n”
f”Symbole : `{symbol}`\n”
f”Montant : `{qty} USDT`\n”
f”Order ID : `{order_id}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage : /sell BTCUSDT 0.001”)
return
symbol = context.args[0].upper()
qty = context.args[1]
try:
result = session.place_order(
category=“spot”,
symbol=symbol,
side=“Sell”,
orderType=“Market”,
qty=qty,
)
order_id = result[“result”][“orderId”]
await update.message.reply_text(
f”✅ *Ordre de vente placé !*\n”
f”Symbole : `{symbol}`\n”
f”Quantité : `{qty}`\n”
f”Order ID : `{order_id}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
try:
result = session.get_open_orders(category=“spot”)
order_list = result[“result”][“list”]
if not order_list:
await update.message.reply_text(“📭 Aucun ordre ouvert.”)
return
lines = [“📋 *Ordres ouverts :*\n”]
for o in order_list:
lines.append(
f”• `{o['symbol']}` | {o[‘side’]} | {o[‘qty’]} | “
f”Prix : {o.get(‘price’, ‘Market’)} | ID : `{o['orderId']}`”
)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“❌ Accès refusé.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage : /cancel ORDER_ID BTCUSDT”)
return
order_id = context.args[0]
symbol = context.args[1].upper()
try:
session.cancel_order(category=“spot”, symbol=symbol, orderId=order_id)
await update.message.reply_text(f”✅ Ordre `{order_id}` annulé.”, parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Erreur : {e}”)

# ============================================================

# LANCEMENT

# ============================================================

def main():
app = Application.builder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler(“start”, start))
app.add_handler(CommandHandler(“balance”, balance))
app.add_handler(CommandHandler(“price”, price))
app.add_handler(CommandHandler(“buy”, buy))
app.add_handler(CommandHandler(“sell”, sell))
app.add_handler(CommandHandler(“orders”, orders))
app.add_handler(CommandHandler(“cancel”, cancel))
print(“🚀 Bot démarré…”)
app.run_polling()

if **name** == “**main**”:
main()
