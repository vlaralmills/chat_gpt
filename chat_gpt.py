import openai
import sqlite3
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from threading import Thread

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Το API Token του Telegram bot

if not OPENAI_API_KEY:
    raise ValueError("🚨 Το OpenAI API Key δεν έχει οριστεί!")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 Το Telegram API Token δεν έχει οριστεί!")

# Δημιουργία OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

@app.route("/", methods=["GET"])
def home():
    return "Chatbot API is running! Use POST /chat to interact."

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id", "guest")  # Αν δεν υπάρχει user_id, χρησιμοποιούμε "guest"
    user_input = data.get("message")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    try:
        # ✅ Φόρτωση προηγούμενων συνομιλιών του χρήστη
        cursor.execute("SELECT user_message, bot_response FROM conversations WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
        history = cursor.fetchall()

        # ✅ Έλεγχος αν η βάση περιέχει δεδομένα
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_chats = cursor.fetchone()[0]
        print(f"📌 Συνολικές συνομιλίες στη βάση: {total_chats}")

        # Μετατροπή ιστορικού σε OpenAI format
        messages = [{"role": "system", "content": "Είσαι ένας βοηθητικός και φιλικός chatbot."}]
        for user_msg, bot_msg in history[-5:]:  # Παίρνουμε τις τελευταίες 5 συνομιλίες
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": bot_msg})

        messages.append({"role": "user", "content": user_input})

        # ✅ Κλήση στο OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        bot_reply = response.choices[0].message.content.strip()

        # ✅ Αποθήκευση συνομιλίας με user_id
        cursor.execute("INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)", (user_id, user_input, bot_reply))
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

    # ✅ Χρήση json.dumps με ensure_ascii=False για να εμφανίζονται σωστά τα ελληνικά
    return app.response_class(
        response=json.dumps(chat_list, ensure_ascii=False, indent=4),
        status=200,
        mimetype="application/json"
    )

# ✅ Ρύθμιση Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Συνάρτηση που διαχειρίζεται τα μηνύματα στο Telegram
def handle_telegram_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    user_id = str(update.message.chat_id)

    # ✅ Κλήση GPT για απάντηση
    response_text = chat(user_message, user_id)

    # ✅ Αποστολή απάντησης στον χρήστη
    update.message.reply_text(response_text)

# Συνάρτηση για επικοινωνία με το OpenAI μέσω του Telegram
def chat(user_input, user_id):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=150,
            temperature=0.7
        )
        bot_reply = response.choices[0].message.content.strip()

        # ✅ Αποθήκευση συνομιλίας
        cursor.execute("INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)", (user_id, user_input, bot_reply))
        conn.commit()

        return bot_reply
    except Exception as e:
        return "⚠️ Σφάλμα στον server!"

# Ρύθμιση του Telegram bot
def setup_telegram_bot():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
    application.run_polling()  # ✅ Αυτό αντικαθιστά το `updater.start_polling()` και `updater.idle()`


# Εκκίνηση του Flask API και του Telegram bot
if __name__ == "__main__":
    Thread(target=setup_telegram_bot).start()  # Εκκίνηση του Telegram bot σε ξεχωριστό thread
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

