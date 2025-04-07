import streamlit as st
import json
import os
from datetime import datetime
from utils import get_chat_history, get_chat_list, save_raw_json

st.title("Экспорт чатов из Bitrix24")

# Выбор чата
chat_list = get_chat_list()
chat_options = {f"{chat['title']} (ID: {chat['chat_id']})": chat["chat_id"] for chat in chat_list}
selected_chat_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat_id = chat_options[selected_chat_name]

# Фильтр по дате
st.markdown("**Фильтрация по дате:**")
date_from = st.date_input("С какой даты", value=datetime.today())
date_to = st.date_input("По какую дату", value=datetime.today())

show_debug = st.checkbox("Показать отладочную информацию", value=True)

if st.button("Выгрузить сообщения"):
    st.info("Загружаем сообщения...")
    all_messages = []
    offset = 0
    limit = 51

    while True:
        messages = get_chat_history(selected_chat_id, offset=offset, limit=limit)
        if not messages:
            break
        all_messages.extend(messages)
        st.write(f"Загружено {len(messages)} сообщений (offset = {offset})")
        if len(messages) < limit:
            break
        offset += limit

    # Фильтрация по дате
    filtered = []
    for msg in all_messages:
        ts = datetime.strptime(msg["date"], "%Y-%m-%dT%H:%M:%S%z")
        if not (date_from <= ts.date() <= date_to):
            continue
        filtered.append(msg)

    st.success(f"Загрузка завершена. Всего сообщений: {len(filtered)}")

    raw_path = save_raw_json(filtered, selected_chat_id)
    st.info(f"Сырые данные сохранены: {raw_path}")

    if show_debug:
        st.subheader("Отладочная информация (первые 100 сообщений):")
        st.json(filtered[:100])
