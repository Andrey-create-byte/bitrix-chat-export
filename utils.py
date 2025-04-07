
import requests
import time

def get_chat_list(webhook):
    url = f"{webhook}/im.recent.get.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    chats = [
        {
            "id": str(chat["chat_id"]),
            "title": f'{chat["title"]} (ID: {chat["chat_id"]})',
            "type": chat["type"],
        }
        for chat in data.get("result", [])
        if chat["type"] == "chat"
    ]
    return chats

def get_chat_history(webhook, chat_id, limit=50, offset=0):
    url = f"{webhook}/im.dialog.messages.get.json"
    params = {
        "DIALOG_ID": f"chat{chat_id}",
        "LIMIT": limit,
        "OFFSET": offset,
        "SORT": "DESC"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("result", {}).get("messages", [])

def get_user_info(webhook, user_ids):
    url = f"{webhook}/user.get.json"
    users = {}
    for user_id in user_ids:
        response = requests.get(url, params={"ID": user_id})
        response.raise_for_status()
        result = response.json().get("result", [])
        if result:
            user = result[0]
            users[user_id] = {
                "name": user.get("NAME", "") + " " + user.get("LAST_NAME", ""),
                "position": user.get("WORK_POSITION", ""),
                "phone": user.get("PERSONAL_MOBILE", ""),
                "email": user.get("EMAIL", ""),
            }
        time.sleep(0.1)
    return users
