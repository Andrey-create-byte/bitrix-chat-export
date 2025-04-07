import streamlit as st
import json
import os
import time
import requests

# === Секреты ===
WEBHOOK = st.secrets["WEBHOOK"]
OUTPUT_FOLDER = "bitrix_chat_exports"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === Получение списка чатов ===
def get_chat_list():
    r = requests.get(WEBHOOK + "im.recent.get").json()
    return r.get("result", [])

# === Получение сообщений постранично по OFFSET ===
def get_all_messages(chat_id, limit=50, sleep_between=0.3):
    offset = 0
    all_messages = []
    total_loaded = 0

    while True:
        response = requests.post(
            url=WEBHOOK + 'im.dialog.messages.get',
            json={
                "DIALOG_ID": f"chat{chat_id}",
                "LIMIT": limit,
                "OFFSET": offset
            }
        )
        data = response.json()

        if 'result' not in data or 'messages' not in data['result']:
            st.error(f"Ошибка или неожиданный ответ API: {data}")
            break

        messages = data['result']['messages']
        all_messages.extend(messages)
        total_loaded += len(messages)

        st.write(f"Загружено {len(messages)} сообщений (offset = {offset})")

        if len(messages) < limit:
            st.success(f"Все сообщения загружены. Всего: {total_loaded}")
            break

        offset += limit
        time.sleep(sleep_between)

    return all_messages

# === Экспорт в JSON-файл ===
def export_chat(chat, debug=False):
    chat_id = chat.get("chat_id") or chat.get("id")
    name = chat.get("title", f"chat_{chat_id}")

    messages = get_all_messages(chat_id)

    filtered = [
        {
            "id": msg.get("id"),
            "timestamp": msg.get("date"),
            "author_id": msg.get("author_id"),
            "text": msg.get("text")
        }
        for msg in messages if msg.get("text")
    ]

    if debug:
        st.subheader("Отладочная информация (первые 100 сообщений):")
        st.write(filtered[:100])

    exported = {
        "chat_id": chat_id,
        "chat_name": name,
        "type": chat.get("type", "chat"),
        "messages": filtered
    }

    filename = f"{OUTPUT_FOLDER}/chat_{chat_id}_full.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
    return filename

# === Интерфейс Streamlit ===
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
