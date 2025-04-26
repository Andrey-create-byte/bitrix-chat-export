import streamlit as st
import requests
import json
import io
from datetime import datetime, date
import dateutil.parser
import time

# === Инициализация из Streamlit ===
WEBHOOK = st.secrets["WEBHOOK"]

# Получение списка чатов
def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    if response.status_code != 200:
        st.error(f"Ошибка получения чатов: {response.text}")
        return []
    try:
        result = response.json().get("result", [])
        return result
    except json.JSONDecodeError:
        st.error("Ошибка разбора JSON при получении чатов.")
        return []

# Получение сообщений чата с полными параметрами
def get_messages(dialog_id, last_id=0, limit=50):
    params = {
        "DIALOG_ID": dialog_id,
        "LIMIT": limit,
        "WITH_FILES": "Y",
        "WITH_ATTACH": "Y",
        "WITH_FORWARD": "Y",
        "WITH_PARAMS": "Y",
    }
    if last_id:
        params["LAST_ID"] = last_id
    url = f"{WEBHOOK}/im.dialog.messages.get"
    response = requests.get(url, params=params)
    if response.status_code != 200:
        st.error(f"Ошибка запроса сообщений: {response.text}")
        return None
    return response.json().get("result", {})

# Загрузка всей переписки
def load_full_history(dialog_id, max_messages=5000):
    all_messages = []
    seen_ids = set()
    last_id = 0
    loaded = 0

    while loaded < max_messages:
        data = get_messages(dialog_id, last_id)
        if not data or not data.get("messages"):
            break

        messages = data["messages"]
        for msg in messages:
            msg_id = msg.get("id")
            if msg_id and msg_id not in seen_ids:
                all_messages.append(msg)
                seen_ids.add(msg_id)

        last_id = min([msg["id"] for msg in messages if "id" in msg])
        loaded += len(messages)
        time.sleep(0.2)

    return all_messages

# Фильтрация сообщений по дате
def filter_messages_by_date(messages, start_date, end_date):
    filtered = []
    for msg in messages:
        msg_date_str = msg.get("date")
        if msg_date_str:
            try:
                msg_datetime = dateutil.parser.isoparse(msg_date_str)
                if start_date <= msg_datetime.date() <= end_date:
                    filtered.append(msg)
            except Exception:
                continue
    return filtered

# === Интерфейс Streamlit ===
st.title("Bitrix24: Полная выгрузка чата по датам")

# 1. Выбор чата
chats = get_recent_chats()
if not chats:
    st.stop()

chat_map = {f'{chat.get("title", "Без названия")} (ID: {chat.get("chat_id")})': chat["chat_id"] for chat in chats if "chat_id" in chat}
selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]
    dialog_id = f"chat{selected_chat_id}"

    # 2. Выбор периода дат
    today = date.today()
    start_date = st.date_input("Начальная дата", value=today.replace(day=1))
    end_date = st.date_input("Конечная дата", value=today)

    if start_date > end_date:
        st.error("Начальная дата должна быть раньше конечной даты.")
        st.stop()

    # 3. Выбор лимита сообщений
    max_messages = st.slider("Максимальное количество сообщений для загрузки", 100, 10000, step=100, value=1000)

    # 4. Кнопка загрузки
    if st.button("Загрузить историю чата"):
        st.info("Загружаем сообщения...")
        all_messages = load_full_history(dialog_id, max_messages=max_messages)

        if not all_messages:
            st.error("Сообщений не найдено.")
            st.stop()

        st.success(f"Загружено сообщений: {len(all_messages)}")

        # Фильтрация по выбранному диапазону дат
        filtered_messages = filter_messages_by_date(all_messages, start_date, end_date)

        st.success(f"Сообщений в выбранном диапазоне: {len(filtered_messages)}")

        buffer = io.BytesIO()
        buffer.write(json.dumps(filtered_messages, ensure_ascii=False, indent=2).encode("utf-8"))
        buffer.seek(0)

        st.download_button(
            "Скачать переписку",
            buffer,
            file_name=f"chat_{selected_chat_id}_export_{start_date}_to_{end_date}.json",
            mime="application/json"
        )
