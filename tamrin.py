import telebot
import yt_dlp
import re
import os
import glob
import time
import requests

# ----------------------------------------------------
# --- ۱. API Key (توکن جدید خود را اینجا قرار دهید) ---
# ----------------------------------------------------
# توکن جدید خود را که از بات‌فادر دریافت می‌کنید، اینجا جایگزین کنید:
BOT_TOKEN = "اینجا_توکن_جدید_را_بنویسید_لطفا" 

bot = telebot.TeleBot(BOT_TOKEN)

# ------------------------
# --- ۲. توابع کمکی ---
# ------------------------

# این تابع، تمام کاراکرهای خاص Markdown V2 را برای نمایش صحیح خنثی (Escape) می‌کند.
def escape_markdown_v2(text):
    if text is None:
        return ""
    # لیست کاراکرهای خاص تلگرام برای Markdown V2
    escape_chars = r'([_*[\]()~>#+=|{}.!-])'
    # کاراکترهای خاص را با یک بک اسلش (\) قبل از آن جایگزین می کند
    return re.sub(escape_chars, r'\\\1', text)

# تابع ویرایش پیام با مدیریت خطا
def edit_message(chat_id, message_id, text):
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode='MarkdownV2'
        )
    except telebot.apihelper.ApiTelegramException as e:
        # اگر خطا "message is not modified" باشد، یعنی محتوا تکراری است.
        if 'Bad Request: message is not modified' in str(e):
            return
        # اگر خطای پارسینگ Markdown باشد، با فرمت ساده ویرایش می‌شود.
        elif "Bad Request: can't parse" in str(e):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=None
            )
        else:
            # خطاهای دیگر را نادیده می‌گیرد
            pass

# --------------------------------------
# --- ۳. تابع ارسال فایل صوتی (اصلاح‌شده) ---
# --------------------------------------
# تغییر: chat_id مستقیماً به عنوان ورودی دریافت می‌شود تا خطای Attribute Error رفع شود
def send_audio_from_url(url, title, initial_message_id, chat_id): 
    
    # تنظیمات yt-dlp (بدون نیاز به FFmpeg برای رفع خطای not found)
    ydl_opts = {
        # فقط بهترین فایل صوتی را مستقیماً دانلود می‌کند (بدون تبدیل)
        'format': 'bestaudio', 
        
        # **بخش postprocessors که نیاز به FFmpeg داشت حذف شده است**
        
        # تنظیم نام فایل
        'outtmpl': f'downloads/{chat_id}_audio_temp.%(ext)s', 
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    audio_file_path = None
    
    try:
        # پیام 'در حال دانلود'
        escaped_title = escape_markdown_v2(title)
        edit_message(chat_id, initial_message_id.message_id, f"🎧 در حال دانلود آهنگ: *{escaped_title}*...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if "instagram.com" in url:
                 raise Exception("دانلود اینستاگرام پشتیبانی نمی‌شود. لطفا لینک یوتیوب بفرستید.")
            
            os.makedirs('downloads', exist_ok=True) 

            # دانلود
            info_dict = ydl.extract_info(url, download=True)
            
            # پیدا کردن فایل دانلود شده (چون فرمت را yt-dlp مشخص می‌کند)
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
            
            caption = escape_markdown_v2(caption) 

    except Exception as e:
        # مدیریت خطای دانلود
        error_message = f"❌ خطای دانلود یا ارسال آهنگ: نتوانستم فایل را دانلود کنم. \n دلیل: {escape_markdown_v2(str(e)[:250])}"
        try:
            # حذف پیام اولیه برای تمیزی
            bot.delete_message(chat_id, initial_message_id.message_id)
        except:
            pass 
        
        bot.send_message(chat_id, error_message, parse_mode='MarkdownV2') 
        
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return

    # مرحله ۲: ارسال فایل
    try:
        # پیام 'در حال ارسال'
        escaped_final_title = escape_markdown_v2(final_title)
        edit_message(chat_id, initial_message_id.message_id, f"⬆️ در حال ارسال آهنگ: *{escaped_final_title}*...")

        # تعیین نوع فایل بر اساس پسوند برای ارسال صحیح
        with open(audio_file_path, 'rb') as audio_file:
            # فایل را به عنوان سند (document) می‌فرستیم تا مطمئن شویم با هر پسوندی ارسال می‌شود.
            bot.send_document(
                chat_id,
                audio_file,
                caption=caption,
                visible_file_name=f"{final_title}.mp3" # نام فایل را در ظاهر mp3 می گذاریم
            )

        bot.delete_message(chat_id, initial_message_id.message_id)
        
    except Exception as e:
        error_message = f"❌ خطای ارسال: نتوانستم فایل را ارسال کنم. \n دلیل: {escape_markdown_v2(str(e)[:250])}"
        bot.send_message(chat_id, error_message, parse_mode='MarkdownV2')
    
    finally:
        # پاکسازی فایل موقت
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# ----------------------------------
# --- ۴. تابع جستجو از متن (اصلاح‌شده) ---
# ----------------------------------
# تغییر: chat_id مستقیماً به عنوان ورودی دریافت می‌شود
def search_from_text(message, query, initial_message_id, chat_id):
    
    escaped_query = escape_markdown_v2(query)
    edit_message(chat_id, initial_message_id.message_id, f"🔍 در حال جستجوی *{escaped_query}* در یوتیوب...")

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True, 'no_warnings': True}) as ydl:
            # جستجوی فقط یک نتیجه (ytsearch1:)
            info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
        
        if info_dict and 'entries' and info_dict['entries']:
            video_info = info_dict['entries'][0]
            video_link = video_info.get('webpage_url')
            video_title = video_info.get('title', 'عنوان نامشخص')
            
            escaped_video_title = escape_markdown_v2(video_title)
            response = f"✅ نتیجه پیدا شد: \n"
            response += f"عنوان: *{escaped_video_title}*\n"
            response += f"لینک: {escape_markdown_v2(video_link)}"
            
            edit_message(chat_id, initial_message_id.message_id, response)
            
            # شروع دانلود فایل صوتی
            send_audio_from_url(video_link, video_title, initial_message_id, chat_id)

        else:
            edit_message(chat_id, initial_message_id.message_id, "❌ متأسفانه نتیجه‌ای در جستجو پیدا نشد.")
            
    except Exception as e:
        error_message = f"❌ خطای جستجو: در طول جستجو خطایی رخ داد. \n دلیل: {escape_markdown_v2(str(e)[:250])}"
        bot.send_message(chat_id, error_message, parse_mode='MarkdownV2')

# --------------------------
# --- ۵. هندلرها و شروع ربات (اصلاح‌شده) ---
# --------------------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! لینک آهنگ یوتیوب را بفرستید یا متن جستجو را برای من ارسال کنید.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_text = message.text
    chat_id = message.chat.id # <--- استخراج صحیح chat_id
    
    initial_msg = bot.send_message(chat_id, "⏳ در حال شروع فرآیند...")
    
    # اگر ورودی با 'http' شروع شود، فرض می‌کنیم لینک است
    if user_text.startswith('http'):
        edit_message(chat_id, initial_msg.message_id, f"🔗 لینک دریافت شد، در حال پردازش...")
        # ارسال chat_id استخراج شده
        send_audio_from_url(user_text, 'Unknown Title', initial_msg, chat_id) 
    
    # در غیر این صورت، جستجو می‌کنیم
    else:
        # ارسال chat_id استخراج شده
        search_from_text(message, user_text, initial_msg, chat_id)
        
# --------------------------
# --- ۶. اجرای ربات ---
# --------------------------

def cleanup_old_files():
    try:
        os.makedirs('downloads', exist_ok=True) 
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
