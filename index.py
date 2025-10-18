import requests
from flask import Flask, request
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# -------------------- CONFIG --------------------
BOT_TOKEN = "8488024807:AAFXgBqDmoKRQdAWgPlOOTj9Lus-o1N1Hps"
OWNER_ID = 8413382851
FIREBASE_URL = "https://legendxbot-686a2-default-rtdb.firebaseio.com/"
API_URL = "https://legendxdata.site/Api/simdata.php?phone="

# -------------------- FIREBASE SETUP --------------------
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": "legendxbot-686a2",
            "private_key_id": "fake-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nFAKEKEY\n-----END PRIVATE KEY-----\n",
            "client_email": "firebase-adminsdk@legendxbot-686a2.iam.gserviceaccount.com",
            "client_id": "1234567890",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk"
        })
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
except Exception as e:
    print("Firebase init error:", e)


# -------------------- SEND MESSAGE --------------------
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


# -------------------- FORMAT SIM INFO --------------------
def format_sim_data(records):
    if not records:
        return "❌ No SIM records found for this number.\n🔁 Try with another number."

    msg = "🎯 *SIM Information Received Successfully*\n━━━━━━━━━━━━━━━\n"
    for r in records:
        msg += (
            f"📱 *Mobile:* `{r.get('Mobile', 'N/A')}`\n"
            f"👤 *Name:* {r.get('Name', 'N/A')}\n"
            f"🪪 *CNIC:* `{r.get('CNIC', 'N/A')}`\n"
            f"🏠 *Address:* {r.get('Address', 'N/A')}\n"
            f"🌍 *Country:* {r.get('Country', 'N/A')}\n"
            "━━━━━━━━━━━━━━━\n"
        )
    msg += "✅ *Status:* Successful\n"
    return msg


# -------------------- POINT SYSTEM --------------------
def get_user_points(uid):
    ref = db.reference(f"users/{uid}/points")
    pts = ref.get()
    return pts if pts else 0


def add_user_points(uid, points):
    ref = db.reference(f"users/{uid}/points")
    current = get_user_points(uid)
    ref.set(current + points)


# -------------------- WEBHOOK --------------------
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json()
        if "message" not in data:
            return "ok"

        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        # START Command
        if text == "/start":
            send_message(chat_id,
                "👋 *Welcome to LegendX SIM Info Bot!*\n\n"
                "➡️ Join our official channels to use this bot:\n"
                "🔗 [Legend Expert](https://t.me/legendxexpert)\n"
                "🔗 [Cyber Expert Chat](https://t.me/cyberexpertchat)\n\n"
                "After joining, send any *mobile number* to get SIM details 📲"
            )
            return "ok"

        # HELP Command
        if text == "/help":
            send_message(chat_id, "💡 Just send a phone number (without 0) to get SIM data.")
            return "ok"

        # ADMIN Add Points
        if text.startswith("/addpoints") and str(chat_id) == str(OWNER_ID):
            try:
                _, uid, pts = text.split()
                add_user_points(uid, int(pts))
                send_message(chat_id, f"✅ Added {pts} points to user {uid}.")
            except Exception:
                send_message(chat_id, "❌ Usage: /addpoints <user_id> <points>")
            return "ok"

        # REFERRAL System
        if text.startswith("/ref"):
            parts = text.split()
            if len(parts) == 2:
                ref_id = parts[1]
                if ref_id != str(chat_id):
                    add_user_points(ref_id, 2)
                    send_message(ref_id, "🎉 You got +2 points from a new referral!")
                    send_message(chat_id, "✅ You joined using referral successfully!")
            return "ok"

        # USER INFO (show points)
        if text == "/points":
            pts = get_user_points(chat_id)
            send_message(chat_id, f"⭐ Your total points: {pts}")
            return "ok"

        # SIM INFO LOOKUP
        if text.isdigit():
            url = f"{API_URL}{text}"
            try:
                resp = requests.get(url, timeout=10)
                js = resp.json()
                if js.get("success") and "records" in js:
                    send_message(chat_id, format_sim_data(js["records"]))
                else:
                    send_message(chat_id, "⚠️ No record found for this number.")
            except Exception as e:
                send_message(chat_id, "❌ Error fetching SIM info, try again later.")
            return "ok"

        # UNKNOWN
        send_message(chat_id, "❌ Invalid command or input. Use /help to see options.")
        return "ok"

    return "Bot is running fine!"


if __name__ == "__main__":
    app.run(debug=True)
