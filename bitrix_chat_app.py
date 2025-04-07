import requests
import datetime
import time
import os
import json

# Webhook Bitrix24
WEBHOOK = "ВАШ_WEBHOOK_BITRIX24"

# Папка для выгрузки
EXPORT_DIR = "bitrix_chat_exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

# Сохраняем JSON-файл
def save_raw_json(data, filename):
    filepath = os.path.join(EXPORT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Получение всех чатов (групповых и открытых линий)
def get_group_and_openline_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    result = response.json().get("result", [])
    chats = []
    for item in result:
        if item.get("type") == "chat" or item.get("chat", {}).get("entity_type").upper() == "LINES":
            chats.append({
                "id": item["chat_id"],
                "name": item["title"],
                "type": "open_line" if item.get("chat", {}).get("entity_type").upper() == "LINES" else "group_chat"
            })
    return chats

# Получение пользователей по ID
USER_CACHE = {}
def get_user_name(user_id):
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]
    url = f"{WEBHOOK}/user.get?id={user_id}"
    r = requests.get(url).json()
    user = r.get("result", [{}])[0]
    full_name = f"{user.get('name', '')} {user.get('last_name', '')}".strip()
    USER_CACHE[user_id] = full_name
    return full_name

# Получение сообщений из чата
def get_chat_messages(chat_id, date_from=None, date_to=None):
    messages = []
    offset = 0
    batch_size = 50
    while True:
        url = f"{WEBHOOK}/im.dialog.messages.get"
        params = {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": batch_size,
            "OFFSET": offset,
            "SORT": "ASC"
        }
        resp = requests.post(url, data=params).json()
        batch = resp.get("result", {}).get("messages", [])
        if not batch:
            break
        for msg in batch:
            msg_date = datetime.datetime.fromisoformat(msg["date"].replace("+03:00", ""))
            if date_from and msg_date < date_from:
                continue
            if date_to and msg_date > date_to:
                continue
            messages.append({
                "id": msg["id"],
                "timestamp": msg["date"],
                "author": get_user_name(msg["author_id"]),
                "text": msg.get("text", ""),
                "type": "file" if msg.get("file") else "text",
                "attachments": [{
                    "filename": msg["file"]["name"],
                    "type": msg["file"]["type"],
                    "size": msg["file"]["size"],
                    "url": msg["file"]["urlPreview"]
                }] if msg.get("file") else []
            })
        offset += batch_size
        time.sleep(0.3)
    return messages

# Экспорт выбранного чата
def export_chat(chat_id, chat_name, chat_type, date_from=None, date_to=None):
    print(f"Выгружаем: {chat_name} ({chat_type})")
    messages = get_chat_messages(chat_id, date_from, date_to)
    participants = list(set([m["author"] for m in messages]))
    export_data = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "type": chat_type,
        "participants": participants,
        "messages": messages
    }
    save_raw_json(export_data, f"chat_{chat_id}_export.json")
    print(f"Сохранено: chat_{chat_id}_export.json ({len(messages)} сообщений)")

# === Пример запуска ===
if __name__ == "__main__":
    chats = get_group_and_openline_chats()
    for chat in chats:
        export_chat(
            chat_id=chat["id"],
            chat_name=chat["name"],
            chat_type=chat["type"],
            date_from=datetime.datetime(2025, 4, 1),
            date_to=datetime.datetime(2025, 4, 7)
        )
        
