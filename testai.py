import requests

api_key = "sk_bnnd5v51_Pk9MGxz9MWTIc0XoeA3qIcpG"
url = "https://api.sarvam.ai/v1/chat/completions"  # Check their docs for correct endpoint

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "model": "sarvam-m",
    "messages": [{"role": "user", "content": "Hello"}]
}

response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.text)
