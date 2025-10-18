import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 🔑 Telegram Bot Token & Owner ID
TOKEN = "8488024807:AAFXgBqDmoKRQdAWgPlOOTj9Lus-o1N1Hps"
OWNER_ID = 8413382851
URL = f"https://api.telegram.org/bot{TOKEN}/"

# ✅ Memory Storage
user_points = {}
referrals = {}

# ✅ Required Channels
REQUIRED_CHANNELS = [
    "@legendxexpert",
    "@cyberexpertchat"
]


# ------------------- Format API Response -------------------
def format_response(data):
    if not data or not isinstance(data, dict):
        return (
            "🚫 *No record found in LEGEND DATA system.*\n"
            "Please check the number and try again."
        )

    return (
        "🎯 *INFO RECEIVED*\n"
        "✅ *Status:* Successful\n\n"
        f"👤 *Name:* {data.get('name','N/A')}\n"
        f"📱 *Number:* {data.get('number','N/A')}\n"
        f"🪪 *CNIC:* {data.get('cnic','N/A')}\n"
        f"🏠 *Address:* {data.get('address','N/A')}\n"
        f"🌍 *City:* {data.get('city','N/A')}\n"
        f"📡 *Sim Type:* {data.get('sim_type','N/A')}\n"
        "━━━━━━━━━━━━━━━━━━"
    )


# ------------------- Telegram Send -------------------
def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(URL + "sendMessage", json=payload)


# ------------------- Channel Join Check -------------------
def check_channel_membership(user_id):
    for channel in REQUIRED_CHANNELS:
        resp = requests.get(URL + "getChatMember", params={"chat_id": channel, "user_id": user_id}).json()
        status = resp.get("result", {}).get("status", "")
        if status not in ["member", "administrator", "creator"]:
            return False
    return True


# ------------------- Webhook -------------------
@app.route("/", methods=["POST", "GET"])
def main():
    if request.method == "POST":
        data = request.get_json()
        if "message" not in data:
            return jsonify({"ok": True})

        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").strip()

        # ✅ /start Command (Referral system)
        if text.startswith("/start"):
            ref_id = None
            parts = text.split()
            if len(parts) > 1:
                try:
                    ref_id = int(parts[1])
                except ValueError:
                    ref_id = None

            # Referral Handling
            if ref_id and ref_id != chat_id:
                if ref_id not in referrals:
                    referrals[ref_id] = set()
                if chat_id not in referrals[ref_id]:
                    referrals[ref_id].add(chat_id)
                    user_points[ref_id] = user_points.get(ref_id, 0) + 2
                    send_message(ref_id, f"🎁 You earned *+2 points* from referral ({chat_id})!")

            if not check_channel_membership(chat_id):
                msg = (
                    "🚨 *Join both channels first to use this bot:*\n"
                    "👉 [Legend Expert](https://t.me/legendxexpert)\n"
                    "👉 [Cyber Expert Chat](https://t.me/cyberexpertchat)\n\n"
                    "After joining, press /start again ✅"
                )
                send_message(chat_id, msg)
                return "ok"

            send_message(chat_id, "👋 *Welcome to LEGEND DATA BOT*\n\nSend any number (without 0) to get details.\n\nUse /refer to earn free points 💎")
            return "ok"

        # ✅ /refer Command
        if text == "/refer":
            link = f"https://t.me/expert_legend_infobot?start={chat_id}"
            send_message(chat_id, f"💎 *Your Referral Link:*\n{link}\n\nEarn *2 Points* per join!\nUse /points to check balance.")
            return "ok"

        # ✅ /points Command
        if text == "/points":
            pts = user_points.get(chat_id, 0)
            send_message(chat_id, f"⭐ *Your Current Points:* {pts}")
            return "ok"

        # ✅ /addpoints (Owner Only)
        if text.startswith("/addpoints") and chat_id == OWNER_ID:
            try:
                _, uid, amt = text.split()
                uid, amt = int(uid), int(amt)
                user_points[uid] = user_points.get(uid, 0) + amt
                send_message(chat_id, f"✅ Added {amt} points to user {uid}.")
                send_message(uid, f"💎 You received {amt} bonus points from admin!")
            except Exception:
                send_message(chat_id, "⚠️ Use: `/addpoints user_id amount`")
            return "ok"

        # ✅ Channel join recheck
        if not check_channel_membership(chat_id):
            msg = (
                "⚠️ Please join the required channels first:\n"
                "👉 [Legend Expert](https://t.me/legendxexpert)\n"
                "👉 [Cyber Expert Chat](https://t.me/cyberexpertchat)"
            )
            send_message(chat_id, msg)
            return "ok"

        # ✅ Points Check
        user_points.setdefault(chat_id, 0)
        if user_points[chat_id] < 4:
            send_message(chat_id, "💰 You need *4 points* to get info.\nUse /refer to earn more points.")
            return "ok"

        user_points[chat_id] -= 4

        # ✅ API Fetch
        api_url = f"https://legendxdata.site/Api/simdata.php?phone={text}"
        try:
            resp = requests.get(api_url)
            api_data = resp.json()
            reply = format_response(api_data)
        except Exception:
            reply = "⚠️ Unable to fetch data right now. Try again later."

        send_message(chat_id, reply)
        return "ok"

    return "🤖 LEGEND DATA BOT is running!"


if __name__ == "__main__":
    app.run(debug=True)
