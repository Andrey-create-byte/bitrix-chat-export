import streamlit as st
import requests
import json
import io
from datetime import datetime, date
import dateutil.parser

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

# Глубокая загрузка всех сообщений для чата
def get_chat_history(dialog_id, limit=50, max_messages=5000):
    all_messages = []
    seen_ids = set()
    last_id = 0
    count = 0

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
        messages = result.get("messages", [])

        if not messages:
            break

        new_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("id") not in seen_ids]
        if not new_messages:
            break

        all_messages.extend(new_messages)
        seen_ids.update(msg["id"] for msg in new_messages)
        last_id = min(msg["id"] for msg in new_messages if "id" in msg)

        count += len(new_messages)
        if count >= max_messages:
            st.warning(f"Загружено {max_messages} сообщений. Дальнейшая загрузка остановлена.")
            break

    return all_messages

# Получение информации о пользователе
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

# Экспорт чата в JSON
def export_chat(chat_id, chat_name, messages, author_info_map):
    export = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "messages": []
    }
    for msg in messages:
        author_id = msg.get("author_id")
        author_info = author_info_map.get(author_id, {"full_name": "Неизвестный пользователь", "work_position": ""})
        export["messages"].append({
            "id": msg.get("id"),
            "timestamp": msg.get("date"),
            "author_id": author_id,
            "author_name": author_info["full_name"],
            "author_position": author_info["work_position"],
            "text": msg.get("text"),
            "params": msg.get("params", {})
        })
    return export

# Фильтрация сообщений по дате
def filter_messages_by_date(messages, start_date, end_date):
    filtered = []
    for msg in messages:
        msg_date_str = msg.get("date")
        if not msg_date_str:
            continue
        try:
            msg_datetime = dateutil.parser.isoparse(msg_date_str)
        except Exception:
            continue
        if start_date <= msg_datetime.date() <= end_date:
            filtered.append(msg)
    return filtered

# Основной интерфейс
st.title("Экспорт истории чатов Bitrix24 с автоподбором даты и ФИО пользователей")

# Загружаем список чатов
chats = get_recent_chats()

st.subheader("Отладка: данные, полученные от Bitrix24")
st.json(chats)

if not chats:
    st.error("Не удалось получить список чатов.")
    st.stop()

chat_map = {f'{chat.get("title", "Без названия")} (ID: {chat.get("chat_id", "нет id")})': chat["chat_id"] for chat in chats if "chat_id" in chat}

if not chat_map:
    st.error("Нет доступных чатов.")
    st.stop()

selected_chat_title = st.selectbox("Выберите чат для экспорта:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]
    dialog_id = f"chat{selected_chat_id}"

    if st.button("Загрузить все сообщения из чата"):
        st.info("Загружаем сообщения...")
        all_messages = get_chat_history(dialog_id)

        if not all_messages:
            st.error("Сообщений в чате нет.")
            st.stop()

        # Автоподбор диапазона дат
        all_dates = []
        for msg in all_messages:
            msg_date_str = msg.get("date")
            if msg_date_str:
                try:
                    msg_datetime = dateutil.parser.isoparse(msg_date_str)
                    all_dates.append(msg_datetime.date())
                except Exception:
                    continue

        if not all_dates:
            st.error("Не удалось определить даты сообщений.")
            st.stop()

        min_date = min(all_dates)
        max_date = max(all_dates)

        st.success(f"Сообщения в чате с {min_date} по {max_date}")

        # Выбор диапазона пользователем
        start_date = st.date_input("Начальная дата", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.date_input("Конечная дата", value=max_date, min_value=min_date, max_value=max_date)

        if start_date > end_date:
            st.error("Начальная дата должна быть раньше конечной даты!")
            st.stop()

        # Фильтрация сообщений
        filtered_messages = filter_messages_by_date(all_messages, start_date, end_date)

        st.success(f"Сообщений после фильтрации: {len(filtered_messages)}")

        if not filtered_messages:
            st.warning("Нет сообщений в выбранном диапазоне дат.")
            st.stop()

        # Получение данных об авторах
        author_ids = {msg["author_id"] for msg in filtered_messages if "author_id" in msg}
        st.info(f"Получение данных о {len(author_ids)} авторах...")

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

        st.subheader("Первые 2 сообщения после фильтрации:")
        st.json(filtered_messages[:2])

        # Экспорт в JSON
        export_data = export_chat(selected_chat_id, selected_chat_title, filtered_messages, author_info_map)

        buffer = io.BytesIO()
        buffer.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
        buffer.seek(0)

        st.download_button(
            "Скачать историю чата в JSON (с ФИО и фильтрацией)",
            buffer,
            file_name=f"chat_{selected_chat_id}_history_with_users.json",
            mime="application/json"
        )
