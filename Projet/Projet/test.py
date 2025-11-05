import requests

url = "http://127.0.0.1:11434/api/generate/"  # use 127.0.0.1 unless your server binds to a different address
payload = {
    "model": "mistral",
    "prompt": "salut",
    "stream": False
}
headers = {"Content-Type": "application/json"}

try:
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    try:
        print("JSON response:", resp.json())
    except ValueError:
        print("Text response:", resp.text)
except requests.RequestException as e:
    print("Request failed:", e)