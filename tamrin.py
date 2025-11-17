import telebot
import yt_dlp
import re
import os
import glob
import time
import requests

# --- ۱. API Key ---
# توکن جدید شما جایگزین شد. (8174456001:AAEyKevw90ynCM91tOB3IS-QTD5XnGOtzQs)
BOT_TOKEN = "8174456001:AAEyKevw90ynCM91tOB3IS-QTD5XnGOtzQs" 

bot = telebot.TeleBot(BOT_TOKEN)

# --- ۲. تابع اصلاح شده فرار از کاراکترهای Markdown (حل خطای نمایش) ---
# این تابع، تمام کاراکرهای خاص Markdown V1 را برای نمایش صحیح خنثی (Escape) می‌کند.
def escape_markdown_v1(text):
    # لیست کامل کاراکترهای خاص
    # Escape characters: '_', '*', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    escape_chars = r'[_*`\[\]()~>#+\-={}.!]'
    return re.sub(escape_chars, r'\\\g<0>', text)

# --- ۳. تابع اصلاح شده ویرایش پیام (برای هندل کردن خطای Markdown) ---
# از send_message به جای edit_message_text در صورت خطا استفاده می‌شود تا از خطای 400 جلوگیری شود
def edit_message(chat_id, message_id, text, parse_mode='Markdown'):
    try:
        # سعی می‌کند پیام موجود را ویرایش کند
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        # اگر خطا ناشی از عدم وجود پیام (یا قدیمی بودن آن) نباشد و خطای Bad Request باشد
        if 'Bad Request: message is not modified' in str(e):
            return # نیازی به ارسال مجدد نیست
        elif "Bad Request" in str(e) or "can't parse" in str(e):
            # اگر خطای Markdown بود، از حالت parse_mode خارج شده و یک پیام جدید با متن ساده می‌فرستد
            bot.send_message(chat_id, f"❌ خطای نمایش! متن با مشکل مواجه شد: \n{text}", parse_mode=None)
        else:
            # سایر خطاهای ناموفق در ویرایش پیام
            bot.send_message(chat_id, "⚠️ خطا در به‌روزرسانی وضعیت. لطفا لینک را دوباره بفرستید.")

# --- ۴. تابع ارسال فایل صوتی (حل خطای FFmpeg محلی) ---
def send_audio_from_url(url, title, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    # اطمینان از وجود پوشه downloads
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # تنظیمات yt-dlp (ydl_opts)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # تنظیم نام فایل برای جلوگیری از تداخل
        'outtmpl': f'downloads/{chat_id}_audio_temp.%(ext)s', 
        'noplaylist': True,
        'quiet': True,
    }

    # مرحله ۱: استخراج اطلاعات و دانلود
    audio_file_path = None
    try:
        # پیام 'در حال دانلود'
        escaped_title = escape_markdown_v1(title)
        edit_message(chat_id, initial_message_id.message_id, f"🎧 در حال دانلود آهنگ: *{escaped_title}*...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # بررسی لینک اینستاگرام یا لینک‌های پشتیبانی نشده yt-dlp قبل از دانلود
            if "instagram.com" in url:
                 raise Exception("دانلود اینستاگرام پشتیبانی نمی‌شود. لطفا لینک یوتیوب بفرستید.")
            
            info_dict = ydl.extract_info(url, download=True)
            
            # پیدا کردن مسیر فایل دانلود شده
            downloaded_files = glob.glob(f"downloads/{chat_id}_audio_temp.*")
            if not downloaded_files:
                raise Exception("نتوانستم فایل دانلود شده را پیدا کنم.")
                
            audio_file_path = downloaded_files[0]
            
            # استخراج عنوان و نام خواننده برای کپشن و metadata
            final_title = info_dict.get('title', 'Unknown Title')
            artist = info_dict.get('artist') or info_dict.get('uploader')
            caption = final_title
            if artist:
                caption = f"{final_title} - {artist}"

    except Exception as e:
        error_message = f"❌ خطای دانلود: نتوانستم فایل را دانلود کنم. \n{str(e)[:250]}"
        # حذف پیام اولیه و ارسال پیام خطا (به دلیل احتمال وجود خطای Markdown در عنوان ویدیو)
        bot.delete_message(chat_id, initial_message_id.message_id)
        bot.send_message(chat_id, escape_markdown_v1(error_message))
        
        # پاکسازی
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return

    # مرحله ۲: ارسال فایل و حذف فایل موقت
    try:
        # پیام 'در حال ارسال'
        edit_message(chat_id, initial_message_id.message_id, f"⬆️ در حال ارسال آهنگ: *{escape_markdown_v1(final_title)}*...")

        with open(audio_file_path, 'rb') as audio_file:
            bot.send_audio(
                chat_id,
                audio_file,
                caption=escape_markdown_v1(caption),
                title=final_title,
                performer=artist
            )

        # حذف پیام‌های موقت و فایل صوتی پس از ارسال موفق
        bot.delete_message(chat_id, initial_message_id.message_id)
        
    except Exception as e:
        error_message = f"❌ خطای ارسال: نتوانستم فایل را ارسال کنم. \n{str(e)[:250]}"
        bot.send_message(chat_id, escape_markdown_v1(error_message))
    
    finally:
        # پاکسازی نهایی فایل
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# --- ۵. تابع جستجو از متن ---
def search_from_text(message, query, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    # به‌روزرسانی پیام 'در حال جستجو'
    escaped_query = escape_markdown_v1(query)
    edit_message(chat_id, initial_message_id.message_id, f"🔍 در حال جستجوی *{escaped_query}* در یوتیوب...")

    try:
        # استفاده از Search در yt-dlp
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
            # جستجوی یک نتیجه با فرمت 'ytsearch1:'
            info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
        
        if info_dict and 'entries' and info_dict['entries']:
            video_info = info_dict['entries'][0]
            video_link = video_info.get('webpage_url')
            video_title = video_info.get('title', 'عنوان نامشخص')
            
            # ساخت پاسخ با استفاده از Markdown V1 و فرار از کاراکترها
            escaped_video_title = escape_markdown_v1(video_title)
            response = f"✅ نتیجه پیدا شد: \n"
            response += f"عنوان: *{escaped_video_title}*\n"
            # استفاده از لینک به صورت ساده برای جلوگیری از خطاهای پارسینگ
            response += f"لینک: {video_link}"
            
            edit_message(chat_id, initial_message_id.message_id, response, parse_mode='Markdown')
            
            # شروع دانلود و ارسال
            send_audio_from_url(video_link, video_title, initial_message_id)

        else:
            edit_message(chat_id, initial_message_id.message_id, "❌ متأسفانه نتیجه‌ای در جستجو پیدا نشد.")
            
    except Exception as e:
        error_message = f"❌ خطای جستجو: در طول جستجو خطایی رخ داد. \n{str(e)[:250]}"
        bot.send_message(chat_id, escape_markdown_v1(error_message))

# --- ۶. هندلرها ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! لینک آهنگ یوتیوب را بفرستید یا متن جستجو را برای من ارسال کنید.")

# @bot.message_handler(content_types=['audio'])
# def handle_audio(message):
#     # NOTE: قابلیت تشخیص آهنگ از روی صدا (مانند Shazam) نیاز به API پیچیده‌تر دارد و در این کد پیاده‌سازی نشده است.
#     bot.reply_to(message, "قابلیت تشخیص آهنگ از روی صدا (مانند Shazam) هنوز در این ربات فعال نیست. لطفا لینک یا متن جستجو بفرستید.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_text = message.text
    
    # پیام اولیه 'در حال شروع فرآیند...'
    initial_msg = bot.send_message(message.chat.id, "⏳ در حال شروع فرآیند...")
    
    # اگر ورودی با 'http' شروع شود، فرض می‌کنیم لینک است
    if user_text.startswith('http'):
        edit_message(message.chat.id, initial_msg.message_id, f"🔗 لینک دریافت شد، در حال پردازش...")
        send_audio_from_url(user_text, 'Unknown Title', initial_msg)
    
    # در غیر این صورت، جستجو می‌کنیم
    else:
        search_from_text(message, user_text, initial_msg)

# --- ۷. اجرای ربات ---

# پاکسازی فایل‌های قدیمی
def cleanup_old_files():
    try:
        if os.path.exists('downloads'):
            for f in glob.glob("downloads/*"):
                os.remove(f)
            print("Cleanup: Old files removed from downloads folder.")
    except Exception as e:
        print(f"Cleanup Error: {e}")

if __name__ == '__main__':
    cleanup_old_files()
    print("Bot is running...")
    # اجرای بی‌نهایت ربات (Polling)
    bot.infinity_polling()
