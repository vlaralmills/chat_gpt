import openai
import sqlite3
import os
import json
import asyncio  # ✅ Προσθήκη για async λειτουργίες
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, CallbackContext

# Δημιουργία Flask app
app = Flask(__name__)
CORS(app)

# Δημιουργία ή σύνδεση με SQLite βάση δεδομένων
conn = sqlite3.connect("chatbot.db", check_same_thread=False)
cursor = conn.cursor()

# Δημιουργία πίνακα αν δεν υπάρχει
cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        user_message TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# ✅ Ανάκτηση των API Keys από τις μεταβλητές περιβάλλοντος
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("🚨 Το OpenAI API Key δεν έχει οριστεί!")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 Το Telegram API Token δεν έχει οριστεί!")

# Δημιουργία OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ✅ Σωστή αρχικοποίηση του Telegram `Application`
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


@app.route("/", methods=["GET"])
def home():
    return "Chatbot API is running! Use POST /chat to interact."


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id", "guest")
    user_input = data.get("message")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    try:
        # ✅ Κλήση GPT για απάντηση
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=150,
            temperature=0.7
        )
        bot_reply = response.choices[0].message.content.strip()

        # ✅ Αποθήκευση συνομιλίας
        cursor.execute("INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)",
                       (user_id, user_input, bot_reply))
        conn.commit()

        return jsonify({"response": bot_reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API για προβολή συνομιλιών συγκεκριμένου χρήστη
@app.route("/history/<user_id>", methods=["GET"])
def get_history(user_id):
    cursor.execute("SELECT user_message, bot_response, timestamp FROM conversations WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    chats = cursor.fetchall()

    chat_list = [{"user": row[0], "bot": row[1], "timestamp": row[2]} for row in chats]

    return app.response_class(
        response=json.dumps(chat_list, ensure_ascii=False, indent=4),
        status=200,
        mimetype="application/json"
    )


# ✅ Webhook για το Telegram bot (Συμβατό με Flask)
@app.route("/telegram", methods=["POST"])
async def telegram_webhook():
    update_json = request.get_json()
    print("📩 Λήφθηκε μήνυμα από το Telegram:", update_json)

    try:
        update = Update.de_json(update_json, bot)
        print("✅ Update αντικείμενο δημιουργήθηκε:", update)

        # ✅ Σωστή χρήση await μέσα σε async function
        await application.update_queue.put(update)

        print("✅ Το μήνυμα επεξεργάστηκε επιτυχώς!")
    except Exception as e:
        print("❌ Σφάλμα στο process_update:", str(e))

    return "OK", 200


# ✅ Χειρισμός μηνυμάτων από το Telegram
async def handle_telegram_message(update: Update, context):
    user_message = update.message.text
    user_id = str(update.message.chat_id)

    print(f"📩 Το bot έλαβε μήνυμα: {user_message} από {user_id}")  # ✅ Debug log

    # ✅ Κλήση GPT για απάντηση
    response_text = await chat_async(user_message, user_id)

    print(f"🤖 Απάντηση chatbot: {response_text}")  # ✅ Debug log

    # ✅ Αποστολή απάντησης στον χρήστη
    try:
        await update.message.reply_text(response_text)
        print("✅ Το μήνυμα απεστάλη επιτυχώς στο Telegram!")
    except Exception as e:
        print(f"❌ Σφάλμα κατά την αποστολή απάντησης: {e}")


# ✅ Συνάρτηση για επικοινωνία με OpenAI (ασύγχρονα)
async def chat_async(user_input, user_id):
    try:
        print("⏳ Στέλνω μήνυμα στο OpenAI API...")  # ✅ Debug log
        response = await asyncio.to_thread(client.chat.completions.create,
                                           model="gpt-4o-mini",
                                           messages=[{"role": "user", "content": user_input}],
                                           max_tokens=150,
                                           temperature=0.7)
        bot_reply = response.choices[0].message.content.strip()
        print(f"🤖 OpenAI API Response: {bot_reply}")  # ✅ Debug log

        # ✅ Αποθήκευση συνομιλίας
        cursor.execute("INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)",
                       (user_id, user_input, bot_reply))
        conn.commit()

        return bot_reply
    except Exception as e:
        print(f"❌ Σφάλμα OpenAI API: {e}")
        return "⚠️ Σφάλμα στον server!"


# ✅ Ρύθμιση Telegram bot με Webhook
async def set_telegram_webhook():
    webhook_url = "https://chat-gpt-c9pz.onrender.com/telegram"
    response = await bot.set_webhook(webhook_url)
    if response:
        print(f"✅ Webhook ρυθμίστηκε σωστά: {webhook_url}")
    else:
        print("❌ Σφάλμα κατά τη ρύθμιση του Webhook!")


# ✅ Εκκίνηση του Telegram bot μέσα σε asyncio event loop
async def run_telegram_bot():
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
    print("🚀 Το Telegram bot ξεκίνησε!")
    await application.run_polling()


# ✅ Εκκίνηση του Flask API και του Telegram bot μαζί
async def main():
    await set_telegram_webhook()  # ✅ Ρύθμιση του Webhook
    task1 = asyncio.create_task(run_telegram_bot())  # ✅ Εκκίνηση του Telegram bot
    task2 = asyncio.to_thread(app.run, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))  # ✅ Εκκίνηση Flask
    await asyncio.gather(task1, task2)  # ✅ Τρέχουν και τα δύο παράλληλα


# ✅ Κύρια εκκίνηση του προγράμματος
if __name__ == "__main__":
    asyncio.run(main())  # ✅ Όλα εκκινούνται μέσα σε ένα event loop
