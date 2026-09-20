import logging
import asyncio
import os
import sqlite3
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

# Configuration
BOT_TOKEN = "8806387746:AAEVNVLEClAJ-7lHy8GfESUwC8q-VoYR-Wc"
ADMIN_USERNAME = "Trusted_zone_1122"
ADMIN_ID = 7624991230

# Database Initialization
DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # User Balances Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    ''')
    # Card Stock Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin TEXT,
            card_details TEXT
        )
    ''')
    # Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Default settings insert
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '30.0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bkash', 'নম্বর সেট করা হয়নি')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('nagad', 'নম্বর সেট করা হয়নি')")
    conn.commit()
    conn.close()

# Database Helper Functions
def get_user_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, 0.0)", (user_id,))
        conn.commit()
        bal = 0.0
    else:
        bal = row[0]
    conn.close()
    return bal

def update_user_balance(user_id, amount_change):
    current = get_user_balance(user_id)
    new_bal = current + amount_change
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, user_id))
    conn.commit()
    conn.close()
    return new_bal

def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (str(value), key))
    conn.commit()
    conn.close()

def get_cards_by_bin(bin_num):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, card_details FROM cards WHERE bin = ?", (bin_num,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_bins():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT bin, COUNT(*) FROM cards GROUP BY bin")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_single_card(bin_num, card_details):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cards (bin, card_details) VALUES (?, ?)", (bin_num, card_details))
    conn.commit()
    conn.close()

def pop_cards(bin_num, qty):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, card_details FROM cards WHERE bin = ? LIMIT ?", (bin_num, qty))
    rows = cursor.fetchall()
    
    delivered = []
    ids_to_delete = []
    for r in rows:
        ids_to_delete.append(r[0])
        delivered.append(r[1])
        
    if ids_to_delete:
        cursor.execute(f"DELETE FROM cards WHERE id IN ({','.join(['?']*len(ids_to_delete))})", ids_to_delete)
        conn.commit()
    conn.close()
    return delivered

def delete_bin_stock(bin_num):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cards WHERE bin = ?", (bin_num,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

user_states = {}

# ----------------- USER COMMANDS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    balance = get_user_balance(user_id)
    price = get_setting("price")

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
        f"📌 **প্রতি কার্ডের বর্তমান মূল্য:** {price} BDT\n"
        f"💳 **আপনার বর্তমান ব্যালেন্স:** {balance} BDT\n"
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
        bal = get_user_balance(user_id)
        await query.message.reply_text(f"💰 **আপনার বর্তমান ব্যালেন্স:** {bal} BDT\n🆔 **আপনার আইডি:** `{user_id}`", parse_mode="Markdown")

    elif query.data == "add_balance_info":
        bkash = get_setting("bkash")
        nagad = get_setting("nagad")
        payment_text = (
            f"➕ **ব্যালেন্স অ্যাড করার নিয়ম:**\n\n"
            f"নিচের বিকাশ বা নগদ নম্বরে টাকা সেন্ড মানি করুন:\n"
            f"📱 **বিকাশ (Bkash):** `{bkash}`\n"
            f"📱 **নগদ (Nagad):** `{nagad}`\n\n"
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
        bins = get_all_bins()
        if not bins:
            await query.message.reply_text("📦 বর্তমানে কোনো কার্ড স্টকে নেই।")
            return

        keyboard = []
        for bin_num, count in bins:
            if count > 0:
                keyboard.append([InlineKeyboardButton(f"🔹 BIN {bin_num} ({count} টি আছে)", callback_data=f"checkbin_{bin_num}")])

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

        cards = get_cards_by_bin(bin_num)
        if len(cards) < qty:
            await query.message.reply_text("❌ দুঃখিত, কাঙ্ক্ষিত পরিমাণের কার্ড বর্তমানে স্টকে নেই।")
            return

        price_per_card = float(get_setting("price"))
        total_cost = price_per_card * qty
        current_bal = get_user_balance(user_id)

        if current_bal < total_cost:
            await query.message.reply_text(
                f"❌ **পর্যাপ্ত ব্যালেন্স নেই!**\n\n"
                f"📊 **প্রয়োজনীয় ব্যালেন্স:** {total_cost} BDT ({qty} টি কার্ডের জন্য)\n"
                f"💳 **আপনার বর্তমান ব্যালেন্স:** {current_bal} BDT\n\n"
                f"টাকা রিচার্জ করতে **Add Balance Info** মেনু দেখুন।",
                parse_mode="Markdown"
            )
            return

        update_user_balance(user_id, -total_cost)
        delivered_cards = pop_cards(bin_num, qty)
        cards_text = "\n".join([f"`{c}`" for c in delivered_cards])
        rem_bal = get_user_balance(user_id)

        await query.message.reply_text(
            f"🎉 **কার্ড ক্রয় সফল হয়েছে! ({qty} টি)**\n\n"
            f"📌 **BIN:** `{bin_num}`\n"
            f"💳 **কার্ডসমূহ:**\n{cards_text}\n\n"
            f"💰 **মোট খরচ:** {total_cost} BDT\n"
            f"💳 **অবশিষ্ট ব্যালেন্স:** {rem_bal} BDT\n\n"
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
    cards = get_cards_by_bin(bin_num)
    if not cards:
        await message_obj.reply_text(
            f"❌ **দুঃখিত!** BIN `{bin_num}`-এর কোনো কার্ড বর্তমানে স্টকে এভেলেবেল নেই।",
            parse_mode="Markdown"
        )
        return

    available_qty = len(cards)
    price_per_card = float(get_setting("price"))

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
        new_bal = update_user_balance(target_id, amount)
        await update.message.reply_text(f"✅ ইউজার `{target_id}`-এর একাউন্টে {amount} BDT যোগ করা হয়েছে। নতুন ব্যালেন্স: {new_bal} BDT", parse_mode="Markdown")
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
    add_single_card(bin_num, card_details)
    total_count = len(get_cards_by_bin(bin_num))
    await update.message.reply_text(f"✅ ১টি কার্ড যোগ করা হয়েছে!\n📌 **BIN:** `{bin_num}`\n📦 মোট কার্ড: {total_count} টি", parse_mode="Markdown")

async def add_cards_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    full_text = update.message.text.strip()
    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    
    first_line_parts = lines[0].split()
    if len(first_line_parts) < 2:
        await update.message.reply_text(
            "⚠️ **বাল্ক কার্ড এড করার সঠিক নিয়ম:**\n\n"
            "`/addcards 414720`\n"
            "`4147200000000000|05|28|123`\n"
            "`4147200000000001|05|28|124`", 
            parse_mode="Markdown"
        )
        return
    
    bin_num = first_line_parts[1].strip()
    cards_to_add = lines[1:]
    
    if not cards_to_add:
        await update.message.reply_text("⚠️ প্রথম লাইনের নিচে কোনো কার্ডের বিবরণ দেওয়া হয়নি।")
        return

    added_count = 0
    for card in cards_to_add:
        if card:
            add_single_card(bin_num, card)
            added_count += 1

    total_count = len(get_cards_by_bin(bin_num))
    await update.message.reply_text(
        f"✅ **সফলভাবে {added_count} টি কার্ড যোগ করা হয়েছে!**\n\n"
        f"📌 **BIN:** `{bin_num}`\n"
        f"📦 **বর্তমান মোট স্টক:** {total_count} টি", 
        parse_mode="Markdown"
    )

async def clear_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/clearstock <BIN>`", parse_mode="Markdown")
        return
    bin_num = context.args[0]
    count = delete_bin_stock(bin_num)
    if count > 0:
        await update.message.reply_text(f"🗑️ BIN `{bin_num}`-এর সকল ({count} টি) কার্ড ডিলিট করা হয়েছে।", parse_mode="Markdown")
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
        set_setting("price", str(new_price))
        await update.message.reply_text(f"✅ কার্ডের নতুন মূল্য সেট করা হয়েছে: **{new_price} BDT**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন।")

async def set_bkash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/setbkash <NUMBER>`", parse_mode="Markdown")
        return
    num = context.args[0]
    set_setting("bkash", num)
    await update.message.reply_text(f"✅ বিকাশ নম্বর সেট করা হয়েছে: `{num}`", parse_mode="Markdown")

async def set_nagad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ নিয়ম: `/setnagad <NUMBER>`", parse_mode="Markdown")
        return
    num = context.args[0]
    set_setting("nagad", num)
    await update.message.reply_text(f"✅ নগদ নম্বর সেট করা হয়েছে: `{num}`", parse_mode="Markdown")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    help_text = (
        "🛠️ **এডমিন কন্ট্রোল প্যানেল কমান্ডসমূহ:**\n\n"
        "💰 **ইউজার ব্যালেন্স যোগ করতে:**\n`/addbalance <USER_ID> <AMOUNT>`\n\n"
        "💳 **একটি কার্ড যোগ করতে:**\n`/addcard <BIN> <CARD_DETAILS>`\n\n"
        "📦 **একসাথে একাধিক (Bulk) কার্ড যোগ করতে:**\n`/addcards <BIN>`\n`card1|MM|YY|CVC`\n`card2|MM|YY|CVC`\n\n"
        "🗑️ **কোনো BIN-এর সব স্টক ডিলিট করতে:**\n`/clearstock <BIN>`\n\n"
        "🏷️ **কার্ডের দাম পরিবর্তন করতে:**\n`/setprice <AMOUNT>`\n\n"
        "📱 **বিকাশ নম্বর দিতে:**\n`/setbkash <NUMBER>`\n\n"
        "📱 **নগদ নম্বর দিতে:**\n`/setnagad <NUMBER>`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# Main Function
async def run_bot():
    init_db()  # Initialize SQLite Database
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

    logging.info("Bot started successfully with Persistent Database...")
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
