import logging
import asyncio
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
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

# Configuration (Updated with your new token)
BOT_TOKEN = "8806387746:AAEVNVLEClAJ-7lHy8GfESUwC8q-VoYR-Wc"
ADMIN_USERNAME = "Trusted_zone_1122"
ADMIN_ID = 7624991230

# Memory Database
user_balances = {}       
card_stock = {}          
user_states = {}  # Track user search state
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
        [InlineKeyboardButton("🔍 Search BIN / Stock & Buy", callback_data="start_search_bin")],
        [InlineKeyboardButton("💰 My Balance", callback_data="my_balance"), InlineKeyboardButton("➕ Add Balance Info", callback_data="add_balance_info")],
        [InlineKeyboardButton("👤 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 হ্যালো {user.first_name}!\n\n"
        f"আমাদের অটোমেটেড ফেসবুক এডস কার্ড বটে স্বাগতম।\n"
        f"এখানে আপনি বিভিন্ন BIN-এর কার্ড অটোমেটিক কিনতে পারবেন।\n\n"
        f"📌 **প্রতি কার্ডের বর্তমান মূল্য:** {settings['price']} BDT\n"
        f"💳 **আপনার বর্তমান ব্যালেন্স:** {user_balances[user_id]} BDT\n"
        f"🆔 **আপনার ইউজার আইডি:** `{user_id}`"
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
        await query.message.reply_text(f"💰 **আপনার বর্তমান ব্যালেন্স:** {bal} BDT\n🆔 **আপনার আইডি:** `{user_id}`", parse_mode="Markdown")

    elif query.data == "add_balance_info":
        payment_text = (
            f"➕ **ব্যালেন্স অ্যাড করার নিয়ম:**\n\n"
            f"নিচের বিকাশ বা নগদ নম্বরে টাকা সেন্ড মানি করুন:\n"
            f"📱 **বিকাশ (Bkash):** `{settings['bkash']}`\n"
            f"📱 **নগদ (Nagad):** `{settings['nagad']}`\n\n"
            f"টাকা পাঠানোর পর এডমিনকে (@{ADMIN_USERNAME}) আপনার ইউজার আইডি (`{user_id}`) এবং ট্রানজেকশন আইডি পাঠিয়ে ব্যালেন্স অ্যাড করে নিন।"
        )
        await query.message.reply_text(payment_text, parse_mode="Markdown")

    elif query.data == "start_search_bin":
        user_states[user_id] = "WAITING_FOR_BIN"
        keyboard = [[InlineKeyboardButton("📦 বর্তমান সব স্টক একসাথে দেখুন", callback_data="show_all_stock")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "🔍 **যে BIN-এর কার্ড খুঁজতে চান তা মেসেজে টাইপ করে পাঠান:**\n"
            "(উদাহরণ: `414720`)\n\n"
            "অথবা সব স্টক একবারে দেখতে নিচের বাটনে চাপ দিন:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "show_all_stock":
        if not card_stock:
            await query.message.reply_text("📦 বর্তমানে কোনো কার্ড স্টকে নেই।")
            return

        keyboard = []
        for bin_num, cards in card_stock.items():
            if len(cards) > 0:
                keyboard.append([InlineKeyboardButton(f"🔹 BIN {bin_num} ({len(cards)} টি আছে)", callback_data=f"checkbin_{bin_num}")])

        if not keyboard:
            await query.message.reply_text("📦 বর্তমানে সকল BIN-এর স্টক খালি।")
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("📦 **বর্তমান উপলব্ধ BIN স্টক তালিকা:**\nপছন্দের BIN-টিতে চাপ দিন:", reply_markup=reply_markup)

    elif query.data.startswith("checkbin_"):
        bin_num = query.data.split("_")[1]
        await process_bin_check(query.message, user_id, bin_num)

    elif query.data.startswith("buy_"):
        parts = query.data.split("_")
        bin_num = parts[1]
        qty = int(parts[2])

        if bin_num not in card_stock or len(card_stock[bin_num]) < qty:
            await query.message.reply_text("❌ দুঃখিত, কাঙ্ক্ষিত পরিমাণের কার্ড বর্তমানে স্টকে নেই।")
            return

        price_per_card = settings["price"]
        total_cost = price_per_card * qty
        current_bal = user_balances.get(user_id, 0.0)

        if current_bal < total_cost:
            await query.message.reply_text(
                f"❌ **পর্যাপ্ত ব্যালেন্স নেই!**\n\n"
                f"📊 **প্রয়োজনীয় ব্যালেন্স:** {total_cost} BDT ({qty} টি কার্ডের জন্য)\n"
                f"💳 **আপনার বর্তমান ব্যালেন্স:** {current_bal} BDT\n\n"
                f"টাকা রিচার্জ করতে **Add Balance Info** মেনু দেখুন।",
                parse_mode="Markdown"
            )
            return

        user_balances[user_id] -= total_cost

        delivered_cards = []
        for _ in range(qty):
            delivered_cards.append(card_stock[bin_num].pop(0))

        cards_text = "\n".join([f"`{c}`" for c in delivered_cards])

        await query.message.reply_text(
            f"🎉 **কার্ড ক্রয় সফল হয়েছে! ({qty} টি)**\n\n"
            f"📌 **BIN:** `{bin_num}`\n"
            f"💳 **কার্ডসমূহ:**\n{cards_text}\n\n"
            f"💰 **মোট খরচ:** {total_cost} BDT\n"
            f"💳 **অবশিষ্ট ব্যালেন্স:** {user_balances[user_id]} BDT\n\n"
            f"ধন্যবাদ আমাদের পরিষেবা ব্যবহার করার জন্য!",
            parse_mode="Markdown"
        )

async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_states.get(user_id) == "WAITING_FOR_BIN":
        user_states[user_id] = None
        bin_num = text.split()[0]
        await process_bin_check(update.message, user_id, bin_num)

async def process_bin_check(message_obj, user_id, bin_num):
    if bin_num not in card_stock or len(card_stock[bin_num]) == 0:
        await message_obj.reply_text(
            f"❌ **দুঃখিত!** BIN `{bin_num}`-এর কোনো কার্ড বর্তমানে স্টকে এভেলেবেল নেই।",
            parse_mode="Markdown"
        )
        return

    available_qty = len(card_stock[bin_num])
    price_per_card = settings["price"]

    qty_options = [1, 2, 3, 5, 10]
    keyboard = []
    row = []

    for q in qty_options:
        if q <= available_qty:
            row.append(InlineKeyboardButton(f"🛒 {q} টি কিনুন ({q * price_per_card} BDT)", callback_data=f"buy_{bin_num}_{q}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await message_obj.reply_text(
        f"✅ **BIN {bin_num} এভেলেবেল আছে!**\n\n"
        f"📦 **বর্তমানে স্টকে আছে:** {available_qty} টি\n"
        f"📌 **প্রতিটি কার্ডের মূল্য:** {price_per_card} BDT\n\n"
        f"👇 **আপনি কয়টি কার্ড কিনতে চান সিলেক্ট করুন:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

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
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_text))
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
