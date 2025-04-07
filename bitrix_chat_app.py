import streamlit as st
import requests
import json
from datetime import datetime, date
import io
from dateutil.parser import parse

WEBHOOK = st.secrets["WEBHOOK"]

def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    return response.json().get("result", [])

def get_chat_history(chat_id, limit=50):
    all_messages = []
    seen_ids = set()
    last_id = 0

    while True:
        params = {
            "DIALOG_ID": f"chat{chat_id}",
            "LIMIT": limit
        }
        if last_id:
            params["LAST_ID"] = last_id

        url = f"{WEBHOOK}/im.dialog.messages.get"
        response = requests.get(url, params=params)
        result = response.json().get("result", {})
        messages = result.get("messages", [])

        if not messages:
            break

        new_messages = [msg for msg in messages if isinstance(msg, dict) and msg["id"] not in seen_ids]
        if not new_messages:
            break

        all_messages.extend(new_messages)
        seen_ids.update(msg["id"] for msg in new_messages)
        last_id = min(msg["id"] for msg in new_messages)

    return all_messages

def export_chat(chat_id, chat_name, messages, date_from=None, date_to=None):
    export = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "type": "group_chat",
        "participants": [],
        "messages": []
    }
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        msg_date_str = msg.get("DATE_CREATE") or msg.get("date")
        if not msg_date_str:
            continue
        try:
            msg_date = parse(msg_date_str)
        except:
            continue

        # Отладочный вывод
        st.write("msg_date =", msg_date, "| from =", date_from, "| to =", date_to)

        if date_from and msg_date < date_from:
            continue
        if date_to and msg_date > date_to:
            continue

        params = msg.get("params", {})
        is_file = isinstance(params, dict) and params.get("FILES")
        msg_type = "file" if is_file else "text"

        export["messages"].append({
            "id": msg.get("id"),
            "timestamp": msg_date_str,
            "author": msg.get("author_id"),
            "text": msg.get("text"),
            "type": msg_type,
            "attachments": []
        })
    return export

st.title("Экспорт чатов из Bitrix24")

# Получение списка чатов
chats = get_recent_chats()
group_chats = [chat for chat in chats if chat["type"] == "chat"]

chat_map = {f'{chat["title"]} (ID: {chat["chat_id"]})': chat["chat_id"] for chat in group_chats}
selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

# Фильтр по дате
st.subheader("Фильтр по дате")
def_date_from = date(2024, 1, 1)
def_date_to = date.today()
date_from = st.date_input("С какой даты", def_date_from)
date_to = st.date_input("По какую дату", def_date_to)

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]

    if st.button("Выгрузить сообщения"):
        st.info("Загружаем сообщения...")
        all_messages = get_chat_history(selected_chat_id)
        st.success(f"Загрузка завершена. Всего сообщений: {len(all_messages)}")

        # Отладочная информация
        st.subheader("Отладочная информация (первые 2 сообщения):")
        st.json(all_messages[:2])

        dt_from = parse(datetime.combine(date_from, datetime.min.time()).isoformat())
        dt_to = parse(datetime.combine(date_to, datetime.max.time()).isoformat())
        export_data = export_chat(selected_chat_id, selected_chat_title, all_messages, dt_from, dt_to)

        buffer = io.BytesIO()
        buffer.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
        buffer.seek(0)

        st.download_button("Скачать JSON", buffer, file_name="exported_chat.json", mime="application/json")
