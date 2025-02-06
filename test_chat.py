import requests

url = "http://127.0.0.1:5000/chat"
user_id = "user_123"  # Μπορεί να είναι οποιοδήποτε αναγνωριστικό χρήστη

while True:
    user_input = input("Εσύ: ")
    if user_input.lower() == "exit":
        break

    data = {"user_id": user_id, "message": user_input}
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        print("Bot:", response.json()["response"])
    else:
        print("❌ Σφάλμα:", response.status_code, response.text)
