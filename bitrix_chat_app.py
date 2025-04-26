import requests
import json
import os
import shutil
import streamlit as st
from zipfile import ZipFile
from datetime import datetime

# Чтение секрета из Streamlit secrets
WEBHOOK_URL = st.secrets["WEBHOOK_URL"]

# Функция для получения сообщений из чата
def get_chat_messages(dialog_id, limit=200, offset=0):
    url = f"{WEBHOOK_URL}im.dialog.messages.get.json"
    payload = {
        "DIALOG_ID": dialog_id,
        "LIMIT": limit,
        "OFFSET": offset
    }
    response = requests.post(url, json=payload)
    return response.json()

# Функция для сохранения сообщений в JSON
def save_messages_to_json(messages, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)

# Функция для сохранения сообщений в TXT
def save_messages_to_txt(messages, filename):
    with open(filename, "w", encoding="utf-8") as f:
        for message in messages:
            author_id = message.get("author_id", "Unknown")
            date = message.get("date_create", "Unknown date")
            text = message.get("message", "")
            f.write(f"{date} - Author {author_id}: {text}\n")
            if 'files' in message:
                for file in message['files']:
                    file_name = file.get('name', 'unnamed_file')
                    file_url = file.get('url_download', '')
                    f.write(f"[Файл] {file_name}: {file_url}\n")
            f.write("-" * 50 + "\n")

# Функция для скачивания файлов с прогресс-баром
def download_files(messages, folder_name):
    os.makedirs(folder_name, exist_ok=True)
    file_count = sum(len(message.get('files', [])) for message in messages)
    if file_count == 0:
        return
    progress_bar = st.progress(0)
    downloaded = 0

    for message in messages:
        if 'files' in message:
            for file in message['files']:
                file_name = file.get('name', 'unnamed_file')
                file_url = file.get('url_download', '')
                if file_url:
                    response = requests.get(file_url)
                    if response.status_code == 200:
                        with open(os.path.join(folder_name, file_name), 'wb') as f:
                            f.write(response.content)
                downloaded += 1
                progress_bar.progress(min(downloaded / file_count, 1.0))

# Функция для архивирования папки с файлами
def zip_folder(folder_name, zip_name):
    with ZipFile(zip_name, 'w') as zipf:
        for root, dirs, files in os.walk(folder_name):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_name))

# Основной процесс
if __name__ == "__main__":
    st.title("Экспорт истории чатов Bitrix24")

    dialog_id = st.text_input("Введите DIALOG_ID чата", value="chat12345")
    filter_type = st.selectbox("Что выгружать?", ["Все сообщения", "Только сообщения с файлами"])
    start_date = st.date_input("Начальная дата фильтрации (по дате сообщения)")
    end_date = st.date_input("Конечная дата фильтрации (по дате сообщения)")

    if st.button("Выгрузить сообщения"):
        if start_date > end_date:
            st.error("Начальная дата не может быть позже конечной даты!")
        else:
            all_messages = []
            offset = 0
            batch_size = 200

            # Постраничная загрузка всех сообщений
            while True:
                data = get_chat_messages(dialog_id, limit=batch_size, offset=offset)
                messages = data.get("result", {}).get("messages", [])

                if not messages:
                    break

                all_messages.extend(messages)
                offset += batch_size

            # Фильтрация сообщений по дате и типу
            filtered_messages = []
            for msg in all_messages:
                msg_date = datetime.strptime(msg.get("date_create", "1970-01-01T00:00:00+00:00")[:10], "%Y-%m-%d").date()
                if start_date <= msg_date <= end_date:
                    if filter_type == "Только сообщения с файлами":
                        if 'files' in msg and msg['files']:
                            filtered_messages.append(msg)
                    else:
                        filtered_messages.append(msg)

            st.success(f"Выгружено сообщений после фильтрации: {len(filtered_messages)}")

            # Сохраняем в JSON и TXT
            filename_json = f"chat_{dialog_id}_messages.json"
            filename_txt = f"chat_{dialog_id}_messages.txt"
            files_folder = f"chat_{dialog_id}_files"
            zip_filename = f"{files_folder}.zip"

            save_messages_to_json(filtered_messages, filename_json)
            save_messages_to_txt(filtered_messages, filename_txt)
            download_files(filtered_messages, files_folder)
            zip_folder(files_folder, zip_filename)

            # Кнопки скачивания
            with open(filename_json, "r", encoding="utf-8") as f:
                st.download_button('Скачать JSON сообщений', f, file_name=filename_json, mime='application/json')

            with open(filename_txt, "r", encoding="utf-8") as f:
                st.download_button('Скачать TXT сообщений', f, file_name=filename_txt, mime='text/plain')

            with open(zip_filename, "rb") as f:
                st.download_button('Скачать ZIP файлов', f, file_name=zip_filename, mime='application/zip')

            # Вывод красивой таблицы сообщений
            simplified_messages = [
                {
                    "Дата": message.get("date_create", "Unknown"),
                    "Автор ID": message.get("author_id", "Unknown"),
                    "Сообщение": message.get("message", "")
                }
                for message in filtered_messages
            ]

            st.dataframe(simplified_messages)

            st.info(f"Файлы сохранены и архивированы: {zip_filename}")
