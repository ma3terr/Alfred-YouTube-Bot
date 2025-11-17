import telebot
import yt_dlp
import re
import os
import glob
import time
import requests

# --- ۱. API Key (توکن فعال خود را اینجا قرار دهید) ---
BOT_TOKEN = "8174456001:AAEyKevw90ynCM91tOB3IS-QTD2432dsa" # توکن شما از تصویر 04D8CFF6-0B71-4C5F-89AE-616EE3A3D74D.png (تغییر یافته برای حفظ امنیت)

bot = telebot.TeleBot(BOT_TOKEN)

# --- ۲. توابع کمکی ---

# این تابع، تمام کاراکرهای خاص Markdown V2 را برای نمایش صحیح خنثی (Escape) می‌کند.
# این کار خطای نمایش: متن با فرمت Markdown قابل نمایش نبود را رفع می‌کند.
def escape_markdown_v2(text):
    if text is None:
        return ""
    # لیست کاراکرهای خاص تلگرام برای Markdown V2
    escape_chars = r'([_*[\]()~>#+=|{}.!-])'
    # کاراکترهای خاص را با یک بک اسلش (\) قبل از آن جایگزین می کند
    return re.sub(escape_chars, r'\\\1', text)

# تابع ویرایش پیام با مدیریت خطا
def edit_message(chat_id, message_id, text, parse_mode='MarkdownV2'):
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode='MarkdownV2'
        )
    except telebot.apihelper.ApiTelegramException as e:
        if 'Bad Request: message is not modified' in str(e):
            return
        # اگر خطای پارسینگ Markdown باشد، متن ساده می‌فرستد.
        elif "Bad Request: can't parse" in str(e):
            # اگر پارسینگ شکست خورد، با فرمت ساده (None) سعی می‌کنیم پیام را ویرایش کنیم.
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=None
            )
        else:
            pass

# --- ۳. تابع ارسال فایل صوتی ---
def send_audio_from_url(url, title, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    # تنظیمات yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        # پیکربندی Postprocessor برای تبدیل به MP3
        # این مرحله نیاز به FFmpeg دارد (که باید در Railway نصب شود)
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
        escaped_title = escape_markdown_v2(title)
        edit_message(chat_id, initial_message_id.message_id, f"🎧 در حال دانلود آهنگ: *{escaped_title}*...", parse_mode='MarkdownV2')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if "instagram.com" in url:
                 raise Exception("دانلود اینستاگرام پشتیبانی نمی‌شود. لطفا لینک یوتیوب بفرستید.")
            
            # **اطمینان از وجود پوشه downloads قبل از شروع دانلود**
            os.makedirs('downloads', exist_ok=True) 

            info_dict = ydl.extract_info(url, download=True)
            
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
        # **حل خطای نمایش Markdown در پیام‌های خطا**
        error_message = f"❌ خطای دانلود یا ارسال آهنگ: نتوانستم فایل را دانلود کنم. \n دلیل: {str(e)[:250]}"
        try:
            # حذف پیام اولیه 
            bot.delete_message(chat_id, initial_message_id.message_id)
        except:
            pass 
        
        # ارسال پیام خطا با parse_mode=None (متن ساده)
        bot.send_message(chat_id, error_message, parse_mode=None) 
        
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return

    # مرحله ۲: ارسال فایل
    try:
        # پیام 'در حال ارسال'
        escaped_final_title = escape_markdown_v2(final_title)
        edit_message(chat_id, initial_message_id.message_id, f"⬆️ در حال ارسال آهنگ: *{escaped_final_title}*...", parse_mode='MarkdownV2')

        with open(audio_file_path, 'rb') as audio_file:
            bot.send_audio(
                chat_id,
                audio_file,
                caption=caption,
                title=final_title,
                performer=artist
            )

        bot.delete_message(chat_id, initial_message_id.message_id)
        
    except Exception as e:
        error_message = f"❌ خطای ارسال: نتوانستم فایل را ارسال کنم. \n دلیل: {str(e)[:250]}"
        bot.send_message(chat_id, error_message, parse_mode=None)
    
    finally:
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# --- ۴. تابع جستجو از متن ---
def search_from_text(message, query, initial_message_id):
    chat_id = initial_message_id.chat.id
    
    escaped_query = escape_markdown_v2(query)
    edit_message(chat_id, initial_message_id.message_id, f"🔍 در حال جستجوی *{escaped_query}* در یوتیوب...", parse_mode='MarkdownV2')

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True, 'no_warnings': True}) as ydl:
            info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
        
        if info_dict and 'entries' and info_dict['entries']:
            video_info = info_dict['entries'][0]
            video_link = video_info.get('webpage_url')
            video_title = video_info.get('title', 'عنوان نامشخص')
            
            escaped_video_title = escape_markdown_v2(video_title)
            response = f"✅ نتیجه پیدا شد: \n"
            response += f"عنوان: *{escaped_video_title}*\n"
            response += f"لینک: {escape_markdown_v2(video_link)}" # لینک را نیز اسکیپ می کنیم
            
            edit_message(chat_id, initial_message_id.message_id, response, parse_mode='MarkdownV2')
            
            send_audio_from_url(video_link, video_title, initial_message_id)

        else:
            edit_message(chat_id, initial_message_id.message_id, "❌ متأسفانه نتیجه‌ای در جستجو پیدا نشد.", parse_mode='MarkdownV2')
            
    except Exception as e:
        error_message = f"❌ خطای جستجو: در طول جستجو خطایی رخ داد. \n دلیل: {str(e)[:250]}"
        bot.send_message(chat_id, error_message, parse_mode=None)

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
        # **حل خطای Attribute Error با ارسال شیء message**
        search_from_text(message, user_text, initial_msg)
        
# --- ۶. اجرای ربات ---

def cleanup_old_files():
    try:
        # **حل خطای No such file or directory**
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
