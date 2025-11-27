import telebot
from telebot import types
import json
import os
from datetime import datetime, timedelta

# ==============================================
# КОНФИГУРАЦИЯ
# ==============================================
BOT_TOKEN = "7691718672:AAHFiQJKfu7I3og-7ECOv8mhq5rK5ea9tvY"  # Заменить на реальный токен
MODERATOR_TELEGRAM_ID = 1978236948  # Заменить на реальный ID модератора (цифровой)
DB_FILE = "support_queue.json"
BAN_FILE = "banned_users.json"  # Файл для хранения информации о банах
WEB_APP_URL = "https://ваш-сайт.com"  # Заменить на реальный URL

# ==============================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ==============================================
bot = telebot.TeleBot(BOT_TOKEN)

# ==============================================
# МОДЕЛЬ ДАННЫХ И РАБОТА С ХРАНИЛИЩЕМ
# ==============================================
class TicketSystem:
    @staticmethod
    def init_db():
        """Инициализирует файлы БД при первом запуске"""
        # Инициализация системы тикетов
        if not os.path.exists(DB_FILE):
            with open(DB_FILE, 'w') as f:
                json.dump({
                    "active_tickets": {},
                    "archive": {},
                    "stats": {"total_created": 0, "total_closed": 0}
                }, f)
        
        # Инициализация системы банов
        if not os.path.exists(BAN_FILE):
            with open(BAN_FILE, 'w') as f:
                json.dump({}, f)

    @staticmethod
    def save_db(data):
        """Сохраняет данные в файл тикетов"""
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_db():
        """Загружает данные из файла тикетов"""
        with open(DB_FILE) as f:
            return json.load(f)

    @staticmethod
    def save_ban_db(data):
        """Сохраняет данные в файл банов"""
        with open(BAN_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_ban_db():
        """Загружает данные из файла банов"""
        with open(BAN_FILE) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    @staticmethod
    def generate_ticket_id():
        """Генерирует новый ID заявки"""
        db = TicketSystem.load_db()
        return db["stats"]["total_created"] + 1

    @staticmethod
    def create_ticket(user_id, message):
        """Создает новую заявку"""
        # Проверяем, не забанен ли пользователь
        ban_data = TicketSystem.load_ban_db()
        if str(user_id) in ban_data:
            ban_info = ban_data[str(user_id)]
            if ban_info['permanent'] or datetime.strptime(ban_info['until'], '%Y-%m-%d %H:%M:%S') > datetime.now():
                return None, None
        
        db = TicketSystem.load_db()
        ticket_id = TicketSystem.generate_ticket_id()
        
        ticket_data = {
            "user_id": user_id,
            "status": "pending",
            "created_at": str(datetime.now()),
            "message": message.text if message.content_type == 'text' else message.caption or "без описания",
            "content_type": message.content_type
        }
        
        db['active_tickets'][str(ticket_id)] = ticket_data
        db["stats"]["total_created"] += 1
        TicketSystem.save_db(db)
        
        return ticket_id, ticket_data

    @staticmethod
    def close_ticket(ticket_id, response_text):
        """Архивирует выполненную заявку"""
        db = TicketSystem.load_db()
        
        if str(ticket_id) not in db['active_tickets']:
            return False
            
        ticket = db['active_tickets'][str(ticket_id)]
        ticket.update({
            "closed_at": str(datetime.now()),
            "moderator_response": response_text,
            "status": "completed"
        })
        
        db['archive'][str(ticket_id)] = ticket
        del db['active_tickets'][str(ticket_id)]
        db["stats"]["total_closed"] += 1
        
        TicketSystem.save_db(db)
        return True

    @staticmethod
    def ban_user(user_id, days=0, permanent=False):
        """Банит пользователя"""
        ban_data = TicketSystem.load_ban_db()
        
        if permanent:
            ban_until = "permanent"
        else:
            ban_until = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        ban_data[str(user_id)] = {
            "banned_at": str(datetime.now()),
            "until": ban_until,
            "permanent": permanent
        }
        
        TicketSystem.save_ban_db(ban_data)
        return True

    @staticmethod
    def unban_user(user_id):
        """Разбанивает пользователя"""
        ban_data = TicketSystem.load_ban_db()
        
        if str(user_id) in ban_data:
            del ban_data[str(user_id)]
            TicketSystem.save_ban_db(ban_data)
            return True
        return False

    @staticmethod
    def is_user_banned(user_id):
        """Проверяет, забанен ли пользователь"""
        ban_data = TicketSystem.load_ban_db()
        
        if str(user_id) not in ban_data:
            return False
            
        ban_info = ban_data[str(user_id)]
        
        if ban_info['permanent']:
            return True
            
        ban_until = datetime.strptime(ban_info['until'], '%Y-%m-%d %H:%M:%S')
        return ban_until > datetime.now()

# ==============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================
def is_moderator(user):
    """Проверяет, является ли пользователь модератором по Telegram ID"""
    return user.id == MODERATOR_TELEGRAM_ID

def send_to_moderator(ticket_id, ticket_data, message):
    """Отправляет заявку модератору"""
    text = (
        f"🆕 Заявка #{ticket_id}\n"
        f"👤 User ID: {ticket_data['user_id']}\n"
        f"📝 Описание: {ticket_data['message']}"
    )
    
    if message.content_type == 'text':
        return bot.send_message(MODERATOR_TELEGRAM_ID, text)
    elif message.content_type == 'photo':
        return bot.send_photo(
            MODERATOR_TELEGRAM_ID,
            message.photo[-1].file_id,
            caption=text
        )
    elif message.content_type == 'document':
        return bot.send_document(
            MODERATOR_TELEGRAM_ID,
            message.document.file_id,
            caption=text
        )

def check_ban(user_id):
    """Проверяет бан пользователя и возвращает сообщение, если забанен"""
    if TicketSystem.is_user_banned(user_id):
        ban_data = TicketSystem.load_ban_db()[str(user_id)]
        
        if ban_data['permanent']:
            return "⛔ Вам закрыт доступ навсегда. Причина: нарушение правил сервиса."
        else:
            ban_until = datetime.strptime(ban_data['until'], '%Y-%m-%d %H:%M:%S')
            remaining = (ban_until - datetime.now()).days + 1
            return f"⛔ Вам ограничен доступ на {remaining} дней. Причина: нарушение правил сервиса."
    return None

# ==============================================
# ОБРАБОТЧИКИ КОМАНД
# ==============================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    # Проверяем бан
    ban_message = check_ban(message.from_user.id)
    if ban_message:
        bot.reply_to(message, ban_message)
        return
    
    bot.reply_to(message,
        "👋 Добро пожаловать!\n"
        "Напишите 'помощь' для связи с поддержкой\n"
        "Или 'подключиться' для доступа к сервису")

@bot.message_handler(commands=['tickets'])
def handle_tickets(message):
    """Показывает активные заявки (только для модератора)"""
    if not is_moderator(message.from_user):
        bot.reply_to(message, "⛔ Доступ запрещен")
        return

    db = TicketSystem.load_db()
    active_tickets = db.get('active_tickets', {})
    
    if not active_tickets:
        bot.reply_to(message, "✅ Нет активных заявок")
        return

    # Формируем отчет
    report = ["📋 Активные заявки:\n"]
    for ticket_id, ticket in active_tickets.items():
        report.append(
            f"#{ticket_id} | 👤 {ticket['user_id']} | "
            f"📅 {ticket['created_at'][:16]} | "
            f"📝 {ticket['message'][:30]}..."
        )
    
    # Отправляем частями (ограничение Telegram)
    for i in range(0, len(report), 10):
        batch = report[i:i+10]
        bot.send_message(message.chat.id, "\n".join(batch))
    
    # Статистика
    stats = db.get('stats', {})
    bot.send_message(
        message.chat.id,
        f"📊 Статистика:\n"
        f"• Активных: {len(active_tickets)}\n"
        f"• Всего создано: {stats.get('total_created', 0)}\n"
        f"• Закрыто: {stats.get('total_closed', 0)}"
    )

@bot.message_handler(commands=['ban'])
def handle_ban(message):
    """Команда бана пользователя (только для модератора)"""
    if not is_moderator(message.from_user):
        bot.reply_to(message, "⛔ Доступ запрещен")
        return
    
    try:
        # Парсим аргументы команды
        args = message.text.split()[1:]
        if len(args) < 1:
            raise ValueError("Недостаточно аргументов")
            
        user_id = int(args[0])
        
        # Проверяем, не пытаемся ли забанить себя
        if user_id == MODERATOR_TELEGRAM_ID:
            bot.reply_to(message, "🤨 Нельзя забанить самого себя!")
            return
            
        # Парсим дни или permanent
        permanent = False
        days = 0
        
        if len(args) > 1:
            if args[1].lower() == 'permanent':
                permanent = True
            else:
                days = int(args[1])
        
        # Выполняем бан
        TicketSystem.ban_user(user_id, days=days, permanent=permanent)
        
        # Формируем сообщение
        if permanent:
            ban_msg = "навсегда"
        else:
            ban_msg = f"на {days} дней"
            
        bot.reply_to(message, f"✅ Пользователь {user_id} забанен {ban_msg}.")
        
        # Отправляем сообщение забаненному пользователю (если он писал боту)
        try:
            if permanent:
                msg = "⛔ Вам закрыт доступ навсегда. Причина: нарушение правил сервиса."
            else:
                msg = f"⛔ Вам ограничен доступ на {days} дней. Причина: нарушение правил сервиса."
            bot.send_message(user_id, msg)
        except Exception as e:
            print(f"Не удалось уведомить пользователя: {e}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}\nИспользование: /ban user_id [days|permanent]")

@bot.message_handler(commands=['unban'])
def handle_unban(message):
    """Команда разбана пользователя (только для модератора)"""
    if not is_moderator(message.from_user):
        bot.reply_to(message, "⛔ Доступ запрещен")
        return
    
    try:
        # Парсим аргументы команды
        args = message.text.split()[1:]
        if len(args) < 1:
            raise ValueError("Недостаточно аргументов")
            
        user_id = int(args[0])
        
        # Выполняем разбан
        if TicketSystem.unban_user(user_id):
            bot.reply_to(message, f"✅ Пользователь {user_id} разбанен.")
            
            # Отправляем сообщение разбаненному пользователю (если он писал боту)
            try:
                bot.send_message(user_id, "✅ Ваш доступ восстановлен. Приносим извинения за неудобства.")
            except Exception as e:
                print(f"Не удалось уведомить пользователя: {e}")
        else:
            bot.reply_to(message, f"ℹ️ Пользователь {user_id} не был забанен.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}\nИспользование: /unban user_id")

@bot.message_handler(commands=['banned'])
def handle_banned_list(message):
    """Показывает список забаненных пользователей (только для модератора)"""
    if not is_moderator(message.from_user):
        bot.reply_to(message, "⛔ Доступ запрещен")
        return
    
    ban_data = TicketSystem.load_ban_db()
    
    if not ban_data:
        bot.reply_to(message, "✅ Нет забаненных пользователей")
        return
    
    report = ["📋 Забаненные пользователи:\n"]
    now = datetime.now()
    
    for user_id, ban_info in ban_data.items():
        if ban_info['permanent']:
            status = "🔴 PERMANENT"
        else:
            ban_until = datetime.strptime(ban_info['until'], '%Y-%m-%d %H:%M:%S')
            if ban_until > now:
                remaining = (ban_until - now).days + 1
                status = f"🟡 {remaining} дней осталось"
            else:
                status = "🟢 Истек (нужно разбанить)"
        
        report.append(f"👤 {user_id} | {status} | с {ban_info['banned_at'][:16]}")
    
    # Отправляем частями (ограничение Telegram)
    for i in range(0, len(report), 10):
        batch = report[i:i+10]
        bot.send_message(message.chat.id, "\n".join(batch))

# ==============================================
# ОБРАБОТЧИКИ СООБЩЕНИЙ
# ==============================================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == 'помощь')
def handle_help_request(message):
    """Начинает процесс создания заявки"""
    # Проверяем бан
    ban_message = check_ban(message.from_user.id)
    if ban_message:
        bot.reply_to(message, ban_message)
        return
    
    bot.reply_to(message, 
        "✍️ Опишите проблему одним сообщением:\n"
        "(можно прикрепить фото/документ)")
    bot.register_next_step_handler(message, process_ticket_creation)

def process_ticket_creation(message):
    """Обрабатывает создание заявки"""
    # Проверяем бан
    ban_message = check_ban(message.from_user.id)
    if ban_message:
        bot.reply_to(message, ban_message)
        return
    
    try:
        # Создаем заявку в БД
        ticket_id, ticket_data = TicketSystem.create_ticket(
            message.from_user.id,
            message
        )
        
        if ticket_id is None:
            bot.reply_to(message, "⛔ Ваш доступ ограничен. Вы не можете создавать заявки.")
            return
        
        # Отправляем модератору
        send_to_moderator(ticket_id, ticket_data, message)
        
        # Подтверждение пользователю
        bot.reply_to(message, 
            "✅ Ваша заявка принята!\n"
            f"Номер: #{ticket_id}\n"
            "Ожидайте ответа в этом чате.")
            
    except Exception as e:
        print(f"Ошибка создания заявки: {e}")
        bot.reply_to(message, "❌ Ошибка при создании заявки")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == 'подключиться')
def handle_connect(message):
    """Обработчик команды подключения"""
    # Проверяем бан
    ban_message = check_ban(message.from_user.id)
    if ban_message:
        bot.reply_to(message, ban_message)
        return
    
    markup = types.InlineKeyboardMarkup()
    web_app = types.WebAppInfo(url=WEB_APP_URL)
    markup.add(types.InlineKeyboardButton("Открыть приложение", web_app=web_app))
    
    bot.send_message(
        message.chat.id,
        "🌐 Для подключения нажмите кнопку ниже:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.reply_to_message and is_moderator(m.from_user))
def handle_moderator_reply(message):
    """Обрабатывает ответы модератора"""
    try:
        # Получаем информацию о заявке
        replied_msg = message.reply_to_message
        if not (replied_msg.text or replied_msg.caption):
            return
            
        # Ищем номер заявки
        source_text = replied_msg.text or replied_msg.caption
        if 'Заявка #' not in source_text:
            return
            
        ticket_id = int(source_text.split('#')[1].split()[0])
        
        # Закрываем заявку и отправляем ответ
        if TicketSystem.close_ticket(ticket_id, message.text):
            ticket = TicketSystem.load_db()['archive'][str(ticket_id)]
            bot.send_message(
                ticket['user_id'],
                f"📩 Ответ по заявке #{ticket_id}:\n{message.text}"
            )
    except Exception as e:
        print(f"Ошибка обработки ответа: {e}")

# ==============================================
# ЗАПУСК СИСТЕМЫ
# ==============================================
if __name__ == "__main__":
    # Инициализация
    TicketSystem.init_db()
    print("🔧 Бот инициализирован")
    print(f"👮 Модератор ID: {MODERATOR_TELEGRAM_ID}")
    print("🔄 Ожидание входящих сообщений...")
    
    # Запуск
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"🚨 Критическая ошибка: {e}")
    finally:
        print("🔴 Бот остановлен")