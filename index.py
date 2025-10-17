import requests
from flask import Flask, request
import json, os

app = Flask(__name__)

# 🔑 Bot token and owner ID
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", 8413382851))
URL = f"https://api.telegram.org/bot{TOKEN}/"

# 📂 Data file
REF_FILE = "referrals.json"

if not os.path.exists(REF_FILE):
    with open(REF_FILE, "w") as f:
        json.dump({}, f)


# ------------------- Helper Functions -------------------
def load_data():
    with open(REF_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(REF_FILE, "w") as f:
        json.dump(data, f, indent=4)


def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(URL + "sendMessage", json=payload)


def format_response(data):
    if not data:
        return "❌ This number data not received."

    header = "🎯 *INFO RECEIVED*\n✅ *Status:* Successful\n━━━━━━━━━━━━━━━\n"
    formatted = [header]

    for item in data:
        block = (
            f"👤 *Name:* {item.get('Name','N/A')}\n"
            f"📱 *Mobile:* {item.get('Mobile','N/A')}\n"
            f"🪪 *CNIC:* {item.get('CNIC','N/A')}\n"
            f"🏠 *Address:* {item.get('Address','N/A')}\n"
            f"🌍 *Country:* {item.get('Country','N/A')}\n"
            "━━━━━━━━━━━━━━━"
        )
        formatted.append(block)

    return "\n".join(formatted)


# ------------------- Webhook -------------------
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        update = request.get_json()

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            user_id = str(chat_id)
            text = update["message"].get("text", "").strip()
            data = load_data()

            # Ensure user entry exists
            if user_id not in data:
                data[user_id] = {"points": 0, "referrals": []}

            # ------------------- Commands -------------------
            if text.startswith("/start"):
                parts = text.split()
                if len(parts) > 1:
                    ref_id = parts[1]
                    if ref_id != user_id and ref_id in data:
                        if user_id not in data[ref_id]["referrals"]:
                            data[ref_id]["referrals"].append(user_id)
                            data[ref_id]["points"] += 2
                            save_data(data)
                            send_message(ref_id, f"🎉 New referral joined! You earned +2 points!\nTotal: {data[ref_id]['points']} points")

                send_message(chat_id,
                    "👋 *Welcome to Expert Legend Info Bot!*\n\n"
                    "🔗 Join our channels first:\n"
                    "➡️ [Legend X Expert](https://t.me/legendxexpert)\n"
                    "➡️ [Cyber Expert Chat](https://t.me/cyberexpertchat)\n\n"
                    "Then send any phone number to get SIM Data.\n"
                    "Use /points to check balance or /about for info."
                )
                save_data(data)
                return "ok"

            elif text == "/help":
                send_message(chat_id,
                    "📖 *Help Menu*\n\n"
                    "➡️ Send a mobile number to get SIM data.\n"
                    "➡️ Each lookup costs *4 points*.\n"
                    "➡️ Invite friends to earn *2 points per referral*.\n"
                    "➡️ Use /points to see your balance."
                )
                return "ok"

            elif text == "/about":
                send_message(chat_id,
                    "🤖 *About This Bot*\n\n"
                    "This bot fetches SIM & CNIC data using API.\n"
                    "Developed by *Expert Legend Team* ⚡"
                )
                return "ok"

            elif text == "/points":
                ref_link = f"https://t.me/expert_legend_infobot?start={user_id}"
                send_message(chat_id,
                    f"💎 *Your Points:* {data[user_id]['points']}\n"
                    f"👥 *Referrals:* {len(data[user_id]['referrals'])}\n\n"
                    f"🔗 *Your Referral Link:*\n{ref_link}"
                )
                return "ok"

            # 🔧 Owner add points manually
            elif text.startswith("/addpoints") and str(chat_id) == str(OWNER_ID):
                try:
                    _, uid, pts = text.split()
                    if uid in data:
                        data[uid]["points"] += int(pts)
                        save_data(data)
                        send_message(chat_id, f"✅ Added {pts} points to {uid}")
                    else:
                        send_message(chat_id, "⚠️ User not found.")
                except:
                    send_message(chat_id, "Usage: /addpoints <user_id> <points>")
                return "ok"

            # ------------------- SIM Data Lookup -------------------
            elif text.isdigit() or text.startswith("92"):
                if data[user_id]["points"] < 4:
                    ref_link = f"https://t.me/expert_legend_infobot?start={user_id}"
                    send_message(chat_id,
                        f"⚠️ You need at least *4 points* to use lookup.\n"
                        f"Invite friends to earn more points!\n\n"
                        f"🔗 *Your Referral Link:*\n{ref_link}"
                    )
                    return "ok"

                api_url = f"https://legendxdata.site/Api/simdata.php?phone={text}"
                try:
                    resp = requests.get(api_url, timeout=10)
                    data_list = resp.json()
                    reply = format_response(data_list)
                    data[user_id]["points"] -= 4
                    save_data(data)
                except Exception:
                    reply = "❌ This number data not received."

                send_message(chat_id, reply)
                return "ok"

            else:
                send_message(chat_id, "⚠️ Unknown command. Use /help for options.")
                return "ok"

        return "ok"

    return "Bot is running fine!"


if __name__ == "__main__":
    app.run(debug=True)
