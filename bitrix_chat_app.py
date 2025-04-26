import streamlit as st
import requests
import json
import io
from datetime import datetime

# Читаем WEBHOOK из секрета
WEBHOOK = st.secrets["WEBHOOK"]

# Получение списка чатов
def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    result = response.json().get("result", [])
    return result

# Получение истории сообщений
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

        # Убираем дубли
        new_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("id") not in seen_ids]
        if not new_messages:
            break

        all_messages.extend(new_messages)
        seen_ids.update(msg["id"] for msg in new_messages)
        last_id = min(msg["id"] for msg in new_messages)

    return all_messages

# Экспорт чата в JSON
def export_chat(chat_id, chat_name, messages):
    export = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "messages": []
    }
    for msg in messages:
        export["messages"].append({
            "id": msg.get("id"),
            "timestamp": msg.get("date"),
            "author_id": msg.get("author_id"),
            "text": msg.get("text"),
            "params": msg.get("params", {})
        })
    return export

# Основной интерфейс
st.title("Экспорт истории чатов из Bitrix24")

# Загружаем чаты
chats = get_recent_chats()
group_chats = [chat for chat in chats if chat.get("CHAT_TYPE") == "chat"]

if not group_chats:
    st.error("Нет доступных групповых чатов для экспорта.")
    st.stop()

# Формируем карту для выбора
chat_map = {f'{chat.get("TITLE", "Без названия")} (ID: {chat["CHAT_ID"]})': chat["CHAT_ID"] for chat in group_chats}
selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]

    if st.button("Выгрузить все сообщения"):
        st.info("Загружаем сообщения...")
        all_messages = get_chat_history(selected_chat_id)
        st.success(f"Загрузка завершена. Всего сообщений: {len(all_messages)}")

        # Отладочная информация
        st.subheader("Первые 2 сообщения для проверки:")
        st.json(all_messages[:2])

        # Экспортируем данные
        export_data = export_chat(selected_chat_id, selected_chat_title, all_messages)

        buffer = io.BytesIO()
        buffer.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
        buffer.seek(0)

        st.download_button(
            "Скачать историю чата в JSON",
            buffer,
            file_name=f"chat_{selected_chat_id}_history.json",
            mime="application/json"
        )
