import requests

url = "http://127.0.0.1:5000/chat"
data = {"message": "Γεια σου chatbot!"}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=data, headers=headers)

if response.status_code == 200:
    print("✅ Επιτυχία! Απάντηση από chatbot:")
    print(response.json())
else:
    print("❌ Σφάλμα:", response.status_code, response.text)
