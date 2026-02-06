import google.generativeai as genai
import telegram
import asyncio
import tiktoken
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
    JobQueue,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update

# تنظیمات
GOOGLE_API_KEY = "AIzaSyDxbi6brNeb_ip8NM9qmn6INzUde3RStlQ" # کلید API خود را اینجا قرار دهید
TELEGRAM_BOT_TOKEN = "7215596772:AAElnYC-MPvSD2ETl8vQ66QL7rbkEpoumJ4" # توکن ربات تلگرام خود را اینجا قرار دهید
MAX_MESSAGE_LENGTH = 1024  # حداکثر طول پیام کاربر
TOKENS_PER_MESSAGE = 300  # تخمین تقریبی تعداد توکن ها برای هر پیام

# مراحل گفتگو
SELECTING_SPECIALTY, GETTING_AGE, GETTING_GENDER, GETTING_HISTORY, GETTING_MEDICATION, TYPING_REPLY = range(
    6
)

# پیکربندی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# پیکربندی ربات تلگرام
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
application.bot_data["chat_history"] = {}  # اضافه کردن دیکشنری برای ذخیره تاریخچه

# ایجاد صف درخواست
request_queue = asyncio.Queue()


# تعریف handler ها
async def start(update: Update, context: CallbackContext) -> int:
    """شروع گفتگو و پرسیدن تخصص مورد نیاز"""
    chat_id = update.message.chat_id
    reply_keyboard = [["قلب", "داخلی", "اطفال"]]
    await update.message.reply_text(
        "سلام! من ربات پزشک یار هستم. لطفا تخصص مورد نیاز خود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="تخصص؟"
        ),
    )
    context.user_data["history"] = []
    context.bot_data["chat_history"][chat_id] = []
    return SELECTING_SPECIALTY


async def select_specialty(update: Update, context: CallbackContext) -> int:
    """ذخیره تخصص و پرسیدن سن بیمار"""
    user = update.message.from_user
    context.user_data["specialty"] = update.message.text
    await update.message.reply_text(
        "سن بیمار را وارد کنید:", reply_markup=ReplyKeyboardRemove()
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
    chat_id = update.message.chat_id
    if not isinstance(context.bot_data["chat_history"][chat_id], list):
        context.bot_data["chat_history"][chat_id] = []
    context.bot_data["chat_history"][chat_id].append(
        f"سابقه‌ بیماری: {update.message.text}"
    )
    await update.message.reply_text("داروهای مصرفی (در صورت وجود) را وارد کنید:")
    return GETTING_MEDICATION


async def getting_medication(update: Update, context: CallbackContext) -> int:
    """ذخیره داروهای مصرفی و نمایش پیام اولیه برای شروع پرسش و پاسخ"""
    context.user_data["medication"] = update.message.text
    await update.message.reply_text(
        f"خیلی ممنون. حالا می‌توانید سوالات پزشکی خود را بپرسید. (حداکثر طول پیام: {MAX_MESSAGE_LENGTH} کاراکتر)"
    )
    return TYPING_REPLY


async def handle_message(update: Update, context: CallbackContext) -> int:
    """پردازش پیام کاربر و ارسال به صف"""
    chat_id = update.message.chat_id
    user_message = update.message.text
    if len(user_message) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(
            f"پیام شما طولانی‌تر از حد مجاز است. لطفا آن را کوتاه‌تر کنید. (حداکثر: {MAX_MESSAGE_LENGTH} کاراکتر)"
        )
        return TYPING_REPLY

    # اضافه کردن پیام کاربر به تاریخچه
    context.bot_data["chat_history"][chat_id].append(f"بیمار: {user_message}")

    await request_queue.put((update, context))
    await update.message.reply_text("درخواست شما در صف پردازش قرار گرفت...")
    return TYPING_REPLY


async def process_queue(context: CallbackContext):
    """پردازش صف و ارسال درخواست به Gemini"""
    while True:
        try:
            update, context_user = await request_queue.get()
            chat_id = update.message.chat_id
            user_message = update.message.text
            state = context_user.user_data

            history = context.bot_data["chat_history"].get(chat_id, [])
            try:
                # ساخت prompt با اطلاعات جمع‌آوری شده
                prompt = f"""
                شما یک دستیار پزشک متخصص به نام "ربات پزشک یار" هستید.
                تخصص شما: {state.get("specialty", "عمومی")}
                لطفا به سوال پزشکی زیر با دقت و به زبان فارسی پاسخ دهید.

                تاریخچه مکالمه:
                {
                    "\\n".join(history)
                }

                بیمار: {user_message}
                سن: {state.get("age", "نامشخص")}
                جنسیت: {state.get("gender", "نامشخص")}
                سابقه بیماری: {state.get("history", "نامشخص")}
                داروهای مصرفی: {state.get("medication", "نامشخص")}

                لطفا با لحنی حرفه‌ای و دلسوزانه پاسخ دهید.
                """

                # تخمین تعداد توکن ها
                encoding = tiktoken.get_encoding("cl100k_base")
                num_tokens = len(encoding.encode(prompt))

                if num_tokens > 25000:
                    await context_user.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="متاسفم، درخواست شما بیش از حد طولانی است و در حال حاضر قادر به پردازش آن نیستم.",
                    )
                else:
                    response = model.generate_content(prompt)
                    await context_user.bot.send_message(
                        chat_id=update.effective_chat.id, text=response.text
                    )

                    # اضافه کردن پاسخ ربات به تاریخچه
                    context.bot_data["chat_history"][chat_id].append(
                        f"ربات پزشک یار: {response.text}"
                    )
                    # محدود کردن طول تاریخچه (مثلا نگه داشتن 10 پیام آخر)
                    context.bot_data["chat_history"][chat_id] = context.bot_data[
                        "chat_history"
                    ][chat_id][-10:]

            except genai.ResponseBlockedError as e:
                print(f"Response Blocked Error: {e}")
                await context_user.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="متاسفم، به دلیل محدودیت‌های محتوایی، قادر به پاسخگویی به این سوال نیستم.",
                )

            except Exception as e:
                print(f"Error: {e}")
                await context_user.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="متاسفم، مشکلی پیش اومد. لطفا دوباره امتحان کنید.",
                )
            finally:
                request_queue.task_done()
        except Exception as e:
            print(f"Error in process_queue: {e}")


async def cancel(update: Update, context: CallbackContext) -> int:
    """لغو و پایان گفتگو"""
    user = update.message.from_user
    await update.message.reply_text(
        "گفتگو لغو شد. برای شروع دوباره /start را بزنید.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# راه‌اندازی مکالمه
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        SELECTING_SPECIALTY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, select_specialty)
        ],
        GETTING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, getting_age)],
        GETTING_GENDER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, getting_gender)
        ],
        GETTING_HISTORY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, getting_history)
        ],
        GETTING_MEDICATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, getting_medication)
        ],
        TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# اضافه کردن handler ها
application.add_handler(conv_handler)


async def error_handler(update: object, context: CallbackContext) -> None:
    """مدیریت خطاهای کلی"""
    print(f"Update caused error: {context.error}")
    if update:
        await update.message.reply_text(
            "یک خطای غیرمنتظره رخ داد. لطفا بعدا دوباره امتحان کنید."
        )


# اضافه کردن error handler
application.add_error_handler(error_handler)

# شروع ربات
if __name__ == "__main__":
    # اضافه کردن جاب process_queue به JobQueue
    application.job_queue.run_repeating(process_queue, interval=5)

    # اجرای ربات
    application.run_polling()