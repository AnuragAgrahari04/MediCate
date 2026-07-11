import os
import requests
from django.conf import settings

def create_daily_room(room_name):
    """Create a video room using Daily.co API."""
    api_key = os.environ.get('DAILY_API_KEY')
    if not api_key:
        return None, None
        
    url = "https://api.daily.co/v1/rooms"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "name": room_name,
        "properties": {
            "exp": int((__import__('time').time()) + 24 * 3600), # Room expires in 24 hours
            "enable_chat": True
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('url'), data.get('name')
        elif response.status_code == 400 and 'already exists' in response.text:
            # Room already exists, fetch it
            get_url = f"https://api.daily.co/v1/rooms/{room_name}"
            get_res = requests.get(get_url, headers=headers)
            if get_res.status_code == 200:
                data = get_res.json()
                return data.get('url'), data.get('name')
    except Exception as e:
        print(f"Daily API error: {e}")
        
    return None, None
