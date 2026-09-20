import logging
import asyncio
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Render Port Binding Dummy Web Server
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    logging.info(f"Dummy HTTP server listening on port {port}")
    server.serve_forever()

# Configuration
BOT_TOKEN = "8806387746:AAFQ8tQBLUBrE1psC5-jYJ18Aw8tTA0pzk8"
ADMIN_USERNAME = "Trusted_zone_1122"
ADMIN_ID = 7624991230

# Memory Database
user_balances = {}       
card_stock = {}          
settings = {
    "price": 30.0,
    "bkash": "নম্বর সেট করা হয়নি",
    "nagad": "নম্বর সেট করা হয়নি"
}

# ----------------- USER COMMANDS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if user_id not in user_balances:
        user_balances[user_id] = 0.0

    keyboard = [
        [InlineKeyboardButton("🔍 Search BIN / Stock", callback_data="check_stock_user")],
        [InlineKeyboardButton("💰 My Balance", callback_data="my_balance"), InlineKeyboardButton("➕ Add Balance Info", callback_data="add_balance_info")],
        [InlineKeyboardButton("👤 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 হ্যালো {user.first_name}!\n\n"
        f"আমাদের অটোমেটেড ফেসবুক এডস কার্ড বটে স্বাগতম।\n"
        f"এখানে আপনি বিভিন্ন BIN-এর কার্ড অটোমেটিক কিনতে পারবেন।\n\n"
        f"📌 **প্রতি কার্ডের বর্তমান মূল্য:** {settings['price']} BDT\n"
        f"💳 **আপনার বর্তমান ব্যালেন্স:** {user_balances[user_id]} BDT"
    )

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "my_balance":
        bal = user_balances.get(user_id, 0.0)
        await query.message.reply_text(f"💰 **আপনার বর্তমান ব্যালেন্স:** {bal} BDT", parse_mode="Markdown")

    elif query.data == "add_balance_info":
        payment_text = (
            f"➕ **ব্যালেন্স অ্যাড করার নিয়ম:**\n\n"
            f"নিচের বিকাশ বা নগদ নম্বরে টাকা সেন্ড মানি করুন:\n"
            f"📱 **বিকাশ (Bkash):** `{settings['bkash']}`\n"
            f"📱 **নগদ (Nagad):** `{settings['nagad']}`\n\n"
            f"টাকা পাঠানোর পর এডমিনকে (@{ADMIN_USERNAME}) আপনার ইউজার আইডি (`{user_id}`) এবং ট্রানজেকশন আইডি পাঠিয়ে ব্যালেন্স অ্যাড করে নিন।"
        )
        await query.message.reply_text(payment_text, parse_mode="Markdown")

    elif query.data == "check_stock_user":
        if not card_stock:
            await query.message.reply_text("📦 বর্তমানে কোনো কার্ড স্টকে নেই।")
            return

        text = f"📦 **বর্তমান স্টক তালিকা (প্রতি কার্ড {settings['price']} BDT):**\n\n"
        for bin_num, cards in card_stock.items():
            text += f"🔹 **BIN:** `{bin_num}` ➔ {len(cards)} টি উপলব্ধ\n"

        await query.message.reply_text(text, parse_mode="Markdown")

# ----------------- ADMIN COMMANDS -----------------

def is_admin(user_id):
    return user_id == ADMIN_ID

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ নিয়ম: `/addbalance <USER_ID> <AMOUNT>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
        user_balances[target_id] = user_balances.get(target_id, 0.0) + amount
        await update.message.reply_text(f"✅ ইউজার `{target_id}`-এর একাউন্টে {amount} BDT যোগ করা হয়েছে। নতুন ব্যালেন্স: {user_balances[target_id]} BDT", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ আইডি বা অ্যামাউন্ট ভুল দেওয়া হয়েছে।")

async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ নিয়ম: `/addcard <BIN> <CARD_DETAILS>`", parse_mode="Markdown")
        return
    bin_num = context.args[0]
    card_details = " ".join(context.args[1:])
    if bin_num not in card_stock:
        card_stock[bin_num] = []
    card_stock[bin_num].append(card_details)
    await update.message.reply_text(f"✅ ১টি কার্ড যোগ করা হয়েছে!\n📌 **BIN:** `{bin_num}`\n📦 মোট কার্ড: {len(card_stock[bin_num])} টি", parse_mode="Markdown")

async def add_cards_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    lines = [line.strip() for line in update.message.text.strip().split('\n') if line.strip()]
    first_line_parts = lines[0].split()
    if len(first_line_parts) < 2:
        await update.message.reply_text("⚠️ নিয়ম:\n`/addcards <BIN>`\n`card1|MM|YY|CVC`\n`card2|MM|YY|CVC`", parse_mode="Markdown")
        return
    bin_num = first_line_parts[1]
    card_lines = lines[1:]
    if not card_lines:
        await update.message.reply_text("⚠️ কমান্ডের নিচের লাইনগুলোতে কার্ড প্রদান করুন।")
        return
    if bin_num not in card_stock:
        card_stock[bin_num] = []
    for card in card_lines:
        card_stock[bin_num].append(card)
    await update.message.reply_text(f"✅ সফলভাবে **{len(card_lines)}** টি কার্ড যোগ করা হয়েছে!\n📌 **BIN:** `{bin_num}`\n📦 বর্তমান মোট স্টক: {len(card_stock[bin_num])} টি", parse_mode="Markdown")

async def clear_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/clearstock <BIN>`", parse_mode="Markdown")
        return
    bin_num = context.args[0]
    if bin_num in card_stock:
        del card_stock[bin_num]
        await update.message.reply_text(f"🗑️ BIN `{bin_num}`-এর সকল কার্ড ডিলিট করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ এই BIN-এ কোনো কার্ড পাওয়া যায়নি।")

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/setprice <PRICE>`", parse_mode="Markdown")
        return
    try:
        new_price = float(context.args[0])
        settings["price"] = new_price
        await update.message.reply_text(f"✅ কার্ডের নতুন মূল্য সেট করা হয়েছে: **{new_price} BDT**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন।")

async def set_bkash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/setbkash <NUMBER>`", parse_mode="Markdown")
        return
    settings["bkash"] = context.args[0]
    await update.message.reply_text(f"✅ বিকাশ নম্বর সেট করা হয়েছে: `{settings['bkash']}`", parse_mode="Markdown")

async def set_nagad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/setnagad <NUMBER>`", parse_mode="Markdown")
        return
    settings["nagad"] = context.args[0]
    await update.message.reply_text(f"✅ নগদ নম্বর সেট করা হয়েছে: `{settings['nagad']}`", parse_mode="Markdown")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    help_text = (
        "🛠️ **এডমিন কন্ট্রোল প্যানেল কমান্ডসমূহ:**\n\n"
        "💰 **ইউজার ব্যালেন্স যোগ করতে:**\n`/addbalance <USER_ID> <AMOUNT>`\n\n"
        "💳 **একটি কার্ড যোগ করতে:**\n`/addcard <BIN> <CARD_DETAILS>`\n\n"
        "📦 **একসাথে একাধিক কার্ড যোগ করতে:**\n`/addcards <BIN>`\n`card1`\n`card2`\n\n"
        "🗑️ **কোনো BIN-এর সব স্টক ডিলিট করতে:**\n`/clearstock <BIN>`\n\n"
        "🏷️ **কার্ডের দাম পরিবর্তন করতে:**\n`/setprice <AMOUNT>`\n\n"
        "📱 **বিকাশ নম্বর দিতে:**\n`/setbkash <NUMBER>`\n\n"
        "📱 **নগদ নম্বর দিতে:**\n`/setnagad <NUMBER>`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# Main Function
async def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("addcard", add_card))
    app.add_handler(CommandHandler("addcards", add_cards_bulk))
    app.add_handler(CommandHandler("clearstock", clear_stock))
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("setbkash", set_bkash))
    app.add_handler(CommandHandler("setnagad", set_nagad))
    app.add_handler(CommandHandler("adminhelp", admin_help))

    logging.info("Bot started successfully...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

def main():
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
