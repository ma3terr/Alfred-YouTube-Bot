import telebot
import yt_dlp
import re
import os
import glob
import time
import requests

# --- ۱. API Key ---
# توکن جدید شما جایگزین شد.
BOT_TOKEN = "8174456001:AAEyKevw90ynCM91tOB3IS-QTD5XnGOtzQs" 

bot = telebot.TeleBot(BOT_TOKEN)

# --- ۲. توابع کمکی ---

# این تابع، تمام کاراکرهای خاص Markdown V1 را برای نمایش صحیح خنثی (Escape) می‌کند.
def escape_markdown_v1(text):
    # لیست کاراکترهای خاص تلگرام برای Markdown V1
    escape_chars = r'[_*`\[\]()~>#+\-={}.!]'
    return re.sub(escape_chars, r'\\\g<0>', text)

# تابع ویرایش پیام با مدیریت خطا
def edit_message(chat_id, message_id, text, parse_mode='Markdown'):
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        # اگر خطا ناشی از عدم تغییر پیام باشد
        if 'Bad Request: message is not modified' in str(e):
            return
        # اگر خطای پارسینگ Markdown باشد یا خطای Bad Request دیگر
        elif "Bad Request" in str(e) or "can't parse" in str(e):
            # اگر خطای نمایش بود، متن ساده را می‌فرستد
            bot.send_message(chat_id, f"❌ خطای نمایش: متن با فرمت Markdown قابل نمایش نبود. لطفا کد را بررسی کنید.", parse_mode=None)
        else:
            # سایر خطاها
            pass # پیام خطا را در جای دیگر هندل می‌کنیم.


# --- ۳. تابع ارسال فایل صوتی ---
def send_audio_from_url(url, title, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    # تنظیمات yt-dlp
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
        'no_warnings': True,
    }

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
                raise Exception("نتوانستم فایل دانلود شده را پیدا کنم. (خطای File Find)")
                
            audio_file_path = downloaded_files[0]
            
            # استخراج متادیتا
            final_title = info_dict.get('title', 'Unknown Title')
            artist = info_dict.get('artist') or info_dict.get('uploader')
            caption = final_title
            if artist:
                caption = f"{final_title} - {artist}"

    except Exception as e:
        error_message = f"❌ خطای دانلود: نتوانستم فایل را دانلود کنم. \n دلیل: {str(e)[:250]}"
        # حذف پیام اولیه و ارسال پیام خطا
        bot.delete_message(chat_id, initial_message_id.message_id)
        bot.send_message(chat_id, escape_markdown_v1(error_message))
        
        # پاکسازی
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return

    # مرحله ۲: ارسال فایل
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

        # حذف پیام‌های موقت
        bot.delete_message(chat_id, initial_message_id.message_id)
        
    except Exception as e:
        error_message = f"❌ خطای ارسال: نتوانستم فایل را ارسال کنم. \n دلیل: {str(e)[:250]}"
        bot.send_message(chat_id, escape_markdown_v1(error_message))
    
    finally:
        # پاکسازی نهایی فایل
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# --- ۴. تابع جستجو از متن ---
def search_from_text(message, query, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    escaped_query = escape_markdown_v1(query)
    edit_message(chat_id, initial_message_id.message_id, f"🔍 در حال جستجوی *{escaped_query}* در یوتیوب...")

    try:
        # جستجوی یک نتیجه با فرمت 'ytsearch1:'
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True, 'no_warnings': True}) as ydl:
            info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
        
        if info_dict and 'entries' and info_dict['entries']:
            video_info = info_dict['entries'][0]
            video_link = video_info.get('webpage_url')
            video_title = video_info.get('title', 'عنوان نامشخص')
            
            # ساخت پاسخ برای نمایش نتیجه
            escaped_video_title = escape_markdown_v1(video_title)
            response = f"✅ نتیجه پیدا شد: \n"
            response += f"عنوان: *{escaped_video_title}*\n"
            response += f"لینک: {video_link}"
            
            edit_message(chat_id, initial_message_id.message_id, response, parse_mode='Markdown')
            
            # شروع دانلود و ارسال
            send_audio_from_url(video_link, video_title, initial_message_id)

        else:
            edit_message(chat_id, initial_message_id.message_id, "❌ متأسفانه نتیجه‌ای در جستجو پیدا نشد.")
            
    except Exception as e:
        error_message = f"❌ خطای جستجو: در طول جستجو خطایی رخ داد. \n دلیل: {str(e)[:250]}"
        bot.send_message(chat_id, escape_markdown_v1(error_message))

# --- ۵. هندلرها ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! لینک آهنگ یوتیوب را بفرستید یا متن جستجو را برای من ارسال کنید.")

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
        
# --- ۶. اجرای ربات ---

def cleanup_old_files():
    try:
        # **حل خطای No such file or directory**
        # این خط تضمین می‌کند که پوشه 'downloads' قبل از استفاده ایجاد شود.
        os.makedirs('downloads', exist_ok=True) 
        
        # پاکسازی فایل‌های قدیمی
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
