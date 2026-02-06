import google.generativeai as genai
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# تنظیمات
GOOGLE_API_KEY = "AIzaSyDxbi6brNeb_ip8NM9qmn6INzUde3RStlQ"
TELEGRAM_BOT_TOKEN = "7215596772:AAElnYC-MPvSD2ETl8vQ66QL7rbkEpoumJ4"

# پیکربندی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# پیکربندی ربات تلگرام
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# تعریف handler ها
async def start(update, context):
    """پیام خوش‌آمدگویی و راهنمایی"""
    await context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! من دستیار پزشکی شما هستم. می‌توانید سوالات پزشکی خود را از من بپرسید.")

async def handle_message(update, context):
    """پردازش پیام کاربر و ارسال پاسخ Gemini"""
    user_message = update.message.text
    try:
        # اضافه کردن دستور زبان فارسی و تخصص پزشکی به درخواست
        prompt = f"""
        شما یک دستیار پزشک متخصص(نام پزشک دستیار= ربات پزشک یار) هستید. لطفا به سوال پزشکی زیر با دقت و به زبان فارسی پاسخ دهید.

        بیمار: {user_message}

        لطفا با لحنی حرفه‌ای و دلسوزانه پاسخ دهید.
        """
        response = model.generate_content(prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response.text)
    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="متاسفم، مشکلی پیش اومد. لطفا دوباره امتحان کنید.")

# اضافه کردن handler ها
start_handler = CommandHandler('start', start)
message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

application.add_handler(start_handler)
application.add_handler(message_handler)

# شروع ربات
application.run_polling()