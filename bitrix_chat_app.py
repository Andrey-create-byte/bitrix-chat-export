import streamlit as st
import requests
import json
from datetime import datetime
import os

# === Секреты ===
WEBHOOK = st.secrets["WEBHOOK"]
OUTPUT_FOLDER = "bitrix_chat_exports"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === ФУНКЦИИ ===

def get_chat_list():
    r = requests.get(WEBHOOK + "im.recent.get").json()
    return r.get("result", [])

def get_chat_history(dialog_id, limit=200):
    messages = []
    offset = 0
    while True:
        r = requests.get(WEBHOOK + "im.dialog.messages.get", params={
            "DIALOG_ID": dialog_id,
            "LIMIT": limit,
            "OFFSET": offset
        }).json()
        batch = r.get("result", {}).get("messages", [])
        if not batch:
            break
        messages.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return messages

def export_chat(chat, date_from, date_to):
    chat_id = chat.get("chat_id") or chat.get("id")
    dialog_id = f"chat{chat_id}" if chat["type"] == "chat" else str(chat_id)
    name = chat.get("title", f"chat_{chat_id}")
    messages = get_chat_history(dialog_id)

    exported = {
        "chat_id": chat_id,
        "chat_name": name,
        "type": chat["type"],
        "messages": []
    }

    for msg in messages:
        ts_raw = msg.get("DATE_CREATE")
        if not ts_raw:
            continue
        ts = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S%z")
        if not (date_from <= ts <= date_to):
            continue

        exported["messages"].append({
            "id": msg["ID"],
            "timestamp": msg["DATE_CREATE"],
            "author_id": msg["AUTHOR_ID"],
            "text": msg["MESSAGE"],
        })

    filename = f"{OUTPUT_FOLDER}/chat_{chat_id}_{date_from.date()}_{date_to.date()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
    return filename

# === STREAMLIT UI ===

st.set_page_config(page_title="Bitrix24 Chat Exporter")
st.title("Экспорт чатов из Bitrix24")

with st.spinner("Загружаем список чатов..."):
    chats = get_chat_list()

if not chats:
    st.error("Список чатов пуст. Убедитесь, что вебхук активен и у пользователя есть доступ к чатам.")
    st.stop()

chat_options = {f"{chat['title']} (ID: {chat['chat_id']})": chat for chat in chats if chat["type"] in ("chat", "sonetGroup", "calendar", "tasks", "user")}
selected_chat_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat = chat_options[selected_chat_name]

date_from = st.date_input("С какой даты", value=datetime.now().date())
date_to = st.date_input("По какую дату", value=datetime.now().date())

if st.button("Выгрузить"):
    with st.spinner("Экспортируем..."):
        dt_from = datetime.combine(date_from, datetime.min.time()).astimezone()
        dt_to = datetime.combine(date_to, datetime.max.time()).astimezone()
        file_path = export_chat(selected_chat, dt_from, dt_to)
        with open(file_path, "rb") as f:
            st.download_button("Скачать JSON", f, file_name=os.path.basename(file_path))
            
