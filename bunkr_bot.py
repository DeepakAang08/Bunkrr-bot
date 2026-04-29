import os
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@yourchannel")  # e.g. @mychannel
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ---- Dummy web server for Render ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# ---- Scraping ----
def get_bunkr_files(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        files, seen = [], set()
        for a in soup.select("a[href]"):
            href = a["href"]
            if re.search(r"/(v|i|d|f)/[^/]+$", href):
                full = href if href.startswith("http") else "https://bunkr.site" + href
                if full not in seen:
                    seen.add(full)
                    files.append({"url": full, "name": full.split("/")[-1]})
        return files
    except:
        return []

def get_direct(page_url):
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.select("source[src]"):
            s = t.get("src", "")
            if s.startswith("http"): return s
        for t in soup.select("a[download]"):
            s = t.get("href", "")
            if s.startswith("http"): return s
        for t in soup.select("img[src]"):
            s = t.get("src", "")
            if s.startswith("http"): return s
    except:
        pass
    return None

# ---- Bot Commands ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I send Bunkr files to your channel.\n\n"
        "Usage:\n"
        "/send https://bunkr.site/a/xxxxxxxx\n\n"
        f"Files will be posted to: {CHANNEL_ID}"
    )

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if a URL was provided
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide a Bunkr link!\n"
            "Usage: /send https://bunkr.site/a/xxxxxxxx"
        )
        return

    url = context.args[0].strip()

    if "bunkr" not in url or "/a/" not in url:
        await update.message.reply_text("⚠️ Invalid Bunkr album link.")
        return

    await update.message.reply_text(f"🔍 Scanning album...")

    files = get_bunkr_files(url)

    if not files:
        await update.message.reply_text("❌ No files found in that album.")
        return

    await update.message.reply_text(
        f"✅ Found {len(files)} file(s).\n"
        f"📤 Sending to {CHANNEL_ID}..."
    )

    ok, fail = 0, 0

    for i, f in enumerate(files, 1):
        await update.message.reply_text(f"⬇️ Processing {i}/{len(files)}: {f['name']}")

        direct = get_direct(f["url"])
        if not direct:
            await update.message.reply_text(f"⚠️ Skipped (no link): {f['name']}")
            fail += 1
            continue

        try:
            data = requests.get(direct, headers=HEADERS, timeout=60).content
            n = f["name"].lower()

            if any(n.endswith(x) for x in [".mp4", ".mov", ".mkv", ".avi", ".webm"]):
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=data,
                    filename=f["name"],
                    caption=f["name"]
                )
            elif any(n.endswith(x) for x in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=data,
                    caption=f["name"]
                )
            else:
                await context.bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=data,
                    filename=f["name"],
                    caption=f["name"]
                )
            ok += 1

        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {f['name']}\n{str(e)}")
            fail += 1

    await update.message.reply_text(
        f"🏁 All done!\n"
        f"✅ Sent: {ok}\n"
        f"❌ Failed: {fail}\n"
        f"📢 Check your channel: {CHANNEL_ID}"
    )

# ---- Main ----
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_command))
    print("Bot running!")
    app.run_polling()

if __name__ == "__main__":
    main()
