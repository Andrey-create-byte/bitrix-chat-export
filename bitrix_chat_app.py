import streamlit as st
import requests
import json
import io
from datetime import datetime, date
import dateutil.parser

# Читаем WEBHOOK из секрета
WEBHOOK = st.secrets["WEBHOOK"]

# Инициализация состояния
if "all_messages" not in st.session_state:
    st.session_state.all_messages = []
if "last_id" not in st.session_state:
    st.session_state.last_id = 0
if "dialog_id" not in st.session_state:
    st.session_state.dialog_id = ""
if "loading_complete" not in st.session_state:
    st.session_state.loading_complete = False

# Получение списка чатов
def get_recent_chats():
    url = f"{WEBHOOK}/im.recent.get"
    response = requests.get(url)
    if response.status_code != 200:
        st.error(f"Ошибка ответа сервера: {response.text}")
        return []
    try:
        result = response.json().get("result", [])
        return result
    except json.JSONDecodeError:
        st.error("Ошибка разбора JSON ответа.")
        return []

# Загрузка порции сообщений
def load_messages(dialog_id, last_id=None, limit=50):
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
        return [], None

    result = response.json().get("result", {})
    messages = result.get("messages", [])

    if not messages:
        return [], None

    new_last_id = min(msg["id"] for msg in messages if "id" in msg)
    return messages, new_last_id

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
st.title("Экспорт истории чатов Bitrix24 (автодогрузка и счётчик)")

# Загружаем чаты
chats = get_recent_chats()

if not chats:
    st.error("Не удалось получить список чатов.")
    st.stop()

chat_map = {f'{chat.get("title", "Без названия")} (ID: {chat.get("chat_id", "нет id")})': chat["chat_id"] for chat in chats if "chat_id" in chat}

selected_chat_title = st.selectbox("Выберите чат:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]

    if st.button("Начать загрузку сообщений"):
        st.session_state.dialog_id = f"chat{selected_chat_id}"
        st.session_state.all_messages = []
        st.session_state.last_id = 0
        st.session_state.loading_complete = False
        st.success("Готово! Нажмите 'Автодогрузить сообщения'.")

    if st.session_state.dialog_id:
        if st.button("Автодогрузить сообщения"):
            max_total = 2000  # максимальное количество сообщений на одну сессию
            batch_size = 50
            total_loaded = 0

            while total_loaded < max_total:
                messages, new_last_id = load_messages(st.session_state.dialog_id, st.session_state.last_id, limit=batch_size)
                if not messages:
                    st.session_state.loading_complete = True
                    break
                st.session_state.all_messages.extend(messages)
                st.session_state.last_id = new_last_id
                total_loaded += len(messages)

            if st.session_state.loading_complete:
                st.success(f"Все сообщения загружены. Всего загружено: {len(st.session_state.all_messages)} сообщений.")
            else:
                st.warning(f"Достигнут лимит {max_total} сообщений. Загружено: {len(st.session_state.all_messages)}.")

        if st.session_state.all_messages:
            st.info(f"Всего загружено сообщений: {len(st.session_state.all_messages)}")

            # Автоподбор диапазона дат
            all_dates = []
            for msg in st.session_state.all_messages:
                msg_date_str = msg.get("date")
                if msg_date_str:
                    try:
                        msg_datetime = dateutil.parser.isoparse(msg_date_str)
                        all_dates.append(msg_datetime.date())
                    except Exception:
                        continue

            if all_dates:
                min_date = min(all_dates)
                max_date = max(all_dates)

                st.success(f"Сообщения с {min_date} по {max_date}")

                start_date = st.date_input("Начальная дата", value=min_date, min_value=min_date, max_value=max_date)
                end_date = st.date_input("Конечная дата", value=max_date, min_value=min_date, max_value=max_date)

                if start_date > end_date:
                    st.error("Начальная дата должна быть раньше конечной даты!")
                    st.stop()

                filtered_messages = filter_messages_by_date(st.session_state.all_messages, start_date, end_date)

                st.success(f"Сообщений после фильтрации: {len(filtered_messages)}")

                if filtered_messages:
                    # Получение данных об авторах
                    author_ids = {msg["author_id"] for msg in filtered_messages if "author_id" in msg}

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

                    # Экспортируем
                    export_data = export_chat(selected_chat_id, selected_chat_title, filtered_messages, author_info_map)

                    buffer = io.BytesIO()
                    buffer.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
                    buffer.seek(0)

                    st.download_button(
                        "Скачать историю чата в JSON",
                        buffer,
                        file_name=f"chat_{selected_chat_id}_history_with_users.json",
                        mime="application/json"
                    )
