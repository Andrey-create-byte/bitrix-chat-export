import streamlit as st
import requests
import json
import io

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
        messages = result.get("messages", [])

        if not messages:
            break

        new_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("id") not in seen_ids]
        if not new_messages:
            break

        all_messages.extend(new_messages)
        seen_ids.update(msg["id"] for msg in new_messages)
        last_id = min(msg["id"] for msg in new_messages if "id" in msg)

    return all_messages

# Экспорт чата в JSON формате
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

# Основной интерфейс приложения
st.title("Экспорт истории чатов из Bitrix24")

# Загружаем чаты
chats = get_recent_chats()

# Отладочный вывод всех чатов
st.subheader("Отладка: данные, полученные от Bitrix24")
st.json(chats)

if not chats:
    st.error("Не удалось получить список чатов. Проверьте настройки вебхука.")
    st.stop()

# Формируем карту для выбора
chat_map = {f'{chat.get("title", "Без названия")} (ID: {chat.get("chat_id", "нет id")})': chat["chat_id"] for chat in chats if "chat_id" in chat}

if not chat_map:
    st.error("Нет доступных чатов для экспорта.")
    st.stop()

# Выбор чата пользователем
selected_chat_title = st.selectbox("Выберите чат для экспорта:", list(chat_map.keys()))

if selected_chat_title:
    selected_chat_id = chat_map[selected_chat_title]

    if st.button("Выгрузить все сообщения"):
        st.info("Загружаем сообщения...")
        dialog_id = f"chat{selected_chat_id}"  # правильно формируем диалог
        all_messages = get_chat_history(dialog_id)

        st.success(f"Загрузка завершена. Всего сообщений: {len(all_messages)}")

        # Отладочная информация
        st.subheader("Первые 2 сообщения для проверки:")
        st.json(all_messages[:2])

        # Формируем JSON файл
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
