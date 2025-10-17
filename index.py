# final index.py (production-ready)
import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# ---------------- CONFIG (use env vars) ----------------
TOKEN = os.getenv("BOT_TOKEN", "")                # set in Vercel env
OWNER_ID = int(os.getenv("OWNER_ID", "8413382851"))  # your owner id (fallback provided)
URL = f"https://api.telegram.org/bot{TOKEN}/"

BOT_USERNAME = os.getenv("BOT_USERNAME", "expert_legend_infobot")  # without @
CHANNEL_1 = os.getenv("CHANNEL_1", "@legendxexpert")
CHANNEL_2 = os.getenv("CHANNEL_2", "@cyberexpertchat")

API_BASE = os.getenv("API_BASE", "https://legendxdata.site/Api/simdata.php?phone=")

REF_FILE = "referrals.json"
LOOKUP_COST = 4
REF_REWARD = 2
# ------------------------------------------------------

# ensure referrals file exists
if not os.path.exists(REF_FILE):
    try:
        with open(REF_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    except Exception:
        pass


# ---------- storage helpers ----------
def load_referrals():
    try:
        with open(REF_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_referrals(data):
    try:
        with open(REF_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def ensure_user(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"count": 0, "list": [], "points": 0}
    return data[uid]


# ---------- telegram helpers ----------
def send_message(chat_id, text, parse_mode="Markdown"):
    if not TOKEN:
        return
    try:
        requests.post(URL + "sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode
        }, timeout=10)
    except Exception:
        pass


def get_chat_member(chat_username, user_id):
    if not TOKEN:
        return None
    try:
        r = requests.get(URL + "getChatMember", params={
            "chat_id": chat_username, "user_id": user_id
        }, timeout=8)
        d = r.json()
        if d.get("ok"):
            return d["result"].get("status")
    except Exception:
        pass
    return None


# ---------- formatting ----------
def format_vip(record):
    header = "⚡ *LEGEND DATA SYSTEM* ⚡\n"
    header += "🎯 *INFO RECEIVED*\n✅ *Status:* Successful\n\n"
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    lines = [
        sep,
        f"👤 *Name:* {record.get('name','N/A')}",
        f"📱 *Number:* {record.get('number','N/A')}",
        f"🪪 *CNIC:* {record.get('cnic', record.get('nic','N/A'))}",
        f"🏠 *Address:* {record.get('address','N/A')}",
        f"🌍 *City:* {record.get('city','N/A')}",
        f"📶 *Operator:* {record.get('operator','N/A')}",
        sep
    ]
    return header + "\n".join(lines)


# ---------- referral / points logic ----------
def add_referral_points(referrer_id, new_user_id):
    data = load_referrals()
    entry = ensure_user(data, referrer_id)
    if str(new_user_id) not in entry["list"]:
        entry["list"].append(str(new_user_id))
        entry["count"] = len(entry["list"])
        entry["points"] = entry.get("points", 0) + REF_REWARD
        data[str(referrer_id)] = entry
        save_referrals(data)
        return entry
    return None


def add_points_to_user(target_id, amount):
    data = load_referrals()
    entry = ensure_user(data, target_id)
    entry["points"] = entry.get("points", 0) + int(amount)
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


def set_points_for_user(target_id, amount):
    data = load_referrals()
    entry = ensure_user(data, target_id)
    entry["points"] = int(amount)
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


def remove_points_from_user(target_id, amount):
    data = load_referrals()
    entry = ensure_user(data, target_id)
    entry["points"] = max(0, entry.get("points", 0) - int(amount))
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


# ---------- main webhook route ----------
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Legend Data Bot — running"

    try:
        update = request.get_json(force=True)
    except Exception:
        return "ok"

    if not update or "message" not in update:
        return "ok"

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    from_user = msg.get("from", {})
    user_id = from_user.get("id")
    text = (msg.get("text") or "").strip()

    # parse /start payload if exists
    start_payload = None
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            start_payload = parts[1].strip()

    # Commands
    # /start -> channel-check, welcome, process referral
    if text.startswith("/start"):
        # channel membership check
        s1 = get_chat_member(CHANNEL_1, user_id)
        s2 = get_chat_member(CHANNEL_2, user_id)
        allowed = ("member", "administrator", "creator")
        if s1 not in allowed or s2 not in allowed:
            msg_text = (
                "🚫 *Access Denied!*\n\n"
                "To use this bot you must join both channels below:\n\n"
                f"🔗 {CHANNEL_1}\n"
                f"🔗 {CHANNEL_2}\n\n"
                "After joining, press /start again."
            )
            send_message(chat_id, msg_text)
            return "ok"

        # allowed -> welcome + referral link
        welcome = (
            "⚡ *WELCOME TO LEGEND DATA SYSTEM* ⚡\n\n"
            "Send a phone number (e.g. `923001234567`) to retrieve SIM data.\n\n"
            f"Share your referral link:\n`https://t.me/{BOT_USERNAME}?start={user_id}`\n"
            "Use /ref to view your referrals and /points to view your points."
        )
        send_message(chat_id, welcome)

        # process referral reward if payload present
        if start_payload:
            try:
                rid = str(int(start_payload))
                if rid != str(user_id):
                    entry = add_referral_points(rid, user_id)
                    if entry:
                        try:
                            send_message(int(rid), f"👑 New Referral!\nUser `{user_id}` joined via your link. Total referrals: {entry['count']}\nPoints: {entry['points']}")
                        except Exception:
                            pass
            except Exception:
                pass

        return "ok"

    # /help
    if text == "/help":
        send_message(chat_id,
            "📘 *Help Menu*\n\n"
            "➡️ Send phone number in format `923001234567` to get SIM info (costs 4 points).\n"
            "➡️ /ref — show referrals\n"
            "➡️ /points — show points and referral link\n"
            "➡️ Owner commands: /addpoints /setpoints /removepoints"
        )
        return "ok"

    # /about
    if text == "/about":
        send_message(chat_id, "🤖 *About This Bot*\nLegend Data Bot — pro SIM lookup tool.")
        return "ok"

    # /ref
    if text == "/ref":
        data = load_referrals()
        entry = data.get(str(user_id), {"count": 0, "list": [], "points": 0})
        send_message(chat_id,
            f"👑 *Your Referrals*\n\n🔹 Total: {entry.get('count',0)}\n🔹 Users: {', '.join(entry.get('list',[])[:10]) or '—'}\n🔹 Points: {entry.get('points',0)}"
        )
        return "ok"

    # /points
    if text == "/points":
        data = load_referrals()
        entry = data.get(str(user_id), {"count": 0, "list": [], "points": 0})
        send_message(chat_id,
            f"💎 *Your Points:* {entry.get('points',0)}\n🔗 Referral Link: `https://t.me/{BOT_USERNAME}?start={user_id}`"
        )
        return "ok"

    # Admin commands: /addpoints <user_id> <amount>, /setpoints, /removepoints
    if text.startswith("/addpoints") or text.startswith("/setpoints") or text.startswith("/removepoints"):
        parts = text.split()
        cmd = parts[0].lower()
        if user_id not in [OWNER_ID]:
            send_message(chat_id, "❌ You are not authorized to use admin commands.")
            return "ok"
        if len(parts) < 3:
            send_message(chat_id, "❌ Usage:\n/addpoints <user_id> <amount>\n/setpoints <user_id> <amount>\n/removepoints <user_id> <amount>")
            return "ok"
        target = parts[1].strip()
        amount = parts[2].strip()
        try:
            if cmd == "/addpoints":
                entry = add_points_to_user(target, int(amount))
                send_message(chat_id, f"✅ Added {amount} points to {target}. New points: {entry.get('points')}")
            elif cmd == "/setpoints":
                entry = set_points_for_user(target, int(amount))
                send_message(chat_id, f"✅ Set {target} points to {amount}.")
            else:
                entry = remove_points_from_user(target, int(amount))
                send_message(chat_id, f"✅ Removed {amount} points from {target}. New points: {entry.get('points')}")
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return "ok"

    # Otherwise treat message as a number lookup
    num = text.replace(" ", "").replace("-", "")
    if not num or not any(ch.isdigit() for ch in num):
        send_message(chat_id, "⚠️ Please send a valid phone number like `923001234567`.")
        return "ok"

    # Check membership one more time
    s1 = get_chat_member(CHANNEL_1, user_id)
    s2 = get_chat_member(CHANNEL_2, user_id)
    if s1 not in ("member", "administrator", "creator") or s2 not in ("member", "administrator", "creator"):
        send_message(chat_id,
            "🚫 *Access Denied!*\nYou must join both channels:\n" + f"{CHANNEL_1}\n{CHANNEL_2}\nAfter joining, try again."
        )
        return "ok"

    # Points check (admins bypass)
    data = load_referrals()
    entry = ensure_user(data, user_id)
    points = entry.get("points", 0)
    if user_id not in [OWNER_ID] and points < LOOKUP_COST:
        send_message(chat_id,
            f"⚠️ *Insufficient Points*\nYou need *{LOOKUP_COST}* points to perform a lookup.\nYour Points: {points}\nInvite friends to earn points:\n`https://t.me/{BOT_USERNAME}?start={user_id}`"
        )
        return "ok"

    # Deduct points (unless owner)
    if user_id not in [OWNER_ID]:
        entry["points"] = max(0, entry.get("points", 0) - LOOKUP_COST)
        data[str(user_id)] = entry
        save_referrals(data)

    # Call API
    api_url = API_BASE + num
    try:
        r = requests.get(api_url, timeout=10)
        resp_json = r.json()
    except Exception:
        send_message(chat_id, "❌ This number data not received.")
        return "ok"

    # Normalize different response shapes
    records = []
    if isinstance(resp_json.get("records"), list) and resp_json.get("records"):
        records = resp_json.get("records")
    elif isinstance(resp_json.get("data"), dict) and resp_json.get("data"):
        records = [resp_json.get("data")]
    elif isinstance(resp_json.get("data"), list):
        records = resp_json.get("data")
    elif isinstance(resp_json.get("result"), list):
        records = resp_json.get("result")

    if not records:
        send_message(chat_id, "❌ This number data not received.")
        return "ok"

    # Send up to 3 records
    for rec in records[:3]:
        try:
            text_out = format_vip(rec)
            send_message(chat_id, text_out, parse_mode="Markdown")
        except Exception:
            send_message(chat_id, "❌ Error formatting data.")

    return "ok"


if __name__ == "__main__":
    # For local testing only
    app.run(host="0.0.0.0", port=5000, debug=True)
