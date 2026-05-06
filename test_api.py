import requests

try:
    response = requests.post("http://localhost:8000/chat", json={"message": "北京天气"})
    print("Status code:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Error:", e)