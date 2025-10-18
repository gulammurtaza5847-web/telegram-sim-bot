# final index.py  — copy this to your repo
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --------- CONFIG from ENV (set these in Vercel) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_ID", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
CHANNEL_1 = os.getenv("CHANNEL_1", "").strip()   # accept "@name" or "name"
CHANNEL_2 = os.getenv("CHANNEL_2", "").strip()
API_BASE = os.getenv("API_BASE", "https://legendxdata.site/Api/simdata.php?phone=").strip()
FIREBASE_URL = os.getenv("FIREBASE_URL", "").rstrip("/")  # like https://...firebaseio.com

if CHANNEL_1.startswith("https://t.me/"):
    CHANNEL_1 = CHANNEL_1.split("/")[-1]
if CHANNEL_2.startswith("https://t.me/"):
    CHANNEL_2 = CHANNEL_2.split("/")[-1]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# constants
REF_REWARD = 2
LOOKUP_COST = 4
TIMEOUT = 10


# ---------------- Firebase REST helpers (no admin SDK) ----------------
def fb_get(path):
    """GET from Firebase REST. path without starting slash. Returns Python object or None."""
    if not FIREBASE_URL:
        return None
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fb_set(path, value):
    """PUT (set) value at path."""
    if not FIREBASE_URL:
        return False
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        r = requests.put(url, json=value, timeout=TIMEOUT)
        return r.status_code in (200, 201)
    except Exception:
        return False


def fb_update(path, value_dict):
    """PATCH update at path."""
    if not FIREBASE_URL:
        return False
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        r = requests.patch(url, json=value_dict, timeout=TIMEOUT)
        return r.status_code in (200, 201)
    except Exception:
        return False


# ---------------- Utility helpers ----------------
def send_message(chat_id, text, parse_mode="Markdown"):
    if not BOT_TOKEN:
        return
    try:
        requests.post(
            TELEGRAM_API + "/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=TIMEOUT,
        )
    except Exception:
        pass


def get_chat_member(chat_username, user_id):
    """Return status string or None."""
    try:
        resp = requests.get(
            TELEGRAM_API + "/getChatMember",
            params={"chat_id": chat_username, "user_id": user_id},
            timeout=TIMEOUT,
        )
        d = resp.json()
        if d.get("ok"):
            return d["result"].get("status")
    except Exception:
        pass
    return None


def ensure_user_record(uid):
    """Ensure /users/{uid} exists in firebase with default structure; return record dict."""
    rec = fb_get(f"users/{uid}")
    if rec is None:
        rec = {"points": 0, "referrals": {}}
        fb_set(f"users/{uid}", rec)
    else:
        # ensure keys exist
        changed = False
        if "points" not in rec:
            rec["points"] = 0
            changed = True
        if "referrals" not in rec:
            rec["referrals"] = {}
            changed = True
        if changed:
            fb_update(f"users/{uid}", rec)
    return rec


def get_points(uid):
    rec = fb_get(f"users/{uid}/points")
    try:
        return int(rec) if rec is not None else 0
    except Exception:
        return 0


def change_points(uid, delta):
    ensure_user_record(uid)
    current = get_points(uid)
    new = max(0, current + int(delta))
    fb_set(f"users/{uid}/points", new)
    return new


def add_referral(referrer_id, new_user_id):
    """Award REF_REWARD to referrer if this new_user_id not already recorded."""
    ensure_user_record(referrer_id)
    ensure_user_record(new_user_id)
    already = fb_get(f"users/{referrer_id}/referrals/{new_user_id}")
    if already:
        return False  # already counted
    # set flag and add points
    fb_set(f"users/{referrer_id}/referrals/{new_user_id}", True)
    change_points(referrer_id, REF_REWARD)
    return True


# ---------------- Format API data (case-insensitive) ----------------
def get_field_case_insensitive(record, *keys):
    """Return first non-empty value for any key variant (case-sensitive or lower)."""
    for k in keys:
        if k in record and record[k]:
            return record[k]
        low = k.lower()
        if low in record and record[low]:
            return record[low]
    # try any known variants
    for k in ["Name", "name", "Mobile", "mobile", "CNIC", "cnic", "Address", "address", "Country", "country"]:
        if k in record and record[k]:
            return record[k]
    return None


def format_sim_records(records):
    if not records or not isinstance(records, list) or len(records) == 0:
        return "❌ No SIM records found for this number.\n🔁 Try another number."
    header = "🎯 *INFO RECEIVED*\n✅ *Status:* Successful\n\n"
    parts = [header]
    for r in records[:5]:  # limit to first 5 if many
        name = get_field_case_insensitive(r, "Name", "name") or "N/A"
        mobile = get_field_case_insensitive(r, "Mobile", "mobile", "Number", "number") or "N/A"
        cnic = get_field_case_insensitive(r, "CNIC", "cnic") or "N/A"
        addr = get_field_case_insensitive(r, "Address", "address") or "N/A"
        country = get_field_case_insensitive(r, "Country", "country") or "N/A"
        block = (
            "━━━━━━━━━━━━━━━━━━\n"
            f"📱 *Mobile:* `{mobile}`\n"
            f"👤 *Name:* {name}\n"
            f"🪪 *CNIC:* `{cnic}`\n"
            f"🏠 *Address:* {addr}\n"
            f"🌍 *Country:* {country}\n"
        )
        parts.append(block)
    parts.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(parts)


# ---------------- Webhook endpoint ----------------
@app.route("/", methods=["GET", "POST"])
def webhook():
    # GET simple health
    if request.method == "GET":
        return "LegendX Bot — running"

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False}), 400

    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return jsonify({"ok": True})

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    from_user = msg.get("from", {})
    user_id = from_user.get("id")
    text = (msg.get("text") or "").strip()

    # handle commands
    # /start [ref]
    if text.startswith("/start"):
        parts = text.split()
        payload = parts[1] if len(parts) > 1 else None

        # ensure user exists
        ensure_user_record(str(user_id))

        # if payload is referral id, try to reward
        if payload:
            try:
                ref_id = str(int(payload))
                if ref_id != str(user_id):
                    added = add_referral(ref_id, str(user_id))
                    if added:
                        # notify referrer
                        try:
                            send_message(ref_id, f"🎉 You earned +{REF_REWARD} points! Total: {get_points(ref_id)}")
                        except Exception:
                            pass
            except Exception:
                pass

        # check channel membership (allow if both joined)
        s1 = get_chat_member(CHANNEL_1, user_id)
        s2 = get_chat_member(CHANNEL_2, user_id)
        allowed = ("member", "administrator", "creator")
        if s1 not in allowed or s2 not in allowed:
            send_message(chat_id,
                         "🚫 *Access Denied*\n\nTo use this bot you must join both channels:\n"
                         f"🔗 @{CHANNEL_1}\n🔗 @{CHANNEL_2}\n\nAfter joining, press /start again.")
            return jsonify({"ok": True})

        # success welcome
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        pts = get_points(str(user_id))
        send_message(chat_id,
                     f"✅ *Welcome!* You have access.\n\n"
                     f"Send the mobile number *without* leading 0 (e.g. `923001234567`).\n\n"
                     f"🔗 Share to earn points: `{ref_link}` — +{REF_REWARD} per join.\n"
                     f"💎 Your Points: {pts}\n"
                     f"⚠️ Each lookup costs {LOOKUP_COST} points.")
        return jsonify({"ok": True})

    # /help
    if text == "/help":
        send_message(chat_id,
                     "📘 *Help*\n\n"
                     "➡️ Send number (e.g. `923001234567`) to get SIM details.\n"
                     "➡️ Use /points to check your points.\n"
                     "➡️ Owner commands: /addpoints <user_id> <amount>")
        return jsonify({"ok": True})

    # /points
    if text == "/points":
        pts = get_points(str(user_id))
        send_message(chat_id, f"💎 *Your Points:* {pts}\nShare: `https://t.me/{BOT_USERNAME}?start={user_id}`")
        return jsonify({"ok": True})

    # owner admin commands
    if text.startswith("/addpoints") or text.startswith("/setpoints") or text.startswith("/removepoints"):
        if str(user_id) != str(OWNER_ID):
            send_message(chat_id, "❌ You are not authorized to use admin commands.")
            return jsonify({"ok": True})
        parts = text.split()
        if len(parts) < 3:
            send_message(chat_id, "❌ Usage: /addpoints <user_id> <amount>")
            return jsonify({"ok": True})
        cmd = parts[0].lower()
        target = parts[1]
        amt = parts[2]
        try:
            if cmd == "/addpoints":
                new = change_points(target, int(amt))
                send_message(chat_id, f"✅ Added {amt} points to {target}. Now: {new}")
                send_message(target, f"💎 Admin added {amt} points to your account. Total: {new}")
            elif cmd == "/setpoints":
                fb_set(f"users/{target}/points", int(amt))
                send_message(chat_id, f"✅ Set {target} points to {amt}.")
            else:  # /removepoints
                new = change_points(target, -int(amt))
                send_message(chat_id, f"✅ Removed {amt} points from {target}. Now: {new}")
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return jsonify({"ok": True})

    # If text is digits -> assume phone lookup
    phone = "".join(ch for ch in text if ch.isdigit())
    if phone:
        # check channel membership again
        s1 = get_chat_member(CHANNEL_1, user_id)
        s2 = get_chat_member(CHANNEL_2, user_id)
        if s1 not in ("member", "administrator", "creator") or s2 not in ("member", "administrator", "creator"):
            send_message(chat_id,
                         "🚫 *Access Denied*\nYou must join both channels:\n"
                         f"🔗 @{CHANNEL_1}\n🔗 @{CHANNEL_2}\nAfter joining press /start.")
            return jsonify({"ok": True})

        # check points (owner bypass)
        if str(user_id) != str(OWNER_ID):
            pts = get_points(str(user_id))
            if pts < LOOKUP_COST:
                send_message(chat_id,
                             f"⚠️ *Insufficient Points*\nYou need {LOOKUP_COST} points to perform lookup.\nYour Points: {pts}\nShare: `https://t.me/{BOT_USERNAME}?start={user_id}`")
                return jsonify({"ok": True})

        # call API
        try:
            resp = requests.get(API_BASE + phone, timeout=TIMEOUT)
            js = resp.json() if resp.status_code == 200 else {}
        except Exception:
            send_message(chat_id, "⚠️ Unable to fetch data right now. Try again later.")
            return jsonify({"ok": True})

        # normalize records
        records = []
        if isinstance(js, dict):
            # common shapes: {"records":[{...},...]} or {"data": {...}} etc.
            if js.get("records"):
                records = js.get("records")
            elif js.get("data"):
                d = js.get("data")
                if isinstance(d, list):
                    records = d
                elif isinstance(d, dict):
                    records = [d]
            elif js.get("result"):
                r = js.get("result")
                if isinstance(r, list):
                    records = r
                elif isinstance(r, dict):
                    records = [r]
            else:
                # maybe top-level fields are the record
                # consider js itself as a single record if it has 'Name' or 'Mobile'
                if any(k.lower() in js for k in ("name", "mobile", "cnic", "address")):
                    records = [js]
        elif isinstance(js, list):
            records = js

        if not records:
            send_message(chat_id, "❌ No record found for this number. Try another.")
            return jsonify({"ok": True})

        # Deduct points AFTER verifying we have records (owner bypass)
        if str(user_id) != str(OWNER_ID):
            change_points(str(user_id), -LOOKUP_COST)

        # send formatted info (may be multiple records)
        try:
            out = format_sim_records(records)
            send_message(chat_id, out)
        except Exception:
            send_message(chat_id, "⚠️ Error formatting data. Try again later.")
        return jsonify({"ok": True})

    # fallback
    send_message(chat_id, "❌ Invalid input. Use /help for commands or send a phone number.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
