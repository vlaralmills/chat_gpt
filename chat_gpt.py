import openai
import sqlite3
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

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

# ✅ Χρήση μεταβλητής περιβάλλοντος για το API Key
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("🚨 Το API Key δεν έχει οριστεί! Χρησιμοποίησε 'set OPENAI_API_KEY=YOUR_KEY' στα Windows ή 'export OPENAI_API_KEY=YOUR_KEY' σε Mac/Linux.")

# Δημιουργία OpenAI client
client = openai.OpenAI(api_key=api_key)

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
import json  # Προσθήκη import για χρήση json.dumps()

@app.route("/history/<user_id>", methods=["GET"])
def get_history(user_id):
    cursor.execute("SELECT user_message, bot_response, timestamp FROM conversations WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    chats = cursor.fetchall()
    
    chat_list = [{"user": row[0], "bot": row[1], "timestamp": row[2]} for row in chats]

    # ✅ Χρήση json.dumps με ensure_ascii=False για να εμφανίζονται σωστά τα ελληνικά
    return app.response_class(
        response=json.dumps(chat_list, ensure_ascii=False, indent=4),  # indent=4 για καλύτερη μορφοποίηση JSON
        status=200,
        mimetype="application/json"
    )


if __name__ == "__main__":
    app.run(port=5000)
