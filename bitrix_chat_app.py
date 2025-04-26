import streamlit as st
import requests
import json
import io
import time
from datetime import date
import dateutil.parser

WEBHOOK = st.secrets["WEBHOOK"]

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

def get_forwarded_message(forward_id):
    url = f"{WEBHOOK}/im.message.get"
    params = {"ID": forward_id}
    tries = 0
    while tries < 3:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            try:
                result = response.json().get("result", {})
                text = result.get("message", {}).get("text", "")
                if text:
                    return text
            except Exception:
                pass
        time.sleep(0.5)
        tries += 1
    return None

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

def get_user_info(user_id):
    url = f"{WEBHOOK}/user.get"
    params = {"ID": user_id}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    try:
        result = response.json().get("result", [])
        if result and isinstance(result, list):
            return result[0]
    except Exception:
        return None

def enrich_messages(messages):
    author_ids = {msg.get("author_id") for msg in messages if msg.get("author_id")}
    author_info_map = {}

    for author_id in author_ids:
        user_info = get_user_info(author_id)
        if user_info:
            author_info_map[author_id] = {
                "full_name": f"{user_info.get('LAST_NAME', '')} {user_info.get('NAME', '')}".strip(),
                "work_position": user_info.get('WORK_POSITION', '')
            }
        else:
            author_info_map[author_id] = {
                "full_name": "Неизвестный пользователь",
                "work_position": ""
            }
        time.sleep(0.1)

    for msg in messages:
        author_id = msg.get("author_id")
        author_info = author_info_map.get(author_id, {"full_name": "Неизвестный пользователь", "work_position": ""})
        msg["author_name"] = author_info["full_name"]
        msg["author_position"] = author_info["work_position"]

        forward_id = None
        if "params" in msg and isinstance(msg["params"], dict):
            forward_id = msg["params"].get("FORWARD_ID")
        if forward_id:
            forwarded_text = get_forwarded_message(forward_id)
            if forwarded_text:
                msg["forward_text"] = forwarded_text
            else:
                msg["forward_text"] = "(Пересланное сообщение не доступно)"

        if "forward_text" not in msg:
            msg["forward_text"] = ""

    return messages

st.title("Bitrix24: Полная выгрузка чата с ФИО и текстами пересланных сообщений")

chats = get_recent_chats()
if not chats:
    st.stop()

chat_map = {f'{chat.get("title", "Без названия")} (ID: {chat.get("chat_id")})': chat["chat_id"] for chat in chats if "chat_id" in chat}
selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]
    dialog_id = f"chat{selected_chat_id}"

    today = date.today()
    start_date = st.date_input("Начальная дата", value=today.replace(day=1))
    end_date = st.date_input("Конечная дата", value=today)

    if start_date > end_date:
        st.error("Начальная дата должна быть раньше конечной.")
        st.stop()

    max_messages = st.slider("Максимальное количество сообщений для загрузки", 100, 10000, step=100, value=1000)

    if st.button("Загрузить историю чата"):
        st.info("Загружаем сообщения...")
        all_messages = load_full_history(dialog_id, max_messages=max_messages)

        if not all_messages:
            st.error("Сообщений не найдено.")
            st.stop()

        st.success(f"Загружено сообщений: {len(all_messages)}")

        filtered_messages = filter_messages_by_date(all_messages, start_date, end_date)

        st.success(f"Сообщений в выбранном диапазоне: {len(filtered_messages)}")

        enriched_messages = enrich_messages(filtered_messages)

        buffer = io.BytesIO()
        buffer.write(json.dumps(enriched_messages, ensure_ascii=False, indent=2).encode("utf-8"))
        buffer.seek(0)

        st.download_button(
            "Скачать переписку с ФИО и текстами пересланных сообщений",
            buffer,
            file_name=f"chat_{selected_chat_id}_export_{start_date}_to_{end_date}_full.json",
            mime="application/json"
        )
