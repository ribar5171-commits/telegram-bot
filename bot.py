import os
import re
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest
from telegram.error import BadRequest

# ================== تنظیمات ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DELETE_AFTER = 41

def parse_ids(text: str):
    text = text.strip()

    range_match = re.match(r"^(\d+)\s*(?:تا|-)\s*(\d+)$", text)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start > end:
            start, end = end, start
        return list(range(start, end + 1)), "range"

    if "با" in text:
        numbers = re.findall(r"\d+", text)
        if numbers:
            return [int(n) for n in numbers], "list"

    if text.isdigit():
        return [int(text)], "single"

    return None, None

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("شما دسترسی ندارید.")
        return

    text = update.message.text.strip()
    match = re.search(r"(?:/add|اد فایل|اضافه فایل)\s+(.+)", text, re.IGNORECASE)
    
    if not match:
        await update.message.reply_text(
            "مثال‌ها:\n`اد فایل 55`\n`اد فایل 10 تا 20`\n`اد فایل 26 با 90`",
            parse_mode="Markdown"
        )
        return

    payload = match.group(1).strip()
    ids, mode = parse_ids(payload)

    if not ids:
        await update.message.reply_text("فرمت اشتباهه.")
        return

    bot_username = (await context.bot.get_me()).username

    if mode == "range":
        link_payload = f"{ids[0]}-{ids[-1]}"
        desc = f"از پیام **{ids[0]}** تا **{ids[-1]}**"
    elif mode == "list":
        link_payload = "_".join(str(i) for i in ids)
        desc = " + ".join(f"**{i}**" for i in ids)
    else:
        link_payload = str(ids[0])
        desc = f"پیام شماره **{ids[0]}**"

    link = f"https://t.me/{bot_username}?start={link_payload}"

    await update.message.reply_text(
        f"✅ لینک ساخته شد\n\n{desc}\n\n🔗 لینک:\n`{link}`",
        parse_mode="Markdown"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("برای دریافت فایل روی لینک کانال کلیک کن.")
        return

    payload = args[0].strip()
    chat_id = update.effective_chat.id
    message_ids = []

    if "-" in payload and payload.replace("-", "").isdigit():
        parts = payload.split("-")
        start, end = int(parts[0]), int(parts[1])
        if start > end:
            start, end = end, start
        message_ids = list(range(start, end + 1))
    elif "_" in payload:
        message_ids = [int(x) for x in payload.split("_") if x.isdigit()]
    elif payload.isdigit():
        message_ids = [int(payload)]
    else:
        await update.message.reply_text("لینک نامعتبر است.")
        return

    sent_messages = []

    for msg_id in message_ids:
        try:
            sent = await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
            sent_messages.append(sent.message_id)
        except Exception:
            continue

    if not sent_messages:
        await update.message.reply_text("هیچ فایلی پیدا نشد.")
        return

    context.job_queue.run_once(
        delete_messages,
        when=DELETE_AFTER,
        data={"chat_id": chat_id, "message_ids": sent_messages}
    )

async def delete_messages(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    for msg_id in job_data["message_ids"]:
        try:
            await context.bot.delete_message(chat_id=job_data["chat_id"], message_id=msg_id)
        except Exception:
            pass

def main():
    # رفع قطعی مشکل event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)

    app = Application.builder().token(BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)(اد فایل|اضافه فایل)"), add_command))
    app.add_handler(CommandHandler("start", start))

    print("ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
