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
        messages += batch
        if len(batch) < limit:
            break
        offset += limit
    return messages

def export_chat(chat, date_from, date_to):
    raw_chat_id = chat["chat_id"]
    dialog_id = raw_chat_id if str(raw_chat_id).startswith("chat") else f"chat{raw_chat_id}"
    name = chat.get("title", f"chat_{raw_chat_id}")
    messages = get_chat_history(dialog_id)
    
    exported = {
        "chat_id": raw_chat_id,
        "chat_name": name,
        "type": chat.get("type", "chat"),
        "participants": [],  # можно доработать
        "messages": []
    }

    for msg in messages:
        msg_time = datetime.strptime(msg["DATE_CREATE"], "%Y-%m-%dT%H:%M:%S%z")
        if not (date_from <= msg_time <= date_to):
            continue

        attachments = []
        if "ATTACH" in msg:
            for block in msg["ATTACH"].get("BLOCKS", []):
                if block.get("TYPE") == "FILE":
                    attachments.append({
                        "filename": block["NAME"],
                        "url": block["LINK"]
                    })
        exported["messages"].append({
            "id": msg["ID"],
            "timestamp": msg["DATE_CREATE"],
            "author_id": msg["AUTHOR_ID"],
            "text": msg["MESSAGE"],
            "type": "text" if not attachments else "file",
            "attachments": attachments
        })

    filename = f"{OUTPUT_FOLDER}/chat_{raw_chat_id}_{date_from.date()}_{date_to.date()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
    return filename

# === UI ===
st.set_page_config(page_title="Bitrix24 Chat Exporter")
st.title("Экспорт чатов из Bitrix24")

with st.spinner("Загружаем список чатов..."):
    chats = get_chat_list()

if not chats:
    st.error("Список чатов пуст. Убедитесь, что вебхук активен и у пользователя есть доступ к чатам.")
    st.stop()

chat_options = {f"{chat.get('title', 'Без названия')} (ID: {chat['chat_id']})": chat for chat in chats}
selected_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat = chat_options[selected_name]

date_from = st.date_input("С какой даты", value=datetime.today())
date_to = st.date_input("По какую дату", value=datetime.today())

if st.button("Выгрузить"):
    with st.spinner("Экспортируем..."):
        dt_from = datetime.combine(date_from, datetime.min.time()).astimezone()
        dt_to = datetime.combine(date_to, datetime.max.time()).astimezone()
        file_path = export_chat(selected_chat, dt_from, dt_to)
        with open(file_path, "rb") as f:
            st.download_button("Скачать JSON", f, file_name=os.path.basename(file_path))
            
