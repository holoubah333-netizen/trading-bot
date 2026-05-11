import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pybit.unified_trading import HTTP

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
BYBIT_API_KEY = os.environ['BYBIT_API_KEY']
BYBIT_API_SECRET = os.environ['BYBIT_API_SECRET']
ALLOWED_USER_ID = int(os.environ['ALLOWED_USER_ID'])
TESTNET = True

logging.basicConfig(
format=”%(asctime)s - %(name)s - %(levelname)s - %(message)s”,
level=logging.INFO
)

session = HTTP(
testnet=TESTNET,
api_key=BYBIT_API_KEY,
api_secret=BYBIT_API_SECRET,
)

def is_authorized(update: Update) -> bool:
return update.effective_user.id == ALLOWED_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
msg = (
“Bot de Trading Bybit\n\n”
“Commandes:\n”
“/buy SYMBOL MONTANT\n”
“/sell SYMBOL QTE\n”
“/balance\n”
“/price SYMBOL\n”
“/orders\n”
“/cancel ORDER_ID SYMBOL”
)
await update.message.reply_text(msg)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
try:
result = session.get_wallet_balance(accountType=“UNIFIED”)
coins = result[“result”][“list”][0][“coin”]
lines = [“Solde:\n”]
for coin in coins:
if float(coin.get(“walletBalance”, 0)) > 0:
lines.append(coin[“coin”] + “: “ + str(round(float(coin[“walletBalance”]), 4)))
await update.message.reply_text(”\n”.join(lines))
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
if not context.args:
await update.message.reply_text(“Usage: /price BTCUSDT”)
return
symbol = context.args[0].upper()
try:
result = session.get_tickers(category=“spot”, symbol=symbol)
ticker = result[“result”][“list”][0]
msg = symbol + “: $” + str(round(float(ticker[“lastPrice”]), 2))
await update.message.reply_text(msg)
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage: /buy BTCUSDT 100”)
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
await update.message.reply_text(“Achat place! ID: “ + result[“result”][“orderId”])
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage: /sell BTCUSDT 0.001”)
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
await update.message.reply_text(“Vente placee! ID: “ + result[“result”][“orderId”])
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
try:
result = session.get_open_orders(category=“spot”)
order_list = result[“result”][“list”]
if not order_list:
await update.message.reply_text(“Aucun ordre ouvert.”)
return
lines = [“Ordres ouverts:”]
for o in order_list:
lines.append(o[“symbol”] + “ “ + o[“side”] + “ “ + str(o[“qty”]))
await update.message.reply_text(”\n”.join(lines))
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“Acces refuse.”)
return
if len(context.args) < 2:
await update.message.reply_text(“Usage: /cancel ORDER_ID BTCUSDT”)
return
order_id = context.args[0]
symbol = context.args[1].upper()
try:
session.cancel_order(category=“spot”, symbol=symbol, orderId=order_id)
await update.message.reply_text(“Ordre annule: “ + order_id)
except Exception as e:
await update.message.reply_text(“Erreur: “ + str(e))

def main():
app = Application.builder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler(“start”, start))
app.add_handler(CommandHandler(“balance”, balance))
app.add_handler(CommandHandler(“price”, price))
app.add_handler(CommandHandler(“buy”, buy))
app.add_handler(CommandHandler(“sell”, sell))
app.add_handler(CommandHandler(“orders”, orders))
app.add_handler(CommandHandler(“cancel”, cancel))
print(“Bot demarre…”)
app.run_polling()

if **name** == “**main**”:
main()
