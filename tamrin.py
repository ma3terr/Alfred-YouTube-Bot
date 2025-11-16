import telebot
import yt_dlp
import re
import os
import glob
import time

# --- ۱. API Key ---
# توکن خود را در خط زیر وارد کنید. (توکن را بدون هیچ فضای خالی در ابتدا یا انتها وارد کنید)
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE" 

bot = telebot.TeleBot(BOT_TOKEN)

# --- ۲. تابع اصلاح شده فرار از کاراکترهای Markdown (حل خطای نمایش) ---
# این تابع، تمام کاراکترهای خاص Markdown V1 را برای نمایش صحیح خنثی (Escape) می‌کند.
def escape_markdown_v1(text):
    # لیست کامل کاراکترهای خاص
    escape_chars = r'[_*`\[\]()~>#+\-={}.!]'
    return re.sub(escape_chars, r'\\\g<0>', text)

# --- ۳. تابع اصلاح شده ویرایش پیام (برای هندل کردن خطای Markdown) ---
def edit_message(chat_id, message_id, text, parse_mode='Markdown'):
    try:
        # سعی می‌کند پیام موجود را ویرایش کند
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode
        )
    except Exception as e:
        # اگر ویرایش ناموفق بود (مثلاً خطای Bad Request به خاطر Markdown نامعتبر)
        if "Bad Request" in str(e):
            # اگر خطای Markdown بود، یک پیام جدید با خطای نمایش می‌فرستد
            bot.send_message(chat_id, "❌ خطای نمایش: نتوانستم متن را با فرمت Markdown نمایش دهم. لطفا کد را بررسی کنید.")
        else:
            # سایر خطاهای ناموفق در ویرایش پیام
            bot.send_message(chat_id, "⚠️ خطا در به‌روزرسانی وضعیت.")

# --- ۴. تابع ارسال فایل صوتی (حل خطای FFmpeg محلی) ---
def send_audio_from_url(url, title, initial_message_id=None):
    chat_id = initial_message_id.chat.id
    
    # تنظیمات yt-dlp (ydl_opts)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # مسیر محلی FFmpeg حذف شد تا روی سرور Railway کار کند.
        'outtmpl': f'downloads/{chat_id}_audio_temp.%(ext)s', 
        'noplaylist': True,
        'quiet': True,
    }

    # مرحله ۱: استخراج اطلاعات و دانلود
    try:
        # پیام 'در حال دانلود'
        escaped_title = escape_markdown_v1(title)
        edit_message(chat_id, initial_message_id.message_id, f"🎧 در حال دانلود آهنگ: *{escaped_title}*...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            # استخراج عنوان و نام خواننده برای کپشن
            final_title = info_dict.get('title', 'Unknown Title')
            artist = info_dict.get('artist') or info_dict.get('uploader')
            caption = final_title
            if artist:
                caption = f"{final_title} - {artist}"

    except Exception as e:
        error_message = f"❌ خطای دانلود: نتوانستم فایل را دانلود کنم. \n{str(e)[:150]}"
        edit_message(chat_id, initial_message_id.message_id, escape_markdown_v1(error_message))
        return

    # مرحله ۲: پیدا کردن فایل دانلود شده
    downloaded_files = glob.glob(f"downloads/{chat_id}_audio_temp.*")
    if not downloaded_files:
        edit_message(chat_id, initial_message_id.message_id, "❌ خطای فایل: نتوانستم فایل دانلود شده را پیدا کنم.")
        return

    audio_file_path = downloaded_files[0]

    # مرحله ۳: ارسال فایل و حذف فایل موقت
    try:
        # پیام 'در حال ارسال'
        edit_message(chat_id, initial_message_id.message_id, f"⬆️ در حال ارسال آهنگ: *{escape_markdown_v1(final_title)}*...")

        with open(audio_file_path, 'rb') as audio_file:
            bot.send_audio(
                chat_id,
                audio_file,
                caption=escape_markdown_v1(caption),
                title=final_title
            )

        # حذف پیام‌های موقت و فایل صوتی پس از ارسال موفق
        bot.delete_message(chat_id, initial_message_id.message_id)
        os.remove(audio_file_path)
        
        # حذف هر فایل mp3 که ممکن است از دانلود قبلی مانده باشد
        for f in glob.glob(f"downloads/{chat_id}_audio_temp.mp3"):
            os.remove(f)


    except Exception as e:
        error_message = f"❌ خطای ارسال: نتوانستم فایل را ارسال کنم. \n{str(e)[:150]}"
        bot.send_message(chat_id, escape_markdown_v1(error_message))
        # پاکسازی پس از خطا
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# --- ۵. تابع جستجو از متن ---
def search_from_text(message, query, initial_message_id=None):
    chat_id = initial_message_id.chat.id
    
    # به‌روزرسانی پیام 'در حال جستجو'
    escaped_query = escape_markdown_v1(query)
    edit_message(chat_id, initial_message_id.message_id, f"🔍 در حال جستجوی *{escaped_query}*...")

    try:
        # استفاده از Search در yt-dlp
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            # جستجوی یک نتیجه با فرمت 'ytsearch1:'
            info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
        
        if 'entries' and info_dict['entries']:
            video_info = info_dict['entries'][0]
            video_link = video_info.get('webpage_url')
            video_title = video_info.get('title')
            
            # ساخت پاسخ با استفاده از Markdown V1 و فرار از کاراکترها
            escaped_video_title = escape_markdown_v1(video_title)
            response = f"✅ نتیجه پیدا شد: \n"
            response += f"عنوان: *{escaped_video_title}*\n"
            response += f"لینک: [ویدیو]({video_link})"
            
            edit_message(chat_id, initial_message_id.message_id, response, parse_mode='Markdown')
            
            # شروع دانلود و ارسال
            send_audio_from_url(video_link, video_title, initial_message_id)

        else:
            edit_message(chat_id, initial_message_id.message_id, "❌ متأسفانه نتیجه‌ای در جستجو پیدا نشد.")
            
    except Exception as e:
        error_message = f"❌ خطای جستجو: در طول جستجو خطایی رخ داد. \n{str(e)[:150]}"
        edit_message(chat_id, initial_message_id.message_id, escape_markdown_v1(error_message))

# --- ۶. هندلرها ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! لینک آهنگ یوتیوب را بفرستید یا متن جستجو را برای من ارسال کنید.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_text = message.text
    
    # پیام اولیه 'در حال شروع فرآیند...'
    initial_msg = bot.send_message(message.chat.id, "⏳ در حال شروع فرآیند...")
    initial_message_id = initial_msg.message_id
    
    # پوشه دانلودها را چک و ایجاد می‌کند
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # اگر ورودی با 'http' شروع شود، فرض می‌کنیم لینک است
    if user_text.startswith('http'):
        edit_message(message.chat.id, initial_message_id, f"🔗 لینک دریافت شد، در حال پردازش...")
        send_audio_from_url(user_text, 'Unknown Title', initial_message_id)
    
    # در غیر این صورت، جستجو می‌کنیم
    else:
        search_from_text(message, user_text, initial_message_id)

# --- ۷. اجرای ربات ---

# حذف هرگونه فایل موقت mp3 قدیمی که ممکن است از اجراهای قبلی مانده باشد
for f in glob.glob("downloads/*_audio_temp.mp3"):
    try:
        os.remove(f)
    except:
        pass

print("Bot is running...")
# برای اطمینان از حذف فایل‌های قدیمی، یک مکث کوتاه اضافه می‌شود
time.sleep(1) 

# اجرای بی‌نهایت ربات (Polling)
bot.infinity_polling()
