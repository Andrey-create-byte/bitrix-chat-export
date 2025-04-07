import streamlit as st
import requests
import json
from datetime import datetime
from io import BytesIO

# === Секреты ===
WEBHOOK = st.secrets["WEBHOOK"]

# === Получение списка чатов ===
def get_chats():
    res = requests.get(f"{WEBHOOK}/im.recent.get").json()
    chats = []
    for item in res.get("result", []):
        if item["type"] == "chat":  # Только групповые чаты
            chats.append({
                "id": item["chat_id"],
                "name": item["title"]
            })
    return chats

# === Получение сообщений ===
def get_chat_history(chat_id):
    messages = []
    offset = 0
    batch = 50
    total_loaded = 0
    previous_count = -1

    while True:
        res = requests.post(f"{WEBHOOK}/im.dialog.messages.get", json={
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": batch,
            "OFFSET": offset
        }).json()

        chunk = res.get("result", {}).get("messages", [])
        messages.extend(chunk)

        if len(messages) == previous_count:
            break

        previous_count = len(messages)
        offset += batch

    return list(reversed(messages))

# === Преобразование в экспортируемый формат ===
def export_chat(chat_id, chat_name, chat_type, messages):
    export = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "type": chat_type,
        "participants": [],
        "messages": []
    }

    for msg in messages:
        msg_type = "text"
        attachments = []

        if isinstance(msg, dict) and "file" in msg:
            msg_type = "file"
            file = msg["file"]
            attachments.append({
                "filename": file.get("name"),
                "type": file.get("type"),
                "size": file.get("size"),
                "url": file.get("url")
            })

        export["messages"].append({
            "id": msg.get("id"),
            "timestamp": msg.get("date"),
            "author": msg.get("author_id"),
            "text": msg.get("text"),
            "type": msg_type,
            "attachments": attachments
        })

    return export

# === Интерфейс Streamlit ===
st.title("Экспорт чатов из Bitrix24")

chat_options = get_chats()
selected = st.selectbox("Выберите чат:", chat_options, format_func=lambda x: f'{x["name"]} (ID: {x["id"]})')

if st.button("Выгрузить чат"):
    all_messages = get_chat_history(selected["id"])
    export_data = export_chat(selected["id"], selected["name"], "group_chat", all_messages)

    # Сохранение в памяти
    json_bytes = BytesIO()
    json_bytes.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
    json_bytes.seek(0)

    st.download_button(
        label="Скачать JSON-файл",
        data=json_bytes,
        file_name=f"chat_{selected['id']}.json",
        mime="application/json"
    )

    st.success(f"Загружено {len(all_messages)} сообщений.")
