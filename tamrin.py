import telebot
from telebot import types
from pytube import Search
from yt_dlp import YoutubeDL
import re
import os
import shutil
import time

# ----------------- API Key -----------------
# ❗️ توکن جدید شما جایگزین شد. (8456082831:AAHIwdxsaqusimIfDBfAPqnEVgTFoZmZFcM)
BOT_TOKEN = "8456082831:AAHIwdxsaqusimIfDBfAPqnEVgTFoZmZFcM"
bot = telebot.TeleBot(BOT_TOKEN)

# ----------------- توابع کمکی -----------------

def escape_markdown_v1(text):
    """
    کاراکترهای خاص را که توسط MarkdownV1 تفسیر می‌شوند، اسکیپ می‌کند.
    """
    # کاراکترهایی که باید در MarkdownV1 اسکیپ شوند:
    escape_chars = r"_*`["
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def edit_message(chat_id, message_id, text, parse_mode='Markdown'):
    """
    پیام موجود را ویرایش می‌کند و خطاهای احتمالی را مدیریت می‌نماید.
    """
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        # اگر خطای Bad Request مربوط به فرمت Markdown بود، بدون فرمت دوباره ارسال می‌کند.
        if "Bad Request" in str(e) and ("can't parse entities" in str(e) or "Unsupported" in str(e)):
            # تلاش برای ارسال پیام بدون فرمت (بدون ویرایش)
            bot.send_message(chat_id, f"⚠️ خطای نمایش: نتوانستم متن را با فرمت Markdown نمایش دهم. \n{text}", parse_mode=None)
        else:
            # سایر خطاها را نمایش می‌دهد
            # اگر پیام قبل از ویرایش حذف شده باشد، این خطا رخ می‌دهد.
            pass


def send_audio_from_url(message, url, title=None, initial_message_id=None):
    chat_id = message.chat.id
    # پوشه موقت برای ذخیره دانلودها (از نام چت استفاده شده است)
    temp_dir = f"downloads/{chat_id}_audio_temp"
    
    # ----------------- تنظیمات yt-dlp -----------------
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        
        # ⚠️ مسیر FFmpeg حذف یا کامنت شد تا در سرورهای ابری خطا ندهد.
        # 'ffmpeg_location': 'C:/ffmpeg/bin/ffmpeg.exe', 
        
        'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
        
        # مدیریت خطاها و Timeout برای دانلودهای طولانی‌تر
        'socket_timeout': 300, # افزایش زمان Timeout به 300 ثانیه (5 دقیقه)
        'retries': 5,          # افزایش تلاش مجدد
        
        # رفع خطاهای مربوط به یوتیوب و Sign-in (Too Many Requests)
        'extractor_args': {
            'youtube': ['--format-sort', 'res,ext,vcodec:none', '--extractor-args', 'youtube:player-client=default']
        },
        'noplaylist': True,
        'quiet': True,
    }

    # 1. دریافت عنوان قبل از دانلود
    info_title = "فایل در حال دانلود"
    try:
        with YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and (info.get('title') or info.get('fulltitle')):
                info_title = info.get('title') or info.get('fulltitle')
            
    except Exception as e:
        info_title = "فایل صوتی ناشناس"


    # 2. شروع دانلود و ارسال پیام به روزرسانی
    escaped_title = escape_markdown_v1(info_title)
    if initial_message_id:
        edit_message(chat_id, initial_message_id, f"🎶 در حال دانلود آهنگ: **{escaped_title}**... (حداکثر 5 دقیقه)", parse_mode='Markdown')
    else:
        initial_message = bot.send_message(chat_id, f"🎶 در حال دانلود آهنگ: **{escaped_title}**... (حداکثر 5 دقیقه)", parse_mode='Markdown')
        initial_message_id = initial_message.message_id
        
    downloaded_files = []
    
    try:
        # حذف محتویات پوشه موقت قبل از شروع
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        
        # اجرای دانلود با yt-dlp
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
            # جستجو برای فایل mp3 دانلود شده در پوشه موقت
            for filename in os.listdir(temp_dir):
                if filename.endswith('.mp3'):
                    downloaded_files.append(filename)
            
            if downloaded_files:
                file_path = os.path.join(temp_dir, downloaded_files[0])
                
                # 3. ارسال فایل
                edit_message(chat_id, initial_message_id, f"📤 در حال ارسال آهنگ: **{escaped_title}**...", parse_mode='Markdown')

                with open(file_path, 'rb') as audio_file:
                    bot.send_audio(
                        chat_id,
                        audio_file,
                        caption=f"🎶 **{escaped_title}**",
                        parse_mode='Markdown'
                    )

                # 4. حذف فایل موقت
                os.remove(file_path)
                edit_message(chat_id, initial_message_id, f"✅ آهنگ **{escaped_title}** با موفقیت ارسال شد.", parse_mode='Markdown')
            else:
                edit_message(chat_id, initial_message_id, f"❌ خطای دانلود: فایل صوتی **{escaped_title}** پیدا نشد. (ممکن است لینک ویدیو نباشد)", parse_mode='Markdown')

    except Exception as e:
        error_message = f"❌ خطای دانلود یا ارسال آهنگ: \n`{str(e)}`"
        edit_message(chat_id, initial_message_id, error_message, parse_mode='Markdown')
    
    finally:
        # تمیزکاری پوشه موقت
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        


def search_from_text(message, query, initial_message_id=None):
    chat_id = message.chat.id
    
    if initial_message_id is None:
        initial_message = bot.send_message(chat_id, f"⏳ در حال جستجوی **{escape_markdown_v1(query)}** در یوتیوب...", parse_mode='Markdown')
        initial_message_id = initial_message.message_id

    # 1. جستجو در یوتیوب
    try:
        s = Search(query)
        if s.results:
            video = s.results[0]
            video_link = f"https://www.youtube.com/watch?v={video.video_id}"
            video_title = video.title
            
            escaped_video_title = escape_markdown_v1(video_title)
            
            # 2. نمایش نتیجه و شروع دانلود
            response = f"✨ **یافت شد:**\n"
            response += f"عنوان: **{escaped_video_title}**\n"
            
            # 3. فراخوانی تابع دانلود (پیام جستجو به پیام دانلود تغییر داده می‌شود)
            send_audio_from_url(message, video_link, video_title, initial_message_id)

        else:
            edit_message(chat_id, initial_message_id, f"⚠️ متأسفانه هیچ نتیجه‌ای برای **{escape_markdown_v1(query)}** در یوتیوب پیدا نشد.", parse_mode='Markdown')

    except Exception as e:
        error_message = f"❌ خطایی در جستجوی یوتیوب: \n`{str(e)}`"
        edit_message(chat_id, initial_message_id, error_message, parse_mode='Markdown')

# ----------------- هندلرهای ربات -----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! من ربات دانلود آهنگ از یوتیوب/اینستاگرام هستم. کافیه لینک یا نام آهنگ رو برام بفرستی تا فایل صوتی رو برات ارسال کنم.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_text = message.text
    chat_id = message.chat.id
    
    initial_msg = bot.send_message(chat_id, "⏳ در حال شروع پردازش درخواست شما...")
    initial_message_id = initial_msg.message_id
    
    if user_text.startswith('http'):
        # اگر کاربر لینک فرستاد
        edit_message(chat_id, initial_message_id, f"🔗 لینک دریافت شد. در حال پردازش لینک **{escape_markdown_v1(user_text[:20])}**...", parse_mode='Markdown')
        send_audio_from_url(message, user_text, initial_message_id=initial_message_id)
    else:
        # اگر کاربر متن (نام آهنگ) فرستاد
        search_from_text(message, user_text, initial_message_id=initial_message_id)

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    bot.reply_to(message, "لطفاً نام آهنگ یا لینک (یوتیوب/اینستاگرام) را تایپ کنید.")

# ----------------- شروع به کار ربات -----------------
print("Bot is running...")
bot.infinity_polling()