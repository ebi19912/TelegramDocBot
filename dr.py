import google.generativeai as genai
import telegram
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update

# تنظیمات
GOOGLE_API_KEY = ""
TELEGRAM_BOT_TOKEN = ":-"

# مراحل گفتگو
GETTING_AGE, GETTING_GENDER, GETTING_SYMPTOMS, GETTING_MEDICAL_HISTORY, TYPING_REPLY = range(5)

# پیکربندی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# پیکربندی ربات تلگرام
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# تعریف handler ها
async def start(update: Update, context: CallbackContext) -> int:
    """شروع گفتگو و پرسیدن سن"""
    await update.message.reply_text(
        "سلام! من ربات دستیار پزشکی هستم. لطفا سن خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GETTING_AGE

async def getting_age(update: Update, context: CallbackContext) -> int:
    """ذخیره سن و پرسیدن جنسیت"""
    context.user_data["age"] = update.message.text
    reply_keyboard = [["مرد", "زن"]]
    await update.message.reply_text(
        "جنسیت خود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="جنسیت؟"
        ),
    )
    return GETTING_GENDER

async def getting_gender(update: Update, context: CallbackContext) -> int:
    """ذخیره جنسیت و پرسیدن علائم"""
    context.user_data["gender"] = update.message.text
    await update.message.reply_text("لطفا علائم خود را به طور دقیق شرح دهید:")
    return GETTING_SYMPTOMS

async def getting_symptoms(update: Update, context: CallbackContext) -> int:
    """ذخیره علائم و پرسیدن سابقه پزشکی"""
    context.user_data["symptoms"] = update.message.text
    await update.message.reply_text(
        "لطفا سابقه پزشکی خود را به طور خلاصه شرح دهید (بیماری‌های خاص، حساسیت‌ها و ...):"
    )
    return GETTING_MEDICAL_HISTORY
  
async def restart(update: Update, context: CallbackContext) -> int:
    """پاک کردن اطلاعات کاربر و شروع مجدد مکالمه از مرحله پرسیدن سن"""
    context.user_data.clear()  # پاک کردن تمام اطلاعات کاربر
    await update.message.reply_text(
        "اطلاعات شما پاک شد. برای شروع دوباره لطفا سن خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GETTING_AGE  # بازگشت به مرحله اول (پرسیدن سن)

async def getting_medical_history(update: Update, context: CallbackContext) -> int:
    """ذخیره سابقه پزشکی و نمایش پیام اولیه برای شروع پرسش و پاسخ"""
    context.user_data["medical_history"] = update.message.text
    await update.message.reply_text(
        "خیلی ممنون. حالا می‌توانید سوالات پزشکی خود را بپرسید یا شرح حال دقیق تری ارائه دهید."
    )
    return TYPING_REPLY

async def handle_message(update: Update, context: CallbackContext) -> int:
    """پردازش پیام کاربر، ارسال پاسخ Gemini و نمایش پیام راهنمای شروع مجدد"""
    user_message = update.message.text
    state = context.user_data
    try:
        # ساخت prompt با اطلاعات جمع‌آوری شده
        prompt = f"""
        شما یک دستیار پزشکی متخصص به نام "ربات دستیار پزشکی" هستید.
        لطفا به سوال پزشکی زیر با دقت و به زبان فارسی پاسخ دهید.

        کاربر: {user_message}
        سن: {state.get("age", "نامشخص")}
        جنسیت: {state.get("gender", "نامشخص")}
        علائم: {state.get("symptoms", "نامشخص")}
        سابقه پزشکی: {state.get("medical_history", "نامشخص")}

        لطفا با لحنی حرفه‌ای و دلسوزانه پاسخ دهید و در صورت نیاز اطلاعات تکمیلی از کاربر درخواست کنید. 
        توجه داشته باشید که شما جایگزین پزشک نیستید و صرفا جهت ارائه اطلاعات اولیه و راهنمایی به کاربر پاسخ می‌دهید.
        """
        response = model.generate_content(prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response.text)
        
        # نمایش پیام راهنمای شروع مجدد
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="برای شروع مجدد و ورود اطلاعات جدید، /restart را بزنید.",
        )

    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="متاسفم، مشکلی پیش اومد. لطفا دوباره امتحان کنید.",
        )
    return TYPING_REPLY

async def cancel(update: Update, context: CallbackContext) -> int:
    """لغو و پایان گفتگو"""
    user = update.message.from_user
    await update.message.reply_text(
        "گفتگو لغو شد. برای شروع دوباره /start را بزنید.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        GETTING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_age)],
        GETTING_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_gender)],
        GETTING_SYMPTOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_symptoms)],
        GETTING_MEDICAL_HISTORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_medical_history)],
        TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CommandHandler("restart", restart),  # اضافه کردن restart به fallbacks
    ],
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler("restart", restart)) # اضافه کردن handler برای دستور restart

# شروع ربات
application.run_polling()