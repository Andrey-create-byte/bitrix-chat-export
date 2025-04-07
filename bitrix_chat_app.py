import streamlit as st
import requests
import json
from datetime import datetime
import os

# === Секреты ===
WEBHOOK = st.secrets["WEBHOOK"]
OUTPUT_FOLDER = "bitrix_chat_exports"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === Получение списка чатов ===
def get_chat_list():
    r = requests.get(WEBHOOK + "im.recent.get").json()
    return r.get("result", [])

# === Получение сообщений через im.dialog.messages.get ===
def get_chat_history(dialog_id, limit=2000):
    messages = []
    offset = 0
    while True:
        r = requests.get(WEBHOOK + "im.dialog.messages.get", params={
            "DIALOG_ID": dialog_id,
            "LIMIT": 200,
            "OFFSET": offset
        }).json()
        batch = r.get("result", {}).get("messages", [])
        if not batch:
            break
        messages.extend(batch)
        if len(batch) < 200 or len(messages) >= limit:
            break
        offset += 200
    return messages

# === Экспорт в файл ===
def export_chat(chat, debug=False):
    chat_id = chat.get("chat_id") or chat.get("id")
    dialog_id = f"chat{chat_id}" if chat.get("type") == "chat" else str(chat_id)
    name = chat.get("title", f"chat_{chat_id}")
    messages = get_chat_history(dialog_id)

    if debug:
        st.subheader("Отладочная информация (первые 2 сообщения):")
        st.write(messages[:2])

    exported = {
        "chat_id": chat_id,
        "chat_name": name,
        "type": chat.get("type", "chat"),
        "messages": []
    }

    for msg in messages:
        exported["messages"].append({
            "id": msg.get("ID"),
            "timestamp": msg.get("DATE_CREATE"),
            "author_id": msg.get("AUTHOR_ID"),
            "text": msg.get("MESSAGE")
        })

    filename = f"{OUTPUT_FOLDER}/chat_{chat_id}_full.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
    return filename

# === Streamlit UI ===
st.set_page_config(page_title="Bitrix24 Chat Exporter")
st.title("Экспорт чатов из Bitrix24")

with st.spinner("Загружаем список чатов..."):
    chats = get_chat_list()

if not chats:
    st.error("Список чатов пуст. Убедитесь, что вебхук активен и у пользователя есть доступ к чатам.")
    st.stop()

chat_options = {
    f"{chat.get('title', 'Без названия')} (ID: {chat.get('chat_id')})": chat
    for chat in chats
    if chat.get("type") in ("chat", "sonetGroup", "calendar", "tasks", "user")
}
selected_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat = chat_options[selected_name]

debug_mode = st.checkbox("Показать отладочную информацию")

if st.button("Выгрузить все сообщения"):
    with st.spinner("Экспортируем..."):
        file_path = export_chat(selected_chat, debug=debug_mode)
        with open(file_path, "rb") as f:
            st.download_button("Скачать JSON", f, file_name=os.path.basename(file_path))
            
