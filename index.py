import os
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ---- CONFIG ----
BOT_TOKEN = "8488024807:AAFXgBqDmoKRQdAWgPlOOTj9Lus-o1N1Hps"
OWNER_ID = 8413382851
CHANNELS = ["@legendxexpert", "@cyberexpertchat"]
API_URL = "https://legendxdata.site/Api/simdata.php?phone="

REF_FILE = "referrals.json"

# ---- FUNCTIONS ----
def load_referrals():
    if not os.path.exists(REF_FILE):
        with open(REF_FILE, "w") as f:
            json.dump({}, f)
    with open(REF_FILE, "r") as f:
        return json.load(f)

def save_referrals(data):
    with open(REF_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def check_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    refs = load_referrals()

    # Referral handling
    if len(context.args) > 0:
        ref_id = context.args[0]
        if ref_id != user_id:
            refs.setdefault(user_id, {"points": 0, "referred_by": ref_id})
            refs.setdefault(ref_id, {"points": 0})
            refs[ref_id]["points"] += 2
            save_referrals(refs)

    if user_id not in refs:
        refs[user_id] = {"points": 0}
        save_referrals(refs)

    # Check if joined all channels
    joined = await check_channels(update, context)
    if not joined:
        buttons = [[InlineKeyboardButton("Join Channel 1", url="https://t.me/legendxexpert")],
                   [InlineKeyboardButton("Join Channel 2", url="https://t.me/cyberexpertchat")],
                   [InlineKeyboardButton("✅ Joined Done", callback_data="joined_done")]]
        await update.message.reply_text(
            "⚠️ Please join both channels to use this bot:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    refer_link = f"https://t.me/{context.bot.username}?start={user_id}"
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"📢 Share your refer link and earn 2 points per user:\n"
        f"{refer_link}\n\n"
        f"💰 You currently have {refs[user_id]['points']} points.\n\n"
        f"Send a 10 or 11 digit number (without 0) to get SIM info."
    )

async def joined_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    joined = await check_channels(query, context)
    if not joined:
        await query.edit_message_text("❌ You must join both channels first!")
    else:
        await query.edit_message_text("✅ Thanks! Now send any number (without 0) to get info.")

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Only the owner can use this command.")
        return

    try:
        user_id = context.args[0]
        amount = int(context.args[1])
        refs = load_referrals()
        refs.setdefault(user_id, {"points": 0})
        refs[user_id]["points"] += amount
        save_referrals(refs)
        await update.message.reply_text(f"✅ Added {amount} points to {user_id}.")
    except Exception as e:
        await update.message.reply_text("⚠️ Usage: /addpoints <user_id> <amount>")

async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    refs = load_referrals()
    points = refs.get(user_id, {"points": 0})["points"]
    await update.message.reply_text(f"💰 You currently have {points} points.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    refs = load_referrals()

    if not text.isdigit():
        await update.message.reply_text("⚠️ Please send a valid phone number without 0.")
        return

    refs.setdefault(user_id, {"points": 0})
    if refs[user_id]["points"] < 4:
        await update.message.reply_text("❌ You need 4 points to get info. Refer friends to earn more!")
        return

    try:
        response = requests.get(API_URL + text)
        data = response.json()

        if not data or "number" not in data:
            raise Exception("Invalid data")

        info = (
            f"📱 **Number:** {data.get('number', 'N/A')}\n"
            f"👤 **Name:** {data.get('name', 'N/A')}\n"
            f"🪪 **CNIC:** {data.get('cnic', 'N/A')}\n"
            f"🏠 **Address:** {data.get('address', 'N/A')}\n"
            f"📶 **Operator:** {data.get('operator', 'N/A')}"
        )
        await update.message.reply_text(info, parse_mode="Markdown")

        refs[user_id]["points"] -= 4
        save_referrals(refs)

    except Exception as e:
        await update.message.reply_text("❌ No data received or invalid number. Please try again later.")

# ---- MAIN ----
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addpoints", add_points))
app.add_handler(CommandHandler("mypoints", my_points))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.COMMAND, handle_message))
app.add_handler(CommandHandler("joined_done", joined_done))

if __name__ == "__main__":
    print("✅ Bot running...")
    app.run_polling()
