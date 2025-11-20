import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
import random
import string

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота (замени на свой)
BOT_TOKEN = "8044248337:AAGMTwUAVhAj-dkvvStQLpT7Di1Tjtevwf0"

# ID администратора (замени на свой Telegram ID)
ADMIN_ID = 5234758651  # Замени на свой реальный ID

# Подключение к базе данных
def init_db():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            referral_token TEXT UNIQUE,
            referred_by INTEGER,
            FOREIGN KEY (referred_by) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Генерация уникального токена
def generate_referral_token():
    while True:
        token = ''.join(random.choices(string.digits, k=8))
        conn = sqlite3.connect('referral_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE referral_token = ?', (token,))
        if not cursor.fetchone():
            conn.close()
            return token
        conn.close()

# Регистрация пользователя
def register_user(user_id, username, first_name, referred_by=None):
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referral_token = generate_referral_token()
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, referral_token, referred_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, referral_token, referred_by))
        conn.commit()
    conn.close()

# Получение информации о пользователе
def get_user_info(user_id):
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Получение рефералов пользователя
def get_user_referrals(user_id):
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name 
        FROM users 
        WHERE referred_by = ?
    ''', (user_id,))
    referrals = cursor.fetchall()
    conn.close()
    return referrals

# Получение топ-10 пользователей по количеству рефералов
def get_top_referrers():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            u.user_id,
            u.username,
            u.first_name,
            COUNT(r.referred_by) as referral_count
        FROM users u
        LEFT JOIN users r ON u.user_id = r.referred_by
        GROUP BY u.user_id, u.username, u.first_name
        ORDER BY referral_count DESC
        LIMIT 10
    ''')
    top_referrers = cursor.fetchall()
    conn.close()
    return top_referrers

# Получение общей статистики
def get_admin_stats():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Общее количество пользователей
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # Количество пользователей с рефералами
    cursor.execute('SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL')
    users_with_referrals = cursor.fetchone()[0]
    
    # Общее количество рефералов
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL')
    total_referrals = cursor.fetchone()[0]
    
    conn.close()
    
    return total_users, users_with_referrals, total_referrals

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    
    # Проверяем реферальный параметр
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            # Проверяем, существует ли пользователь, который пригласил
            referrer = get_user_info(referred_by)
            if referrer:
                referred_by = referred_by
        except ValueError:
            referred_by = None
    
    # Регистрируем пользователя
    register_user(user_id, username, first_name, referred_by)
    
    # Приветственное сообщение
    welcome_text = f"""
Salom, {first_name}! 👋

Taklif tizimiga xush kelibsiz! 
Do'stlaringizni taklif qiling va mukofotlar oling! 🎉

Quyidagi menyudan harakatni tanlang:
    """
    
    # Создаем клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton("📊 Mening hisobim", callback_data="score")],
        [InlineKeyboardButton("👤 Meni kim taklif qildi", callback_data="referrer")],
        [InlineKeyboardButton("🔗 Taklif havolasi olish", callback_data="get_referral")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Обработчик административной команды
async def admin_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Sizda bu buyruqni bajarish huquqi yo'q.")
        return
    
    # Получаем статистику
    total_users, users_with_referrals, total_referrals = get_admin_stats()
    top_referrers = get_top_referrers()
    
    # Формируем сообщение со статистикой
    stats_text = f"""
📊 **ADMINISTRATOR STATISTIKASI**

👥 Umumiy foydalanuvchilar soni: {total_users}
🤝 Taklif qilgan foydalanuvchilar: {users_with_referrals}
📈 Jami takliflar: {total_referrals}

🏆 **TAKLIFLAR BO'YICHA TOP-10 FOYDALANUVCHI:**
"""
    
    if top_referrers:
        for i, (user_id, username, first_name, referral_count) in enumerate(top_referrers, 1):
            username_display = f"@{username}" if username else first_name
            stats_text += f"\n{i}. {username_display} - {referral_count} taklif"
    else:
        stats_text += "\n😔 Hozircha takliflar bo'yicha ma'lumot yo'q"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# Обработчик нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_info = get_user_info(user_id)
    
    await query.answer()
    
    if query.data == "score":
        # Показываем счет рефералов
        referrals = get_user_referrals(user_id)
        
        if referrals:
            referral_list = "👥 Sizning takliflaringiz:\n\n"
            for i, ref in enumerate(referrals, 1):
                ref_user_id, ref_username, ref_first_name = ref
                username_display = f"@{ref_username}" if ref_username else ref_first_name
                referral_list += f"{i}. {username_display}\n"
            
            referral_list += f"\n📈 Jami takliflar: {len(referrals)}"
        else:
            referral_list = "😔 Hozircha sizda takliflar yo'q.\nMukofot olish uchun do'stlaringizni taklif qiling! 🎁"
        
        await query.edit_message_text(
            text=referral_list,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
    
    elif query.data == "referrer":
        # Показываем, кто пригласил пользователя
        if user_info and user_info[4]:  # referred_by
            referrer_id = user_info[4]
            referrer_info = get_user_info(referrer_id)
            
            if referrer_info:
                ref_user_id, ref_username, ref_first_name, _, _ = referrer_info
                username_display = f"@{ref_username}" if ref_username else ref_first_name
                message = f"🤝 Sizni taklif qilgan: {username_display}"
            else:
                message = "❌ Sizni taklif qilgan foydalanuvchi haqida ma'lumot topilmadi."
        else:
            message = "❌ Siz taklif havolasi orqali qo'shilmagansiz."
        
        await query.edit_message_text(
            text=message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
    
    elif query.data == "get_referral":
        # Показываем реферальную ссылку
        if user_info:
            referral_token = user_info[3]
            referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
            
            message = f"""
🔗 Sizning taklif havolangiz:

`{referral_link}`

📢 Ushbu havolani do'stlaringizga yuboring! 
Har bir taklif qilingan do'st uchun mukofot olasiz! 🎁

👥 Sizning takliflaringiz soni: {len(get_user_referrals(user_id))}
            """
            
            await query.edit_message_text(
                text=message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
            )
    
    elif query.data == "back_to_main":
        # Возвращаемся к главному меню
        user = query.from_user
        welcome_text = f"""
Salom, {user.first_name}! 👋

Taklif tizimiga xush kelibsiz! 
Do'stlaringizni taklif qiling va mukofotlar oling! 🎉

Quyidagi menyudan harakatni tanlang:
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Mening hisobim", callback_data="score")],
            [InlineKeyboardButton("👤 Meni kim taklif qildi", callback_data="referrer")],
            [InlineKeyboardButton("🔗 Taklif havolasi olish", callback_data="get_referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=welcome_text, reply_markup=reply_markup)

# Основная функция
def main():
    # Инициализируем базу данных
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminstatistikapolzovateley", admin_statistics))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    print("Bot ishga tushdi!")
    application.run_polling()

if __name__ == "__main__":
    main()
