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
    result = []
    r = requests.get(WEBHOOK + "im.recent.get").json()
    for item in r.get("result", []):
        chat = item.get("CHAT")
        if chat and chat.get("TYPE") in (
            "chat", "open", "call", "sonetGroup", "calendar", "tasks"
        ):
            result.append(chat)
    return result

def get_openline_dialogs():
    result = set()
    r = requests.get(WEBHOOK + "imopenlines.session.list", params={"LIMIT": 100}).json()
    for session in r.get("result", []):
        result.add(session["CHAT_ID"])
    return list(result)

def get_chat_history(chat_id, limit=200):
    messages = []
    start = 0
    while True:
        r = requests.get(WEBHOOK + "im.dialog.messages.get", params={
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": limit,
            "OFFSET": start
        }).json()
        batch = r.get("result", {}).get("messages", [])
        messages += batch
        if len(batch) < limit:
            break
        start += limit
    return messages

def export_chat(chat, date_from, date_to):
    chat_id = chat["ID"]
    name = chat.get("NAME", f"chat_{chat_id}")
    messages = get_chat_history(chat_id)
    participants = chat.get("USER_IDS", [])
    exported = {
        "chat_id": chat_id,
        "chat_name": name,
        "type": chat.get("TYPE", "chat"),
        "participants": participants,
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

    filename = f"{OUTPUT_FOLDER}/chat_{chat_id}_{date_from.date()}_{date_to.date()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
    return filename

# === STREAMLIT UI ===
st.set_page_config(page_title="Bitrix24 Chat Exporter")
st.title("Экспорт чатов из Bitrix24")

with st.spinner("Загружаем список чатов..."):
    group_chats = get_chat_list()
    openline_ids = get_openline_dialogs()
    filtered_chats = [
        chat for chat in group_chats
        if int(chat["ID"]) in openline_ids or chat.get("TYPE") in (
            "chat", "open", "call", "sonetGroup", "calendar", "tasks"
        )
    ]

if not filtered_chats:
    st.error("Список чатов пуст. Убедитесь, что вебхук активен и у пользователя есть доступ к групповым чатам или открытым линиям.")
    st.stop()
else:
    chat_options = {
        f"{chat.get('NAME', 'Без имени')} (ID: {chat['ID']})": chat
        for chat in filtered_chats
    }
    selected_chat_name = st.selectbox("Выберите чат или открытую линию:", list(chat_options.keys()))
    selected_chat = chat_options[selected_chat_name]

    date_from = st.date_input("Дата С")
    date_to = st.date_input("Дата ПО")

    if st.button("Выгрузить чат"):
        with st.spinner("Экспортируем сообщения..."):
            dt_from = datetime.combine(date_from, datetime.min.time()).astimezone()
            dt_to = datetime.combine(date_to, datetime.max.time()).astimezone()
            filepath = export_chat(selected_chat, dt_from, dt_to)
            with open(filepath, "rb") as f:
                st.download_button("Скачать JSON", f, file_name=os.path.basename(filepath))
