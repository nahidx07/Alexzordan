import os
import json
import telebot
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, request
from datetime import datetime

# ========= CONFIG =========
# টোকেন সরাসরি কোডে না রেখে Environment Variable থেকে নেওয়া হবে
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5024973191"))
DATABASE_URL = os.environ.get("DATABASE_URL")

# Firebase Credentials - Environment Variable থেকে লোড হবে
firebase_config = os.environ.get("FIREBASE_CREDENTIALS")

if not firebase_admin._apps:
    if firebase_config:
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            "databaseURL": DATABASE_URL
        })
    else:
        print("Firebase Credentials not found!")

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ---------- Helpers ----------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def create_ticket(user):
    ref = db.reference("tickets")
    data = ref.get() or {}

    if str(user.id) in data:
        return data[str(user.id)]["ticket"]

    ticket = f"TKT-{1000 + len(data) + 1}"

    ref.child(str(user.id)).set({
        "ticket": ticket,
        "status": "open",
        "created": now()
    })

    db.reference(f"users/{user.id}").set({
        "name": user.first_name,
        "username": user.username,
        "ticket": ticket,
        "joined": now()
    })

    return ticket

def save_message(ticket, sender, text):
    db.reference(f"messages/{ticket}").push({
        "sender": sender,
        "text": text,
        "time": now()
    })

# ---------- Bot Logic ----------
@bot.message_handler(commands=['start'])
def start(message):
    try:
        ticket = create_ticket(message.from_user)
        admin_text = (
            "🆕 New Ticket\n\n"
            f"🎫 Ticket: {ticket}\n"
            f"👤 Name: {message.from_user.first_name}\n"
            f"🆔 User ID: {message.from_user.id}"
        )
        bot.send_message(ADMIN_ID, admin_text)
        bot.send_message(
            message.chat.id,
            f"স্বাগতম! আপনার সমস্যাটি লিখুন 🙂\n\n🎫 Ticket: {ticket}"
        )
    except Exception as e:
        print(f"Error in start: {e}")

@bot.message_handler(func=lambda m: str(m.chat.id) != str(ADMIN_ID))
def user_message(message):
    try:
        ticket = create_ticket(message.from_user)
        save_message(ticket, "user", message.text)

        admin_text = (
            "📩 Support Message\n\n"
            f"🎫 Ticket: {ticket}\n"
            f"👤 Name: {message.from_user.first_name}\n"
            f"🆔 User ID: {message.from_user.id}\n\n"
            f"💬 Message:\n{message.text}"
        )
        bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        print(f"Error in user_message: {e}")

@bot.message_handler(func=lambda m: str(m.chat.id) == str(ADMIN_ID) and m.reply_to_message)
def admin_reply(message):
    try:
        text = message.reply_to_message.text
        if "Ticket:" in text and "User ID:" in text:
            ticket = text.split("Ticket:")[1].split("\n")[0].strip()
            user_id = text.split("User ID:")[1].split("\n")[0].strip()

            save_message(ticket, "admin", message.text)
            bot.send_message(user_id, message.text)
        else:
            bot.send_message(ADMIN_ID, "❌ ফরম্যাট মিলছে না। বটের পাঠানো মেসেজে রিপ্লাই দিন।")

    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(ADMIN_ID, "❌ Reply failed")

# ---------- Webhook Route ----------
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@app.route('/')
def index():
    return "Bot is running on Vercel!", 200

# Vercel needs this
if __name__ == '__main__':
    app.run()
