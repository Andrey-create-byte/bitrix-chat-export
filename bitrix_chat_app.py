import streamlit as st
import requests
import json
from datetime import datetime

WEBHOOK = st.secrets["WEBHOOK"]


def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    return response.json().get("result", [])


def get_chat_history(chat_id, limit=50):
    offset = 0
    all_messages = []
    previous_count = -1

    while True:
        url = f"{WEBHOOK}/im.dialog.messages.get"
        params = {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": limit,
            "OFFSET": offset
        }
        response = requests.get(url, params=params)
        messages = response.json().get("result", {}).get("messages", [])

        if not messages:
            break

        all_messages.extend(messages)
        offset += limit

        if len(all_messages) == previous_count:
            break
        previous_count = len(all_messages)

    return all_messages


def extract_participants(chat):
    if chat.get("type") == "chat":
        return [user["name"] for user in chat.get("users", [])]
    return []


def export_chat(chat_id, chat_name, messages):
    export = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "type": "group_chat",
        "participants": [],
        "messages": []
    }
    for msg in messages:
        export["messages"].append({
            "id": msg["id"],
            "timestamp": msg["date"],
            "author": msg["author_id"],
            "text": msg["text"],
            "type": "file" if msg.get("params", {}).get("FILES") else "text",
            "attachments": []
        })
    return export


st.title("Экспорт чатов из Bitrix24")

# Получение списка чатов
chats = get_recent_chats()
group_chats = [chat for chat in chats if chat["type"] == "chat"]

chat_map = {f'{chat["title"]} (ID: {chat["chat_id"]})': chat["chat_id"] for chat in group_chats}
selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]

    if st.button("Выгрузить все сообщения"):
        st.info("Загружаем сообщения...")
        all_messages = get_chat_history(selected_chat_id)
        st.success(f"Загрузка завершена. Всего сообщений: {len(all_messages)}")

        # Отладочная информация
        st.subheader("Отладочная информация (первые 2 сообщения):")
        st.json(all_messages[:2])

        export_data = export_chat(selected_chat_id, selected_chat_title, all_messages)
        with open("exported_chat.json", "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        with open("exported_chat.json", "rb") as f:
            st.download_button("Скачать JSON", f, file_name="exported_chat.json", mime="application/json")
            
