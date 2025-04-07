import streamlit as st
import requests
import json
from datetime import datetime
import os

# === Секреты ===
WEBHOOK = st.secrets["WEBHOOK"]
OUTPUT_FOLDER = "bitrix_chat_exports"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === Получение списка чатов из im.recent.get ===
def get_recent_chats():
    r = requests.get(WEBHOOK + "im.recent.get").json()
    chats = []
    for item in r.get("result", []):
        if item.get("type") in ("chat", "open", "call", "sonetGroup", "calendar", "tasks"):
            chats.append({
                "title": item.get("title", "Без имени"),
                "chat_id": item.get("chat_id"),
                "type": item.get("type"),
            })
    return chats

# === История сообщений ===
def get_chat_history(chat_id, limit=200):
    messages = []
    offset = 0
    while True:
        r = requests.get(WEBHOOK + "im.dialog.messages.get", params={
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": limit,
            "OFFSET": offset
        }).json()
        batch = r.get("result", {}).get("messages", [])
        messages += batch
        if len(batch) < limit:
            break
        offset += limit
    return messages

# === Экспорт в файл ===
def export_chat(chat, date_from, date_to):
    messages = get_chat_history(chat["chat_id"])
    filtered = []

    for msg in messages:
        ts = datetime.strptime(msg["DATE_CREATE"], "%Y-%m-%dT%H:%M:%S%z")
        if not (date_from <= ts <= date_to):
            continue
        filtered.append({
            "id": msg["ID"],
            "author_id": msg["AUTHOR_ID"],
            "timestamp": msg["DATE_CREATE"],
            "text": msg["MESSAGE"]
        })

    output = {
        "chat_id": chat["chat_id"],
        "title": chat["title"],
        "type": chat["type"],
        "messages": filtered
    }

    filename = f"{OUTPUT_FOLDER}/chat_{chat['chat_id']}_{date_from.date()}_{date_to.date()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return filename

# === Streamlit UI ===
st.set_page_config(page_title="Bitrix24 Chat Exporter")
st.title("Экспорт чатов из Bitrix24")

with st.spinner("Загружаем список чатов..."):
    chats = get_recent_chats()

if not chats:
    st.warning("Нет доступных чатов.")
    st.stop()

chat_options = {f"{chat['title']} (ID: {chat['chat_id']})": chat for chat in chats}
selected_chat_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat = chat_options[selected_chat_name]

date_from = st.date_input("С какой даты")
date_to = st.date_input("По какую дату")

if st.button("Выгрузить"):
    with st.spinner("Экспортируем..."):
        dt_from = datetime.combine(date_from, datetime.min.time()).astimezone()
        dt_to = datetime.combine(date_to, datetime.max.time()).astimezone()
        file_path = export_chat(selected_chat, dt_from, dt_to)
        with open(file_path, "rb") as f:
            st.download_button("Скачать JSON", f, file_name=os.path.basename(file_path))
            
