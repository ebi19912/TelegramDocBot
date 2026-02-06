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
SELECTING_SPECIALTY, GETTING_AGE, GETTING_GENDER, GETTING_HISTORY, GETTING_MEDICATION, TYPING_REPLY = range(6)

# پیکربندی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# پیکربندی ربات تلگرام
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# تعریف handler ها
async def start(update: Update, context: CallbackContext) -> int:
    """شروع گفتگو و پرسیدن تخصص مورد نیاز"""
    reply_keyboard = [["قلب", "داخلی", "اطفال"]]
    await update.message.reply_text(
        "سلام! من ربات پزشک یار هستم. لطفا تخصص مورد نیاز خود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="تخصص؟"
        ),
    )
    return SELECTING_SPECIALTY

async def select_specialty(update: Update, context: CallbackContext) -> int:
    """ذخیره تخصص و پرسیدن سن بیمار"""
    user = update.message.from_user
    context.user_data["specialty"] = update.message.text
    await update.message.reply_text(
        "سن بیمار را وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GETTING_AGE

async def getting_age(update: Update, context: CallbackContext) -> int:
    """ذخیره سن و پرسیدن جنسیت بیمار"""
    context.user_data["age"] = update.message.text
    reply_keyboard = [["مرد", "زن"]]
    await update.message.reply_text(
        "جنسیت بیمار را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="جنسیت؟"
        ),
    )
    return GETTING_GENDER

async def getting_gender(update: Update, context: CallbackContext) -> int:
    """ذخیره جنسیت و پرسیدن سابقه بیماری"""
    context.user_data["gender"] = update.message.text
    await update.message.reply_text("سابقه بیماری (در صورت وجود) را وارد کنید:")
    return GETTING_HISTORY

async def getting_history(update: Update, context: CallbackContext) -> int:
    """ذخیره سابقه بیماری و پرسیدن داروهای مصرفی"""
    context.user_data["history"] = update.message.text
    await update.message.reply_text("داروهای مصرفی (در صورت وجود) را وارد کنید:")
    return GETTING_MEDICATION

async def getting_medication(update: Update, context: CallbackContext) -> int:
    """ذخیره داروهای مصرفی و نمایش پیام اولیه برای شروع پرسش و پاسخ"""
    context.user_data["medication"] = update.message.text
    await update.message.reply_text(
        "خیلی ممنون. حالا می‌توانید سوالات پزشکی خود را بپرسید."
    )
    return TYPING_REPLY

async def handle_message(update: Update, context: CallbackContext) -> int:
    """پردازش پیام کاربر و ارسال پاسخ Gemini"""
    user_message = update.message.text
    state = context.user_data
    try:
        # ساخت prompt با اطلاعات جمع‌آوری شده
        prompt = f"""
        شما یک دستیار پزشک متخصص به نام "ربات پزشک یار" هستید.
        تخصص شما: {state.get("specialty", "عمومی")}
        لطفا به سوال پزشکی زیر با دقت و به زبان فارسی پاسخ دهید.

        بیمار: {user_message}
        سن: {state.get("age", "نامشخص")}
        جنسیت: {state.get("gender", "نامشخص")}
        سابقه بیماری: {state.get("history", "نامشخص")}
        داروهای مصرفی: {state.get("medication", "نامشخص")}

        لطفا با لحنی حرفه‌ای و دلسوزانه پاسخ دهید.
        """
        response = model.generate_content(prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response.text)
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

#  راه‌اندازی مکالمه
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        SELECTING_SPECIALTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_specialty)],
        GETTING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_age)],
        GETTING_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_gender)],
        GETTING_HISTORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_history)],
        GETTING_MEDICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_medication)],
        TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# اضافه کردن handler ها
application.add_handler(conv_handler)

# شروع ربات
application.run_polling()