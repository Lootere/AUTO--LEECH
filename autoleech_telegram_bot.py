import os
import time
import threading
import feedparser
import qbittorrentapi
from telegram import Update, Bot, ParseMode
from telegram.ext import CommandHandler, Updater, CallbackContext

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Set your bot token
TELEGRAM_TARGET = os.environ.get("TELEGRAM_TARGET")  # User ID or channel username
QB_HOST = os.environ.get("QB_HOST", "localhost")
QB_PORT = int(os.environ.get("QB_PORT", 8080))
QB_USERNAME = os.environ.get("QB_USERNAME", "admin")
QB_PASSWORD = os.environ.get("QB_PASSWORD", "adminadmin")
DOWNLOAD_PATH = os.environ.get("DOWNLOAD_PATH", "./downloads")
FEEDS_FILE = "feeds.txt"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# --- qBittorrent Setup ---
qb = qbittorrentapi.Client(host=QB_HOST, port=QB_PORT, username=QB_USERNAME, password=QB_PASSWORD)
try:
    qb.auth_log_in()
except Exception as e:
    print(f"qBittorrent connection error: {e}")

# --- Helper Functions ---

def load_feeds():
    if not os.path.isfile(FEEDS_FILE):
        return []
    with open(FEEDS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_feed(url):
    feeds = load_feeds()
    if url not in feeds:
        with open(FEEDS_FILE, "a") as f:
            f.write(url + "\n")
        return True
    return False

def fetch_and_enqueue(bot=None, context=None):
    feeds = load_feeds()
    for feed_url in feeds:
        d = feedparser.parse(feed_url)
        for entry in d.entries:
            link = entry.get("link")
            if not link:
                continue
            # Try to avoid adding the same torrent repeatedly: use tag or file as marker
            tag = "[autoleech]"
            try:
                if link.startswith("magnet:"):
                    qb.torrents_add(urls=link, save_path=DOWNLOAD_PATH, tags=tag)
                elif link.endswith(".torrent"):
                    qb.torrents_add(urls=link, save_path=DOWNLOAD_PATH, tags=tag)
            except Exception as ex:
                print(f"Failed to add: {link} - {ex}")

def get_completed_downloads():
    return [
        t for t in qb.torrents_info(status_filter="completed", tag="[autoleech]")
        if t.save_path and any(t.name.endswith(ext) for ext in [".mkv", ".mp4"])
    ]

def upload_to_telegram(bot_token, chat_id, file_path):
    bot = Bot(bot_token)
    with open(file_path, "rb") as f:
        bot.send_document(chat_id=chat_id, document=f, filename=os.path.basename(file_path))

def process_and_upload(bot_token, chat_id):
    completed = get_completed_downloads()
    for torrent in completed:
        full_path = os.path.join(torrent.save_path, torrent.name)
        if os.path.exists(full_path):
            try:
                upload_to_telegram(bot_token, chat_id, full_path)
                qb.torrents_delete(delete_files=True, torrent_hashes=torrent.hash)
                print(f"Uploaded and deleted: {full_path}")
            except Exception as ex:
                print(f"Upload failed: {full_path} - {ex}")

# --- Telegram Command Handlers ---

def add_feed(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].startswith("http"):
        update.message.reply_text("Usage: /add <RSS feed URL>")
        return
    url = context.args[0]
    if save_feed(url):
        update.message.reply_text(f"Feed added: {url}")
    else:
        update.message.reply_text("Feed already exists.")

def refresh_handler(update: Update, context: CallbackContext):
    fetch_and_enqueue()
    update.message.reply_text("Feeds refreshed and torrents enqueued.")

def status_handler(update: Update, context: CallbackContext):
    downloading = qb.torrents_info(status_filter="downloading")
    completed = get_completed_downloads()
    msg = f"Active downloads: {len(downloading)}\nCompleted (awaiting upload): {len(completed)}"
    update.message.reply_text(msg)

# --- Periodic Job ---
def periodic_job():
    while True:
        fetch_and_enqueue()
        process_and_upload(TELEGRAM_TOKEN, TELEGRAM_TARGET)
        time.sleep(300)  # 5 min

# --- Main ---

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("add", add_feed))
    dp.add_handler(CommandHandler("refresh", refresh_handler))
    dp.add_handler(CommandHandler("status", status_handler))

    # Start periodic background worker
    threading.Thread(target=periodic_job, daemon=True).start()

    updater.start_polling()
    print("Bot started. Listening for commands...")
    updater.idle()

if __name__ == "__main__":
    main()