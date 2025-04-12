import openai
import sqlite3
import os
import json
from flask import Flask, request, jsonify,render_template
from flask_cors import CORS
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import asyncio

app = Flask(__name__)
CORS(app)

# Database setup
conn = sqlite3.connect("chatbot.db", check_same_thread=False)
cursor = conn.cursor()

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

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = "https://chat-gpt-c9pz.onrender.com/telegram"

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing API keys!")

# Initialize clients
client = openai.OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def chat_with_gpt(user_input: str) -> str:
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo",  # Changed to valid model name
            messages=[{"role": "user", "content": user_input}],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "Συγγνώμη, προέκυψε ένα σφάλμα."

async def handle_message(update: Update, context) -> None:
    try:
        user_message = update.message.text
        user_id = str(update.message.chat_id)
        
        # Get response from GPT
        bot_response = await chat_with_gpt(user_message)
        
        # Save to database
        cursor.execute(
            "INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)",
            (user_id, user_message, bot_response)
        )
        conn.commit()
        
        # Send response
        await update.message.reply_text(bot_response)
    except Exception as e:
        print(f"Error in handle_message: {e}")
        await update.message.reply_text("Συγγνώμη, προέκυψε ένα σφάλμα.")

@app.route("/telegram", methods=["POST"])
async def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(), bot)
        await handle_message(update, None)
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204

@app.route("/robots.txt", methods=["GET"])
def robots():
    return """
    User-agent: *
    Disallow: /
    """, 200



@app.route("/chat", methods=["POST"])
async def chat():
    try:
        data = request.json
        user_id = data.get("user_id", "guest")
        user_message = data.get("message")
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
            
        bot_response = await chat_with_gpt(user_message)
        
        cursor.execute(
            "INSERT INTO conversations (user_id, user_message, bot_response) VALUES (?, ?, ?)",
            (user_id, user_message, bot_response)
        )
        conn.commit()
        
        return jsonify({"response": bot_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history/<user_id>", methods=["GET"])
def get_history(user_id):
    cursor.execute(
        "SELECT user_message, bot_response, timestamp FROM conversations WHERE user_id = ? ORDER BY timestamp DESC",
        (user_id,)
    )
    chats = cursor.fetchall()
    chat_list = [{"user": row[0], "bot": row[1], "timestamp": row[2]} for row in chats]
    return jsonify(chat_list)

async def setup():
    # Set webhook
    await bot.set_webhook(WEBHOOK_URL)
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    # Setup bot and webhook
    asyncio.run(setup())
    # Run Flask app
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
