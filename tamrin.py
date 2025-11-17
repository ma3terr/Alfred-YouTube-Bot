import telebot
from pytube import YouTube
import os
import tempfile
import re

# توکن جدید شما
# BOT_TOKEN = "توکن را در اینجا قرار دهید"
BOT_TOKEN = "8174456001:AAEyKevw90ynCM91tOB3IS-QTD5XnGOtzQs"
bot = telebot.TeleBot(BOT_TOKEN)

# مسیر برای فایل‌های موقت
# از tempfile برای مدیریت بهتر فایل‌های موقت استفاده می‌شود
TEMP_DIR = tempfile.gettempdir()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """پاسخ به دستور /start"""
    bot.reply_to(message, "سلام! لینک ویدیوی یوتیوب مورد نظرتو بفرست تا فایل صوتی (MP3) اونو برات بفرستم.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    """
    پردازش لینک‌های یوتیوب
    """
    link = message.text.strip()
    chat_id = message.chat.id
    
    # بررسی کنید که آیا متن یک لینک یوتیوب معتبر است
    youtube_regex = re.compile(
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&?]+)'
    )
    if not youtube_regex.match(link):
        bot.reply_to(message, "لطفاً یک لینک معتبر یوتیوب ارسال کنید.")
        return

    # ارسال پیام 'در حال شروع فرآیند...'
    processing_message = bot.reply_to(message, "در حال شروع فرآیند... ⏳")

    # متغیرها را خارج از try تعریف می‌کنیم تا در finally قابل دسترسی باشند
    output_path = None
    new_filename = None

    try:
        # 1. دانلود استریم صوتی
        yt = YouTube(link)
        
        # انتخاب بهترین استریم صوتی
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            bot.edit_message_text("خطا: استریم صوتی در این ویدیو پیدا نشد.", chat_id, processing_message.message_id)
            return

        # 2. نام فایل موقت (دانلود به صورت mp4)
        output_path = os.path.join(TEMP_DIR, f"{yt.video_id}.mp4")
        
        # 3. دانلود به mp4 موقت
        audio_stream.download(output_path=TEMP_DIR, filename=yt.video_id)

        # 4. تغییر نام به MP3 (ffmpeg این کار را انجام می‌دهد)
        base, ext = os.path.splitext(output_path)
        new_filename = base + '.mp3'
        os.rename(output_path, new_filename)

        # 5. ارسال فایل MP3
        with open(new_filename, 'rb') as audio_file:
            bot.send_audio(
                chat_id, 
                audio_file, 
                title=yt.title, 
                performer=yt.author,
                reply_to_message_id=message.message_id
            )
            
        bot.delete_message(chat_id, processing_message.message_id)
        
    except Exception as e:
        error_message = f"خطا در پردازش: {e}\nلطفاً دوباره امتحان کنید یا لینک دیگری بفرستید."
        print(f"Error: {e}")
        # ویرایش پیام در حال پردازش به پیام خطا
        bot.edit_message_text(error_message, chat_id, processing_message.message_id)

    finally:
        # 6. پاکسازی فایل‌های موقت
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        if new_filename and os.path.exists(new_filename):
            os.remove(new_filename)


# شروع به کار ربات
if __name__ == '__main__':
    try:
        print("Bot is running...")
        bot.infinity_polling()
    except Exception as e:
        print(f"Polling error: {e}")
