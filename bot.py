# bot.py
import os
import sys
import requests
from googletrans import Translator
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
FB_TOKEN = os.getenv("FB_ACCESS_TOKEN")  # optional but needed for /fb
OWNER_ID = os.getenv("OWNER_ID")  # optional: restrict restart to owner (Telegram user id)

translator = Translator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✅ Bot চলছে!\n\n"
        "Commands:\n"
        "/start - এই মেসেজ\n"
        "/translate <text> - ইংরেজি (বা অন্য ভাষা) থেকে বাংলা তে translate করে দিবে\n"
        "/fb <facebook_link> - public FB profile/page info ও profile picture দেখাবে\n"
        "/restart - (owner only) bot restart করাবে\n\n"
        "উদাহরণ: /translate Hello world\n"
        "উদাহরণ: /fb https://www.facebook.com/zuck"
    )
    await update.message.reply_text(msg)

# Restart: exit process so Railway will auto-restart the container
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if OWNER_ID:
        try:
            allowed = int(OWNER_ID)
        except:
            allowed = None
        if allowed and user.id != allowed:
            return await update.message.reply_text("❌ আপনি অনুমোদিত নন।")
    await update.message.reply_text("♻️ Restarting bot (Railway will restart)...")
    # flush then exit
    sys.stdout.flush()
    sys.exit(0)

# Translate command
async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        return await update.message.reply_text("ব্যবহার: /translate Hello world")
    try:
        res = translator.translate(text, dest="bn")  # translate to Bengali
        await update.message.reply_text(f"🔤 Translation:\n{res.text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Translate error: {e}")

# Helper to extract FB id/username from URL
def parse_fb_identifier(url: str):
    # remove query params
    url = url.split('?')[0].rstrip('/')
    parts = url.split('/')
    # find last non-empty part
    for part in reversed(parts):
        if part:
            return part
    return None

# FB info
async def fb_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("ব্যবহার: /fb https://www.facebook.com/username_or_page")
    link = context.args[0].strip()
    fb_id = parse_fb_identifier(link)
    if not fb_id:
        return await update.message.reply_text("❌ অবশ্যই একটি সঠিক Facebook URL দিন।")

    if not FB_TOKEN:
        return await update.message.reply_text("❌ FB_ACCESS_TOKEN সেট করা নেই (Graph API token)।")

    url = f"https://graph.facebook.com/{fb_id}"
    params = {
        "fields": "name,about,link,picture.type(large)",
        "access_token": FB_TOKEN
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
    except Exception as e:
        return await update.message.reply_text(f"❌ HTTP error: {e}")

    if "error" in data:
        return await update.message.reply_text(f"❌ FB API error: {data['error'].get('message', data['error'])}")

    name = data.get("name", "Unknown")
    about = data.get("about") or data.get("bio") or "No public about/bio"
    pic = None
    if data.get("picture") and isinstance(data["picture"], dict):
        pic = data["picture"].get("data", {}).get("url")

    caption = f"📌 Name: {name}\nℹ️ About: {about}\n🔗 Link: {link}"
    if pic:
        # send photo with caption
        try:
            await update.message.reply_photo(photo=pic, caption=caption)
        except Exception:
            # fallback to text
            await update.message.reply_text(caption + f"\n\nProfile Picture: {pic}")
    else:
        await update.message.reply_text(caption + "\n\n(Profile picture not available)")

# Catch non-command messages that contain facebook link — optional convenience
async def catch_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if "facebook.com" in text:
        # try to extract link-like token and call fb_info
        parts = text.split()
        for p in parts:
            if "facebook.com" in p:
                # simulate command args
                context.args = [p]
                return await fb_info(update, context)

def main():
    if not BOT_TOKEN:
        print("TG_BOT_TOKEN environment variable not set. Exiting.")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("translate", translate_text))
    app.add_handler(CommandHandler("fb", fb_info))

    # optional: auto-detect facebook links in plain messages
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), catch_links))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
