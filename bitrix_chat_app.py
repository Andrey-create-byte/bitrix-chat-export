import streamlit as st
import json
import os
from datetime import datetime
from bitrix_api import get_chat_history, get_chats

st.title("Экспорт чатов из Bitrix24")

# Получение чатов
chats = get_chats()
chat_options = {f"{chat['title']} (ID: {chat['chat_id']})": chat['chat_id'] for chat in chats}
selected_chat_name = st.selectbox("Выберите чат:", list(chat_options.keys()))
selected_chat_id = chat_options[selected_chat_name]

show_debug = st.checkbox("Показать отладочную информацию", value=True)

if st.button("Выгрузить все сообщения"):
    st.info("Загружаем сообщения...")
    messages = []
    offset = 0
    batch_size = 50
    last_id = 0

    while True:
        batch = get_chat_history(chat_id=selected_chat_id, first_id=last_id)
        if not batch:
            break
        messages.extend(batch)
        st.write(f"Загружено {len(batch)} сообщений (offset = {offset})")
        last_id = batch[-1]['id']
        offset += batch_size

    st.success(f"Загрузка завершена. Всего сообщений: {len(messages)}")

    # Сохраняем сырые данные
    os.makedirs("bitrix_chat_exports", exist_ok=True)
    raw_file_path = f"bitrix_chat_exports/chat_{selected_chat_id}_full_history.json"
    with open(raw_file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    st.code(f"Сырые данные сохранены: {raw_file_path}")

    # Отладочная информация
    if show_debug:
        st.subheader("Отладочная информация (первые 100 сообщений):")
        st.json(messages[:100])
        
