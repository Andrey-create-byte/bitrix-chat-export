import streamlit as st
import requests
import json
import io
from datetime import datetime, date

# Читаем WEBHOOK из секрета
WEBHOOK = st.secrets["WEBHOOK"]

# Получение списка чатов
def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    st.write("Статус ответа:", response.status_code)
    if response.status_code != 200:
        st.error(f"Ошибка ответа сервера: {response.text}")
        return []
    try:
        result = response.json().get("result", [])
        return result
    except json.JSONDecodeError:
        st.error("Ошибка разбора JSON ответа.")
        return []

# Получение истории сообщений для чата
def get_chat_history(dialog_id, limit=50):
    all_messages = []
    seen_ids = set()
    last_id = 0

    while True:
        params = {
            "DIALOG_ID": dialog_id,
            "LIMIT": limit
        }
        if last_id:
            params["LAST_ID"] = last_id

        url = f"{WEBHOOK}/im.dialog.messages.get"
        response = requests.get(url, params=params)

        if response.status_code != 200:
            st.error(f"Ошибка получения сообщений: {response.text}")
            break

        result = response.json().get("result", {})
        messages = result
