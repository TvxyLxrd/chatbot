import sqlite3
import telebot
from telebot import types
import logging
import threading

logging.basicConfig(level=logging.INFO)

# Создание базы данных и таблицы при запуске бота
conn = sqlite3.connect('forbidden_words.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS forbidden_words (word TEXT)''')
conn.commit()
conn.close()

# API-Токен ВАШЕГО бота
BOT_TOKEN = ''

# Канал, на который должны быть подписаны пользователи
REQUIRED_CHANNEL = ''

# ID администраторов бота
ADMIN_IDS = []

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)

# Обработчик команды /start и команд администратора
@bot.message_handler(func=lambda message: message.text == '/start' or message.text.startswith('/addword') or message.text.startswith('/delword') or message.text == '/wordlist')
def handle_start_and_admin_command(message):
    if message.text == '/start':
        # Проверка подписки на канал
        is_subscribed = is_user_subscribed(message.chat.id, message.from_user.id)
        if is_subscribed or message.from_user.id in ADMIN_IDS:
            # Пользователь подписан, отправить приветственное сообщение
            bot.send_message(message.chat.id, 'Добро пожаловать! Вы можете публиковать сообщения в этом чате.')
        else:
            # Пользователь не подписан, отправить сообщение с кнопкой для подписки в чат
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton('Подписаться на канал', url=f'https://t.me/{REQUIRED_CHANNEL[1:]}')
            markup.add(btn)
            message_to_delete = bot.send_message(chat_id=message.chat.id, text='Вы должны быть подписаны на наш канал, чтобы публиковать сообщения в этом чате. Пожалуйста, подпишитесь.', reply_markup=markup)
            threading.Timer(15, lambda: bot.delete_message(chat_id=message.chat.id, message_id=message_to_delete.message_id)).start()
    elif message.from_user.id not in ADMIN_IDS:
        bot.send_message(chat_id=message.chat.id, text='У вас недостаточно прав для выполнения этой команды.')
        return
    else:
        conn = sqlite3.connect('forbidden_words.db')
        cursor = conn.cursor()

        if message.text.startswith('/addword'):
            # Добавить новое слово в таблицу
            try:
                word = message.text.split()[1]
                cursor.execute("INSERT INTO forbidden_words VALUES (?)", (word,))
                conn.commit()
                bot.send_message(chat_id=message.chat.id, text=f'Слово "{word}" добавлено в таблицу запрещенных слов.')
                logging.info(f'Word "{word}" added to forbidden_words table by user {message.from_user.id}')
            except Exception as e:
                bot.send_message(chat_id=message.chat.id, text=f'Ошибка при добавлении слова: {str(e)}')
                logging.error(f'Error adding word "{word}" to forbidden_words table by user {message.from_user.id}: {str(e)}')
        elif message.text.startswith('/delword'):
            # Удалить слово из таблицы
            try:
                word = message.text.split()[1]
                cursor.execute("DELETE FROM forbidden_words WHERE word=?", (word,))
                conn.commit()
                bot.send_message(chat_id=message.chat.id, text=f'Слово "{word}" удалено из таблицы запрещенных слов.')
                logging.info(f'Word "{word}" deleted from forbidden_words table by user {message.from_user.id}')
            except Exception as e:
                bot.send_message(chat_id=message.chat.id, text=f'Ошибка при удалении слова: {str(e)}')
                logging.error(f'Error deleting word "{word}" from forbidden_words table by user {message.from_user.id}: {str(e)}')
        elif message.text == '/wordlist':
            # Вывести список запрещенных слов
            try:
                cursor.execute('SELECT * FROM forbidden_words')
                forbidden_words = [row[0] for row in cursor.fetchall()]
                if not forbidden_words:
                    bot.send_message(chat_id=message.chat.id, text='Список запрещенных слов пуст.')
                else:
                    forbidden_words_str = '\n'.join(forbidden_words)
                    bot.send_message(chat_id=message.chat.id, text=f'Список запрещенных слов:\n{forbidden_words_str}')
                logging.info(f'Wordlist requested by user {message.from_user.id}')
            except Exception as e:
                bot.send_message(chat_id=message.chat.id, text=f'Ошибка при получении списка слов: {str(e)}')
                logging.error(f'Error getting wordlist by user {message.from_user.id}: {str(e)}')
            finally:
                conn.close()

# Обработчик входящих сообщений
@bot.message_handler(content_types=['text'])
def handle_message(message):
    print(f'Received message {message.text} from user {message.from_user.id} in chat {message.chat.id}')
    # Проверка подписки на канал
    is_subscribed = is_user_subscribed(message.chat.id, message.from_user.id)

    print(f'User {message.from_user.id} is {"subscribed" if is_subscribed else "not subscribed"}')
    if not is_subscribed and message.from_user.id not in ADMIN_IDS:
        # Пользователь не подписан, удалить сообщение
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        # Отправить сообщение с кнопкой для подписки в чат
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton('Подписаться на канал', url=f'https://t.me/{REQUIRED_CHANNEL[1:]}')
        markup.add(btn)
        message_to_delete = bot.send_message(chat_id=message.chat.id, text='Вы должны быть подписаны на наш канал, чтобы публиковать сообщения в этом чате. Пожалуйста, подпишитесь.', reply_markup=markup)
        threading.Timer(15, lambda: bot.delete_message(chat_id=message.chat.id, message_id=message_to_delete.message_id)).start()
    else:
        # Пользователь подписан, проверить сообщение на запрещенный контент
        if message.from_user.id not in ADMIN_IDS and has_forbidden_content(message.text):
            # Сообщение содержит запрещенный контент, удалить его
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

# Функция проверки подписки пользователя на канал
def is_user_subscribed(chat_id, user_id):
    try:
        chat_member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return chat_member.status in ['member', 'creator', 'administrator']
    except telebot.apihelper.ApiException:
        return False

# Функция проверки сообщения на запрещенный контент
def has_forbidden_content(message_text):
    conn = sqlite3.connect('forbidden_words.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM forbidden_words')
    forbidden_words = [row[0] for row in cursor.fetchall()]
    for word in forbidden_words:
        if word in message_text.lower():
            return True
    return False

# Запуск бота
bot.polling()
