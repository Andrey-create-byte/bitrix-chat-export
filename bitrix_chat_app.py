import streamlit as st
import requests
import datetime
import time

WEBHOOK = "ВАШ_WEBHOOK_BITRIX24"

# Получение списка групповых чатов и открытых линий
def get_chats():
    res = requests.post(f'{WEBHOOK}/im.recent.get').json()
    chats = []
    for item in res.get('result', []):
        if item['type'] in ['chat', 'lines']:
            chats.append({
                'id': item['chat_id'],
                'name': item['title'],
                'type': 'open_line' if item['type'] == 'lines' else 'group_chat'
            })
    return chats

# Получение участников чата
def get_participants(chat_id):
    res = requests.post(f'{WEBHOOK}/im.chat.user.list', json={'CHAT_ID': chat_id}).json()
    participants = []
    for user_id in res.get('result', []):
        user_res = requests.post(f'{WEBHOOK}/user.get', json={'ID': user_id}).json()
        user = user_res.get('result', [{}])[0]
        participants.append(f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}")
    return participants

# Выгрузка сообщений, включая архивные
def get_chat_history(chat_id, date_from, date_to):
    messages, offset = [], 0
    while True:
        res = requests.post(f'{WEBHOOK}/im.dialog.messages.get', json={
            'DIALOG_ID': f'chat{chat_id}',
            'LIMIT': 50,
            'OFFSET': offset
        }).json()
        batch = res.get('result', {}).get('messages', [])
        if not batch:
            break
        for msg in batch:
            ts = datetime.datetime.fromisoformat(msg['date'])
            if date_from <= ts <= date_to:
                messages.append({
                    'id': msg['id'],
                    'timestamp': msg['date'],
                    'author': msg['author_id'],
                    'text': msg['text'],
                    'type': 'file' if 'files' in msg else 'text',
                    'attachments': [
                        {
                            'filename': f['name'],
                            'type': f['type'],
                            'size': f['size'],
                            'url': f['urlDownload']
                        } for f in msg.get('files', [])
                    ]
                })
        offset += 50
        time.sleep(0.1)
    return messages

# Streamlit UI
st.title("Экспорт чатов из Bitrix24")

chats = get_chats()
chat_option = st.selectbox("Выберите чат или открытую линию:", [f"{c['name']} (ID: {c['id']})" for c in chats])
chat_id = int(chat_option.split("ID: ")[1].rstrip(")"))

date_from = st.date_input("С даты", datetime.date.today() - datetime.timedelta(days=7))
date_to = st.date_input("По дату", datetime.date.today())

if st.button("Выгрузить"):
    selected_chat = next(c for c in chats if c['id'] == chat_id)
    participants = get_participants(chat_id)
    messages = get_chat_history(
        chat_id,
        datetime.datetime.combine(date_from, datetime.time.min),
        datetime.datetime.combine(date_to, datetime.time.max)
    )

    export_data = {
        'chat_id': chat_id,
        'chat_name': selected_chat['name'],
        'type': selected_chat['type'],
        'participants': participants,
        'messages': messages
    }

    st.download_button(
        "Скачать JSON",
        data=requests.utils.json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"chat_{chat_id}_{date_from}_{date_to}.json",
        mime="application/json"
    )
    
