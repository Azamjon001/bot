import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
import random
import string

# Loglarni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot tokeni (o'z tokeningizni qo'ying)
BOT_TOKEN = "7910545283:AAGaCF6WKng5iiFhXgDy9EHp3il2AMW8vgo"

# Administrator ID (o'z Telegram ID'ingizni qo'ying)
ADMIN_ID = 5234758651  # O'zingizning haqiqiy ID'ingizga almashtiring

# Ma'lumotlar bazasiga ulanish
def init_db():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
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

# Takrorlanmas token yaratish
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

# Foydalanuvchini ro'yxatdan o'tkazish
def register_user(user_id, username, first_name, referred_by=None):
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Foydalanuvchi mavjudligini tekshiramiz
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

# Foydalanuvchi haqida ma'lumot olish
def get_user_info(user_id):
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Foydalanuvchi takliflari
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

# Eng ko'p taklif qilgan 10 foydalanuvchi
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

# Umumiy statistika
def get_admin_stats():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    # Umumiy foydalanuvchilar soni
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # Taklif qilgan foydalanuvchilar soni
    cursor.execute('SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL')
    users_with_referrals = cursor.fetchone()[0]
    
    # Umumiy takliflar soni
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL')
    total_referrals = cursor.fetchone()[0]
    
    conn.close()
    
    return total_users, users_with_referrals, total_referrals

# /start buyrug'i uchun ishlovchi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    
    # Taklif parametrini tekshiramiz
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            # Taklif qilgan foydalanuvchi mavjudligini tekshiramiz
            referrer = get_user_info(referred_by)
            if referrer:
                referred_by = referred_by
        except ValueError:
            referred_by = None
    
    # Foydalanuvchini ro'yxatdan o'tkazamiz
    register_user(user_id, username, first_name, referred_by)
    
    # Xush kelibsiz matni
    welcome_text = f"""
Salom, {first_name}! 👋

Taklif tizimiga xush kelibsiz! 
Do'stlaringizni taklif qiling va mukofotlar oling! 🎉

Quyidagi menyudan harakatni tanlang:
    """
    
    # Tugmali klaviaturani yaratamiz
    keyboard = [
        [InlineKeyboardButton("📊 Mening hisobim", callback_data="score")],
        [InlineKeyboardButton("👤 Meni kim taklif qildi", callback_data="referrer")],
        [InlineKeyboardButton("🔗 Taklif havolasi olish", callback_data="get_referral")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Administrator buyrug'i uchun ishlovchi
async def admin_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Foydalanuvchi administrator ekanligini tekshiramiz
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Sizda bu buyruqni bajarish huquqi yo'q.")
        return
    
    # Statistikani olamiz
    total_users, users_with_referrals, total_referrals = get_admin_stats()
    top_referrers = get_top_referrers()
    
    # Statistik xabarni shakllantiramiz
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

# Tugmalar bosilganda ishlovchi
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_info = get_user_info(user_id)
    
    await query.answer()
    
    if query.data == "score":
        # Takliflar hisobini ko'rsatamiz
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
        # Foydalanuvchini kim taklif qilganini ko'rsatamiz
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
        # Taklif havolasini ko'rsatamiz
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
        # Asosiy menyuga qaytamiz
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

# Asosiy funksiya
def main():
    # Ma'lumotlar bazasini ishga tushiramiz
    init_db()
    
    # Dasturni yaratamiz
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Ishlovchilarni qo'shamiz
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminstatistikapolzovateley", admin_statistics))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Botni ishga tushiramiz
    print("Bot ishga tushdi!")
    application.run_polling()

if __name__ == "__main__":
    main()
