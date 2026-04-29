import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ============================
# PUT YOUR BOT TOKEN HERE
# ============================
BOT_TOKEN = "8604002829:AAFGYbn3Hx7FyXU1MoXdYToEpZzqTdoJ55A"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ---- Helper: Extract files from a Bunkr album ----
def get_bunkr_files(album_url: str) -> list[dict]:
    """Scrape all file links from a Bunkr album page."""
    try:
        resp = requests.get(album_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    files = []

    # Bunkr album items are in <a> tags with links to individual file pages
    for a_tag in soup.select("a[href]"):
        href = a_tag["href"]
        # Match individual file pages like /v/filename or /i/filename or /d/filename
        if re.search(r"/(v|i|d|f)/[^/]+$", href):
            full_url = href if href.startswith("http") else "https://bunkr.site" + href
            name = full_url.split("/")[-1]
            files.append({"page_url": full_url, "name": name})

    # Remove duplicates
    seen = set()
    unique = []
    for f in files:
        if f["page_url"] not in seen:
            seen.add(f["page_url"])
            unique.append(f)

    return unique


def get_direct_url(file_page_url: str) -> str | None:
    """Visit a Bunkr file page and extract the real download URL."""
    try:
        resp = requests.get(file_page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Look for <source src="..."> (videos) or <img src="..."> or <a download href="...">
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

    # Validate it looks like a bunkr album link
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
            # Download the file
            r = requests.get(direct_url, headers=HEADERS, timeout=60, stream=True)
            r.raise_for_status()

            file_data = r.content
            fname = file_info["name"]

            # Send based on file type
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
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
