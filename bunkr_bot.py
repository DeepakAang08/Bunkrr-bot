import os
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ============================
# PUT YOUR BOT TOKEN HERE
# ============================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8604002829:AAFGYbn3Hx7FyXU1MoXdYToEpZzqTdoJ55A")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ---- Dummy web server to satisfy Render ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# ---- Helper: Extract files from a Bunkr album ----
def get_bunkr_files(album_url: str) -> list[dict]:
    try:
        resp = requests.get(album_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    files = []

    for a_tag in soup.select("a[href]"):
        href = a_tag["href"]
        if re.search(r"/(v|i|d|f)/[^/]+$", href):
            full_url = href if href.startswith("http") else "https://bunkr.site" + href
            name = full_url.split("/")[-1]
            files.append({"page_url": full_url, "name": name})

    seen = set()
    unique = []
    for f in files:
        if f["page_url"] not in seen:
            seen.add(f["page_url"])
            unique.append(f)

    return unique


def get_direct_url(file_page_url: str) -> str | None:
    try:
        resp = requests.get(file_page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup.select("source[src]"):
        src = tag.get("src", "")
        if src.startswith("http") and any(ext in src for ext in [".mp4", ".mov", ".mkv", ".avi"]):
            return src

    for tag in soup.select("a[download]"):
        href = tag.get("href", "")
        if href.startswith("http"):
            return href

    for tag in soup.select("img[src]"):
        src = tag.get("src", "")
        if src.startswith("http") and any(ext in src for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            return src

    return None


# ---- Bot Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Bunkr Downloader Bot!\n\n"
        "Just send me a Bunkr album link like:\n"
        "https://bunkr.site/a/xxxxxxxx\n\n"
        "And I'll download all the files for you! 🚀"
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "bunkr" not in url or "/a/" not in url:
        await update.message.reply_text(
            "⚠️ Please send a valid Bunkr album link.\n"
            "Example: https://bunkr.site/a/xxxxxxxx"
        )
        return

    await update.message.reply_text("🔍 Scanning album... please wait.")

    files = get_bunkr_files(url)

    if not files:
        await update.message.reply_text("❌ No files found. The album might be empty or the link is invalid.")
        return

    await update.message.reply_text(f"✅ Found {len(files)} file(s). Starting download...")

    success = 0
    failed = 0

    for i, file_info in enumerate(files, 1):
        await update.message.reply_text(f"⬇️ Downloading file {i}/{len(files)}: {file_info['name']}")

        direct_url = get_direct_url(file_info["page_url"])

        if not direct_url:
            await update.message.reply_text(f"⚠️ Could not get download link for: {file_info['name']}")
            failed += 1
            continue

        try:
            r = requests.get(direct_url, headers=HEADERS, timeout=60, stream=True)
            r.raise_for_status()
            file_data = r.content
            fname = file_info["name"]

            if any(fname.lower().endswith(ext) for ext in [".mp4", ".mov", ".mkv", ".avi", ".webm"]):
                await update.message.reply_video(video=file_data, filename=fname)
            elif any(fname.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                await update.message.reply_photo(photo=file_data)
            else:
                await update.message.reply_document(document=file_data, filename=fname)

            success += 1

        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send {file_info['name']}: {str(e)}")
            failed += 1

    await update.message.reply_text(
        f"🏁 Done!\n✅ Success: {success}\n❌ Failed: {failed}"
    )


# ---- Main ----
def main():
    # Start dummy web server in background thread
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
