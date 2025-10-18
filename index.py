import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --------- CONFIG from ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_ID", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
CHANNEL_1 = os.getenv("CHANNEL_1", "").strip()
CHANNEL_2 = os.getenv("CHANNEL_2", "").strip()
API_BASE = os.getenv("API_BASE", "https://legendxdata.site/Api/simdata.php?phone=").strip()
FIREBASE_URL = os.getenv("FIREBASE_URL", "").rstrip("/")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
LOOKUP_COST = 4
REF_REWARD = 2
TIMEOUT = 10

# ----------------- Firebase helpers -----------------
def fb_get(path):
    if not FIREBASE_URL: return None
    try:
        r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=TIMEOUT)
        if r.status_code == 200: return r.json()
    except: return None
    return None

def fb_set(path, value):
    if not FIREBASE_URL: return False
    try:
        r = requests.put(f"{FIREBASE_URL}/{path}.json", json=value, timeout=TIMEOUT)
        return r.status_code in (200, 201)
    except: return False

def fb_update(path, value):
    if not FIREBASE_URL: return False
    try:
        r = requests.patch(f"{FIREBASE_URL}/{path}.json", json=value, timeout=TIMEOUT)
        return r.status_code in (200, 201)
    except: return False

# ----------------- Telegram helpers -----------------
def send_message(chat_id, text, parse_mode="Markdown"):
    if not BOT_TOKEN: return
    try:
        requests.post(
            TELEGRAM_API + "/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=TIMEOUT,
        )
    except: pass

def get_chat_member(chat_username, user_id):
    try:
        r = requests.get(TELEGRAM_API + "/getChatMember",
                         params={"chat_id": chat_username, "user_id": user_id}, timeout=TIMEOUT)
        d = r.json()
        if d.get("ok"): return d["result"].get("status")
    except: return None
    return None

def ensure_user_record(uid):
    rec = fb_get(f"users/{uid}")
    if rec is None:
        rec = {"points": 0, "referrals": {}}
        fb_set(f"users/{uid}", rec)
    else:
        changed = False
        if "points" not in rec: rec["points"] = 0; changed=True
        if "referrals" not in rec: rec["referrals"] = {}; changed=True
        if changed: fb_update(f"users/{uid}", rec)
    return rec

def get_points(uid):
    try: return int(fb_get(f"users/{uid}/points") or 0)
    except: return 0

def change_points(uid, delta):
    ensure_user_record(uid)
    new = max(0, get_points(uid) + int(delta))
    fb_set(f"users/{uid}/points", new)
    return new

def add_referral(referrer_id, new_user_id):
    ensure_user_record(referrer_id)
    ensure_user_record(new_user_id)
    if fb_get(f"users/{referrer_id}/referrals/{new_user_id}"): return False
    fb_set(f"users/{referrer_id}/referrals/{new_user_id}", True)
    change_points(referrer_id, REF_REWARD)
    return True

def format_sim_records(records):
    if not records or not isinstance(records, list) or len(records)==0:
        return "❌ No SIM records found."
    parts=["🎯 *INFO RECEIVED*"]
    for r in records[:5]:
        name = r.get("Name") or r.get("name") or "N/A"
        mobile = r.get("Mobile") or r.get("mobile") or "N/A"
        cnic = r.get("CNIC") or r.get("cnic") or "N/A"
        addr = r.get("Address") or r.get("address") or "N/A"
        country = r.get("Country") or r.get("country") or "N/A"
        parts.append(f"📱 `{mobile}` | 👤 {name} | 🪪 `{cnic}` | 🏠 {addr} | 🌍 {country}")
    return "\n".join(parts)

# ----------------- Webhook -----------------
@app.route("/webhook", methods=["GET","POST"])
def webhook():
    if request.method=="GET": return "Bot running"
    data = request.get_json(silent=True)
    if not data: return jsonify({"ok":False}),400
    msg = data.get("message") or data.get("edited_message")
    if not msg: return jsonify({"ok":True})

    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = (msg.get("text") or "").strip()

    # /start command
    if text.startswith("/start"):
        ensure_user_record(str(user_id))
        send_message(chat_id, f"✅ Welcome! You can now send a mobile number for lookup.")
        return jsonify({"ok":True})

    # /points
    if text=="/points":
        pts=get_points(str(user_id))
        send_message(chat_id,f"💎 Points: {pts}")
        return jsonify({"ok":True})

    # Owner commands
    if text.startswith(("/addpoints","/removepoints","/setpoints")):
        if str(user_id)!=str(OWNER_ID):
            send_message(chat_id,"❌ Not authorized")
            return jsonify({"ok":True})
        parts = text.split()
        if len(parts)<3: send_message(chat_id,"❌ Usage: /addpoints <user_id> <amount>"); return jsonify({"ok":True)
        cmd,target,amt=parts[0],parts[1],int(parts[2])
        if cmd=="/addpoints": new=change_points(target,amt); send_message(chat_id,f"✅ Added {amt} points. Now: {new}")
        elif cmd=="/removepoints": new=change_points(target,-amt); send_message(chat_id,f"✅ Removed {amt} points. Now: {new}")
        else: fb_set(f"users/{target}/points",amt); send_message(chat_id,f"✅ Set points to {amt}")
        return jsonify({"ok":True})

    # Numeric -> phone lookup
    phone="".join(ch for ch in text if ch.isdigit())
    if phone:
        try:
            resp=requests.get(API_BASE+phone,timeout=TIMEOUT)
            js=resp.json() if resp.status_code==200 else {}
            records=[js] if isinstance(js, dict) else js
            out=format_sim_records(records)
            send_message(chat_id,out)
        except:
            send_message(chat_id,"⚠️ Error fetching data.")
        return jsonify({"ok":True})

    # fallback
    send_message(chat_id,"❌ Invalid input. Send /help or a phone number.")
    return jsonify({"ok":True})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)), debug=False)
