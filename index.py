# final professional index.py
import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# ---------------- CONFIG (use Vercel env vars) ----------------
TOKEN = os.getenv("BOT_TOKEN", "")  # Put your token in Vercel env
OWNER_ID = int(os.getenv("OWNER_ID", "8413382851"))  # your numeric Telegram id
BOT_USERNAME = os.getenv("BOT_USERNAME", "expert_legend_infobot")  # without @
CHANNEL_1 = os.getenv("CHANNEL_1", "@legendxexpert")
CHANNEL_2 = os.getenv("CHANNEL_2", "@cyberexpertchat")
API_BASE = os.getenv("API_BASE", "https://legendxdata.site/Api/simdata.php?phone=")

URL = f"https://api.telegram.org/bot{TOKEN}/"

REF_FILE = "referrals.json"
REF_REWARD = 2     # points per referral
LOOKUP_COST = 4    # points cost per lookup
# --------------------------------------------------------------

# ensure referrals file exists
if not os.path.exists(REF_FILE):
    try:
        with open(REF_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    except Exception:
        pass


# ---------- Storage helpers ----------
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


def ensure_user_entry(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"referrals": [], "points": 0}
    return data[uid]


# ---------- Telegram helpers ----------
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
    """Return status like 'member', 'left', etc. or None on error."""
    if not TOKEN:
        return None
    try:
        r = requests.get(URL + "getChatMember", params={"chat_id": chat_username, "user_id": user_id}, timeout=8)
        d = r.json()
        if d.get("ok"):
            return d["result"].get("status")
    except Exception:
        pass
    return None


# ---------- Formatting ----------
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


# ---------- Referral / Points logic ----------
def give_referral_reward(referrer_id, new_user_id):
    data = load_referrals()
    entry = ensure_user_entry(data, referrer_id)
    if str(new_user_id) not in entry["referrals"]:
        entry["referrals"].append(str(new_user_id))
        entry["points"] = entry.get("points", 0) + REF_REWARD
        data[str(referrer_id)] = entry
        save_referrals(data)
        return entry
    return None


def add_points(target_id, amount):
    data = load_referrals()
    entry = ensure_user_entry(data, target_id)
    entry["points"] = entry.get("points", 0) + int(amount)
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


def set_points(target_id, amount):
    data = load_referrals()
    entry = ensure_user_entry(data, target_id)
    entry["points"] = int(amount)
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


def remove_points(target_id, amount):
    data = load_referrals()
    entry = ensure_user_entry(data, target_id)
    entry["points"] = max(0, entry.get("points", 0) - int(amount))
    data[str(target_id)] = entry
    save_referrals(data)
    return entry


# ---------- Main webhook ----------
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

    # parse /start payload for referral
    start_payload = None
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            start_payload = parts[1].strip()

    # ------- COMMANDS -------
    # /start: check channels, welcome (and reward referrer once)
    if text.startswith("/start"):
        s1 = get_chat_member(CHANNEL_1, user_id)
        s2 = get_chat_member(CHANNEL_2, user_id)
        allowed = ("member", "administrator", "creator")
        if s1 not in allowed or s2 not in allowed:
            send_message(chat_id,
                "🚫 *Access Denied!*\n\n"
                "To use this bot you must join both channels below:\n\n"
                f"🔗 {CHANNEL_1}\n"
                f"🔗 {CHANNEL_2}\n\n"
                "After joining, press /start again."
            )
            return "ok"

        # user is member of both channels -> professional English welcome
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        send_message(chat_id,
            "✅ *Welcome!* You have successfully joined the required channels.\n\n"
            "Please send the mobile number *without* leading 0 (example: `923001234567`) to retrieve SIM/CNIC details.\n\n"
            f"Share your referral link to earn points: `{ref_link}`\n"
            "Each referral gives you +2 points. Each lookup costs 4 points."
        )

        # process referral reward once (if payload exists)
        if start_payload:
            try:
                rid = str(int(start_payload))
                if rid != str(user_id):
                    entry = give_referral_reward(rid, user_id)
                    if entry:
                        # notify referrer about reward
                        try:
                            send_message(int(rid), f"🎉 You earned +{REF_REWARD} points! Total: {entry.get('points')}")
                        except Exception:
                            pass
            except Exception:
                pass

        return "ok"

    # /help
    if text == "/help":
        send_message(chat_id,
            "📘 *Help Menu*\n\n"
            "➡️ Send mobile number in international format without leading 0 (e.g. `923001234567`).\n"
            "➡️ Each lookup costs *4 points*. Earn points by sharing your referral link (+2 per referral).\n"
            "➡️ Use /points to view balance and /ref to view referrals."
        )
        return "ok"

    # /about
    if text == "/about":
        send_message(chat_id,
            "🤖 *About This Bot*\n\n"
            "Legend Data Bot — professional SIM lookup tool (data via legendxdata API)."
        )
        return "ok"

    # /ref
    if text == "/ref":
        data = load_referrals()
        entry = data.get(str(user_id), {"referrals": [], "points": 0})
        send_message(chat_id,
            f"👑 *Your Referrals*\n\n"
            f"🔹 Total: {len(entry.get('referrals', []))}\n"
            f"🔹 Users: {', '.join(entry.get('referrals', [])[:10]) or '—'}\n"
            f"🔹 Points: {entry.get('points', 0)}"
        )
        return "ok"

    # /points
    if text == "/points":
        data = load_referrals()
        entry = data.get(str(user_id), {"referrals": [], "points": 0})
        send_message(chat_id,
            f"💎 *Your Points:* {entry.get('points', 0)}\n"
            f"🔗 Referral Link: `https://t.me/{BOT_USERNAME}?start={user_id}`"
        )
        return "ok"

    # Admin commands (owner only)
    if text.startswith("/addpoints") or text.startswith("/setpoints") or text.startswith("/removepoints"):
        parts = text.split()
        cmd = parts[0].lower()
        if user_id != OWNER_ID:
            send_message(chat_id, "❌ You are not authorized to use admin commands.")
            return "ok"
        if len(parts) < 3:
            send_message(chat_id, "❌ Usage:\n/addpoints <user_id> <amount>\n/setpoints <user_id> <amount>\n/removepoints <user_id> <amount>")
            return "ok"
        target = parts[1].strip()
        amount = parts[2].strip()
        try:
            if cmd == "/addpoints":
                entry = add_points(target, int(amount))
                send_message(chat_id, f"✅ Added {amount} points to {target}. New points: {entry.get('points')}")
            elif cmd == "/setpoints":
                entry = set_points(target, int(amount))
                send_message(chat_id, f"✅ Set {target} points to {amount}.")
            else:
                entry = remove_points(target, int(amount))
                send_message(chat_id, f"✅ Removed {amount} points from {target}. New points: {entry.get('points')}")
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return "ok"

    # Otherwise assume number lookup
    num = text.replace(" ", "").replace("-", "")
    if not num or not any(ch.isdigit() for ch in num):
        send_message(chat_id, "⚠️ Please send a valid phone number like `923001234567`.")
        return "ok"

    # membership check (again)
    s1 = get_chat_member(CHANNEL_1, user_id)
    s2 = get_chat_member(CHANNEL_2, user_id)
    if s1 not in ("member", "administrator", "creator") or s2 not in ("member", "administrator", "creator"):
        send_message(chat_id,
            "🚫 *Access Denied!*\nYou must join both channels:\n" + f"{CHANNEL_1}\n{CHANNEL_2}\nAfter joining, try again."
        )
        return "ok"

    # points check (owner bypass)
    data = load_referrals()
    entry = ensure_user_entry(data, user_id)
    points = entry.get("points", 0)
    if user_id != OWNER_ID and points < LOOKUP_COST:
        send_message(chat_id,
            f"⚠️ *Insufficient Points*\nYou need *{LOOKUP_COST}* points to perform a lookup.\nYour Points: {points}\nInvite friends to earn points:\n`https://t.me/{BOT_USERNAME}?start={user_id}`"
        )
        return "ok"

    # deduct points if not owner
    if user_id != OWNER_ID:
        entry["points"] = max(0, entry.get("points", 0) - LOOKUP_COST)
        data[str(user_id)] = entry
        save_referrals(data)

    # call API
    api_url = API_BASE + num
    try:
        r = requests.get(api_url, timeout=10)
        resp_json = r.json()
    except Exception:
        send_message(chat_id, "❌ This number data not received.")
        return "ok"

    # normalize response shapes
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

    # send up to 3 records
    for rec in records[:3]:
        try:
            text_out = format_vip(rec)
            send_message(chat_id, text_out, parse_mode="Markdown")
        except Exception:
            send_message(chat_id, "❌ Error formatting data.")

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
