import telebot
from pytube import Search
import yt_dlp as ydlp
import os
import re

# 1. توکن API
# توکن خود را در خط زیر وارد کنید
BOT_TOKEN = "8456082831:AAHIwdxsaqusimIfDBfAPqnEVgTFoZmZFcM" 
bot = telebot.TeleBot(BOT_TOKEN)

# تابع برای فرار از کاراکترهای مارک‌داون (Markdown)
def escape_markdown_v1(text):
    # کاراکترهای قابل فرار در MarkdownV1
    escape_chars = r"[_*`\[\]()~>#+=|{}.!]"
    # جایگزینی با کاراکتر فرار (\) قبل از کاراکترهای خاص
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)


# تابع برای ویرایش پیام (برای به‌روزرسانی وضعیت دانلود)
def edit_message(chat_id, message_id, text, parse_mode=None):
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        # اگر خطای Bad Request به دلیل مشکل در Markdown باشد
        if "Bad Request" in str(e):
            # اگر خطای Markdown رخ داد، فقط متن ساده را ارسال کنید
            bot.send_message(chat_id, "⚠️ خطای نمایش: نتوانستم متن را با فرمت نمایش دهم. لطفا کد را بررسی کنید.", disable_notification=True)
        else:
            # سایر خطاها
            pass

# تابع برای ارسال صوت پس از دانلود
def send_audio_from_url(url, title=None, initial_message_id=None):
    chat_id = initial_message_id.chat.id
    
    # 1. ساخت آپشن‌های ytdlp
    # توجه: گزینه 'ffmpeg_location' حذف شد تا از FFmpeg سرور استفاده شود.
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        
        # 'ffmpeg_location': r'C:\ProgramFiles\ffmpeg\ffmpeg.exe', # این خط حذف شد
        
        'nocheckcertificate': True,
        'no_warnings': True,
        'retries': 3,
        'force_generic_extractor': True,
        'skip_download': False,
        'outtmpl': f'downloads/{chat_id}_audio_temp.%(ext)s', # مسیر ذخیره موقت
        'noplaylist': True,
        'quiet': True,
    }

    title = ""
    try:
        # 2. استخراج اطلاعات اولیه و عنوان آهنگ
        with ydlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # سعی در یافتن بهترین عنوان ممکن
            if info.get('title'):
                title = info.get('title')
            elif info.get('uploader') and 'youtube' not in info.get('uploader').lower():
                 title = f"{info.get('uploader')} - {info.get('title')}"
            else:
                 title = info.get('title') or "فایل دانلود شده"
            
    except Exception as e:
        # اگر خطای استخراج اطلاعات رخ داد (مثلا: ویدیو خصوصی است یا پیدا نشد)
        edit_message(chat_id, initial_message_id, f"❌ خطای دانلود: نتوانستم اطلاعات ویدیو را استخراج کنم. ({str(e)})")
        return

    # 3. دانلود فایل
    escaped_title = escape_markdown_v1(title)
    
    # پیام در حال دانلود
    edit_message(chat_id, initial_message_id, f"🎶 در حال دانلود آهنگ **{escaped_title}** ...")

    file_path = f'downloads/{chat_id}_audio_temp.mp3'

    try:
        with ydlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # 4. جستجوی فایل دانلود شده
        # ytdlp فایل را ذخیره کرده، باید نام فایل ذخیره شده را پیدا کنیم
        downloaded_files = [f for f in os.listdir('./downloads/') if f.startswith(f'{chat_id}_audio_temp') and f.endswith('.mp3')]
        
        if downloaded_files:
            file_path = os.path.join('./downloads/', downloaded_files[0])
            
            # 5. ارسال آهنگ
            edit_message(chat_id, initial_message_id, f"📤 در حال ارسال آهنگ **{escaped_title}**...")
            
            with open(file_path, 'rb') as audio_file:
                bot.send_audio(chat_id, audio_file, caption=title)
            
            # 6. حذف فایل
            os.remove(file_path)
            edit_message(chat_id, initial_message_id, f"✅ آهنگ **{escaped_title}** با موفقیت ارسال شد.")
            
        else:
            # اگر فایل پیدا نشد
            edit_message(chat_id, initial_message_id, f"❌ خطای دانلود: فایل صوتی پس از دانلود پیدا نشد.")


    except Exception as e:
        # در صورت بروز هر گونه خطای دانلود یا ارسال
        error_message = f"❌ خطای دانلود یا ارسال آهنگ: {str(e)}"
        edit_message(chat_id, initial_message_id, error_message)
        
    finally:
         # تمیزکاری (حذف فایل‌های موقت اگر مانده باشند)
        if os.path.exists(file_path):
            os.remove(file_path)


# تابع جستجو و ارسال لینک (برای متن‌های عادی)
def search_from_text(query, initial_message_id=None):
    chat_id = initial_message_id.chat.id
    
    # پیام در حال جستجو
    edit_message(chat_id, initial_message_id, f"🔎 در حال جستجوی **{query}**...")

    try:
        s = Search(query)
        s.run_search()
        
        if s.results:
            video_url = s.results[0].watch_url
            video_title = s.results[0].title
            
            # 1. پیدا کردن لینک یوتیوب
            escaped_title = escape_markdown_v1(video_title)
            
            response = f"🎶 **{escaped_title}**\n\n"
            response += f"[مشاهده در یوتیوب]({video_url})"
            
            edit_message(chat_id, initial_message_id, response, parse_mode='Markdown')
            
            # 2. فراخوانی دانلود آهنگ
            send_audio_from_url(video_url, video_title, initial_message_id)

        else:
            # اگر نتیجه‌ای یافت نشد
            edit_message(chat_id, initial_message_id, f"❌ متاسفانه منبعی نتیجه‌ای در جستجوی شما پیدا نشد. دوباره امتحان کنید.")

    except Exception as e:
        error_message = f"❌ خطای جستجوی یوتیوب: {str(e)}"
        edit_message(chat_id, initial_message_id, error_message)


# --- بخش مدیریت پیام‌ها ---

# دستور /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎶 سلام! نام آهنگ یا لینک (یوتیوب/اینستاگرام/ساندکلاد) را برایم بفرست تا دانلود کرده و برایتان ارسال کنم.")


# مدیریت پیام‌های متنی
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_text = message.text
    chat_id = message.chat.id
    
    # 1. ساخت پوشه دانلودها اگر موجود نیست
    if not os.path.exists('./downloads'):
        os.makedirs('./downloads')
    
    # 2. ارسال پیام اولیه (در حال شروع)
    initial_msg = bot.send_message(chat_id, "⏳ در حال شروع فرآیند...")
    
    # 3. اگر لینک باشد
    if user_text.startswith(('http://', 'https://')):
        # بررسی می‌کنیم که آیا اینستاگرام است یا خیر
        if 'instagram.com' in user_text.lower():
            edit_message(chat_id, initial_msg, "📸 لینک اینستاگرام دریافت شد. در حال تلاش برای دانلود...")
        else:
            edit_message(chat_id, initial_msg, "🔗 لینک دریافت شد. در حال دانلود آهنگ...")
            
        send_audio_from_url(user_text, initial_msg)
        
    # 4. اگر متن باشد (جستجو)
    else:
        search_from_text(user_text, initial_msg)

# مدیریت پیام‌های صوتی (Voice)
@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    bot.reply_to(message, "🎧 لطفا نام آهنگ را تایپ کنید یا لینک آن را ارسال نمایید.")


# شروع به کار ربات
if __name__ == '__main__':
    # این خط را برای اطمینان از حذف فایل‌های موقت اجرا می‌کنیم
    if not os.path.exists('./downloads'):
        os.makedirs('./downloads')

    print("Bot is running...")
    bot.infinity_polling()

