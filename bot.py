import json
import os
import asyncio
import time
from uuid import uuid4
from typing import Any, Dict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import RetryAfter


# ================= CONFIG =================

# Replit: set BOT_TOKEN in Secrets.
TOKEN = os.getenv("BOT_TOKEN", "token botfather")

CHANNEL_USERNAME = "@mtlofc"

CHANNELS = [
    (-1002898158139, "https://t.me/+Wvx7ydVVmB01MjM9"),
    (-1003887541991, "https://t.me/+xE6hIy3yXIk0MWU1"),
    (-1004479812201, "https://t.me/+eQP1P6V9cfIyNDRl"),
]

OWNER_ID = 8129334904
POST_ADMIN_IDS = [1452491231]

DATA_FILE = "data.json"
BACKUP_FILE = "backup_data.json"

DEFAULT_COIN_PREM = 25
POST_CHANNEL = -1003571662326
PAP_CHANNEL = "@siniratepap"

PENDING_POST: Dict[str, Dict[str, Any]] = {}
BOT_USERNAME = None


# ================= DATABASE =================

def default_data() -> Dict[str, Any]:
    return {
        "content": {},
        "users": [],
        "clicks": 0,
        "coin": {},
        "premium_users": [],
        "referral_count": {},
        "thumbnail_main": None,
        "thumbnail_pap": None,
    }


def load_data() -> Dict[str, Any]:
    """Load database and migrate missing fields from older versions."""
    if not os.path.exists(DATA_FILE):
        data = default_data()
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("data.json is not a JSON object")

        defaults = default_data()
        changed = False

        for key, value in defaults.items():
            if key not in data:
                data[key] = value
                changed = True

        if changed:
            save_data(data)

        return data

    except Exception:
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                defaults = default_data()
                for key, value in defaults.items():
                    data.setdefault(key, value)

                save_data(data)
                return data
            except Exception:
                pass

        data = default_data()
        save_data(data)
        return data


def save_data(data: Dict[str, Any]) -> None:
    """Atomic database write plus backup."""
    temp_file = DATA_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_file, DATA_FILE)

    with open(BACKUP_FILE, "w", encoding="utf-8") as b:
        json.dump(data, b, indent=2, ensure_ascii=False)
        b.flush()
        os.fsync(b.fileno())


def get_coin(data: Dict[str, Any], user_id: int | str) -> int:
    return int(data.get("coin", {}).get(str(user_id), 0))


def add_coin(data: Dict[str, Any], user_id: int | str, amount: int = 1) -> None:
    uid = str(user_id)
    data.setdefault("coin", {})
    data["coin"][uid] = get_coin(data, user_id) + amount
    save_data(data)


def reduce_coin(data: Dict[str, Any], user_id: int | str, amount: int) -> None:
    uid = str(user_id)
    data.setdefault("coin", {})
    data["coin"][uid] = max(0, get_coin(data, user_id) - amount)
    save_data(data)


def is_premium(data: Dict[str, Any], user_id: int | str) -> bool:
    return str(user_id) in data.get("premium_users", [])


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def check_membership(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    not_joined = []

    tasks = [
        context.bot.get_chat_member(chat_id, user_id)
        for chat_id, _ in CHANNELS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for channel, result in zip(CHANNELS, results):
        if isinstance(result, Exception):
            not_joined.append(channel)
        elif result.status in ("left", "kicked"):
            not_joined.append(channel)

    return not_joined


def join_keyboard(not_joined):
    buttons = [
        [InlineKeyboardButton("➕ Join Channel", url=url)]
        for _, url in not_joined
    ]
    return InlineKeyboardMarkup(buttons)


async def send_content(
    message,
    item: Dict[str, Any],
    is_pap: bool = False,
) -> None:
    item_type = item.get("type")

    if item_type == "text":
        await message.reply_text(
            item.get("content", ""),
            protect_content=True,
        )

    elif item_type == "photo":
        await message.reply_photo(
            item["content"],
            caption=item.get("caption", "") if is_pap else None,
            protect_content=True,
        )

    elif item_type == "video":
        await message.reply_video(
            item["content"],
            caption=item.get("caption", "") if is_pap else None,
            protect_content=True,
        )


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    data = load_data()

    if user.id not in data["users"]:
        data["users"].append(user.id)
        save_data(data)

    if not context.args:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "ASUPAN MEDIA",
                    url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                )
            ]
        ])

        await update.message.reply_text(
            "Bot aktif.\nPowered by @AsupanLokaI",
            reply_markup=keyboard,
        )
        return

    key = context.args[0]
    is_pap = False

    if key.startswith("pap_"):
        key = key.removeprefix("pap_")
        is_pap = True

    if key not in data["content"]:
        return

    t0 = time.time()
    not_joined = await check_membership(context, user.id)

    if not_joined:
        buttons = [
            [InlineKeyboardButton("➕ Join Channel", url=url)]
            for _, url in not_joined
        ]
        buttons.append([
            InlineKeyboardButton(
                "🔄 Coba Lagi",
                callback_data=f"retry_{key}",
            )
        ])

        name = user.mention_html()

        await update.message.reply_text(
            (
                f"<blockquote>👋 Hello {name}\n\n"
                "Anda harus bergabung di Channel/Group saya terlebih dahulu "
                "untuk melihat media yang saya bagikan.\n\n"
                "Silakan Join Ke Channel &amp; Group Terlebih Dahulu"
                "</blockquote>"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    print(f"FSub check selesai dalam {time.time() - t0:.2f} detik")

    await send_content(
        update.message,
        data["content"][key],
        is_pap=is_pap,
    )


# ================= CALLBACK =================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    user = query.from_user
    data = load_data()

    # ---------- PREMIUM CONTENT ----------
    if query.data.startswith("prem_"):
        key = query.data.split("_", 1)[1]

        if key not in data["content"]:
            await query.message.reply_text("❌ Data tidak ditemukan.")
            return

        item = data["content"][key]
        coin_required = int(
            item.get("coin_required", DEFAULT_COIN_PREM)
        )

        if not is_premium(data, user.id):
            user_coin = get_coin(data, user.id)

            if user_coin < coin_required:
                await query.message.reply_text(
                    "🚫 Coin Tidak Cukup.\n"
                    "Untuk mendapatkan COIN gratis gunakan tombol "
                    "Dapatkan Coin."
                )
                return

            reduce_coin(data, user.id, coin_required)

            await query.message.reply_text(
                f"Coin Terpakai: -{coin_required}\n"
                f"Coin Anda Saat Ini: {get_coin(data, user.id)} 💰"
            )

        await send_content(query.message, item)

    # ---------- POST MAIN ----------
    elif query.data.startswith("postmain_"):
        pid = query.data.split("_", 1)[1]

        if pid not in PENDING_POST:
            await query.message.reply_text("❌ Data hilang.")
            return

        post_data = PENDING_POST[pid]
        data = load_data()
        thumb = data.get("thumbnail_main")

        try:
            if thumb:
                await context.bot.send_photo(
                    chat_id=POST_CHANNEL,
                    photo=thumb,
                    caption=(
                        f"{post_data['text']}\n\n"
                        "<blockquote>KASI REACT EMOJI DONG KA 😘</blockquote>"
                    ),
                    parse_mode="HTML",
                )
            else:
                await context.bot.send_message(
                    chat_id=POST_CHANNEL,
                    text=post_data["text"],
                    parse_mode="HTML",
                )

            await query.edit_message_text(
                "✅ BERHASIL DIPOST KE CHANNEL"
            )

        except Exception as e:
            await query.message.reply_text(
                f"❌ ERROR POST\n\n{e}"
            )

        PENDING_POST.pop(pid, None)

    # ---------- POST PAP ----------
    elif query.data.startswith("postpap_"):
        pid = query.data.split("_", 1)[1]

        if pid not in PENDING_POST:
            await query.message.reply_text("❌ Data hilang.")
            return

        post_data = PENDING_POST[pid]

        if post_data["key"] not in data["content"]:
            await query.message.reply_text("❌ Content tidak ditemukan.")
            PENDING_POST.pop(pid, None)
            return

        pap_key = str(uuid4())[:8]
        source = data["content"][post_data["key"]]

        data["content"][pap_key] = {
            "type": source["type"],
            "content": source["content"],
            "caption": source.get("raw_caption", ""),
        }

        save_data(data)

        bot_username = BOT_USERNAME or (await context.bot.get_me()).username
        pap_link = f"https://t.me/{bot_username}?start=pap_{pap_key}"

        thumb = data.get("thumbnail_pap")

        title = post_data["title"] or "rate dong sayang"

        try:
            if thumb:
                await context.bot.send_photo(
                    chat_id=PAP_CHANNEL,
                    photo=thumb,
                    caption=(
                        f"{title}\n\n"
                        f"{pap_link}\n\n"
                        "ᴅᴏɴᴀsɪ ᴋɪʀɪᴍ ᴋᴇsɪɴɪ\n"
                        "@DONASIPAPSBOT"
                    ),
                    parse_mode="HTML",
                )
            else:
                await context.bot.send_message(
                    chat_id=PAP_CHANNEL,
                    text=(
                        f"{post_data['text']}\n\n"
                        "BOT DONASI CEWEK\n"
                        "@namabottele"
                    ),
                    parse_mode="HTML",
                )

            await query.edit_message_text(
                "✅ BERHASIL DIPOST KE CHANNEL PAP"
            )

        except Exception as e:
            await query.message.reply_text(
                f"❌ ERROR POST\n\n{e}"
            )

        PENDING_POST.pop(pid, None)

    # ---------- LINK ONLY ----------
    elif query.data.startswith("linkonly_"):
        pid = query.data.split("_", 1)[1]

        if pid not in PENDING_POST:
            await query.message.reply_text("❌ Data hilang.")
            return

        post_data = PENDING_POST[pid]

        await query.message.edit_text(
            f"🔗 LINK GENERATE\n\n{post_data['text']}"
        )

        PENDING_POST.pop(pid, None)

    # ---------- GET COIN ----------
    elif query.data.startswith("getcoin_"):
        target_id = query.data.split("_", 1)[1]
        bot_username = BOT_USERNAME or (await context.bot.get_me()).username

        share_url = (
            "https://t.me/share/url?"
            f"url=https://t.me/{bot_username}?start={target_id}"
            "&text=BACA%20CERITA%20ENAK%20DISINI"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Share & Dapatkan Coin Gratis 💰",
                    url=share_url,
                )
            ]
        ])

        await query.message.reply_text(
            "Dapatkan Coin Gratis Dengan Share Bot Ini ke Grup / Chat 👇",
            reply_markup=keyboard,
        )

    # ---------- RETRY F-SUB ----------
    elif query.data.startswith("retry_"):
        key = query.data.split("_", 1)[1]

        if key not in data["content"]:
            await query.message.reply_text("❌ Data tidak ditemukan.")
            return

        not_joined = await check_membership(context, user.id)

        if not_joined:
            buttons = [
                [InlineKeyboardButton("➕ Join Channel", url=url)]
                for _, url in not_joined
            ]
            buttons.append([
                InlineKeyboardButton(
                    "🔄 Coba Lagi",
                    callback_data=f"retry_{key}",
                )
            ])

            await query.message.reply_text(
                "🚫 Anda belum join semua channel!\n"
                "TUTORIAL ADA DI SINI:\n"
                "https://t.me/CekTutornya/8",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        await send_content(
            query.message,
            data["content"][key],
        )


# ================= OWNER COMMANDS =================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    message = update.effective_message
    raw_text = message.text or ""

    if not raw_text.lower().startswith("/broadcast"):
        await message.reply_text("Gunakan: /broadcast teks")
        return

    text = raw_text[len("/broadcast"):].lstrip()

    if not text:
        await message.reply_text("Gunakan: /broadcast teks")
        return

    original_entities = message.entities or []

    prefix = raw_text[:len(raw_text) - len(text)]
    prefix_utf16_length = len(prefix.encode("utf-16-le")) // 2

    entities = [
        entity
        for entity in original_entities
        if entity.offset >= prefix_utf16_length
    ]

    entities = MessageEntity.shift_entities(
        -prefix_utf16_length,
        entities,
    )

    data = load_data()
    queue = asyncio.Queue()

    for user_id in data["users"]:
        await queue.put(user_id)

    await message.reply_text(
        f"🚀 Broadcast dimulai\nTarget: {queue.qsize()} user"
    )

    success = 0
    failed = 0
    rate_lock = asyncio.Lock()
    last_send_time = 0.0
    send_interval = 0.05

    async def worker():
        nonlocal success, failed, last_send_time

        while True:
            user_id = await queue.get()

            try:
                while True:
                    try:
                        async with rate_lock:
                            now = asyncio.get_running_loop().time()
                            wait_time = send_interval - (
                                now - last_send_time
                            )

                            if wait_time > 0:
                                await asyncio.sleep(wait_time)

                            last_send_time = (
                                asyncio.get_running_loop().time()
                            )

                            await context.bot.send_message(
                                chat_id=user_id,
                                text=text,
                                entities=entities,
                            )

                        success += 1
                        break

                    except RetryAfter as e:
                        await asyncio.sleep(e.retry_after)

                    except Exception:
                        failed += 1
                        break

            finally:
                queue.task_done()

    workers = [
        asyncio.create_task(worker())
        for _ in range(5)
    ]

    await queue.join()

    for task in workers:
        task.cancel()

    await asyncio.gather(
        *workers,
        return_exceptions=True,
    )

    await message.reply_text(
        f"✅ Broadcast selesai\n"
        f"Berhasil: {success}\n"
        f"Gagal: {failed}"
    )


async def setthumbmain(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    msg = update.message

    if not msg or not msg.photo:
        await msg.reply_text(
            "Kirim foto dengan command /setthumbmain"
        )
        return

    data = load_data()
    data["thumbnail_main"] = msg.photo[-1].file_id
    save_data(data)

    await msg.reply_text(
        "✅ Thumbnail MAIN berhasil disimpan!"
    )


async def setthumbpap(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    msg = update.message

    if not msg or not msg.photo:
        await msg.reply_text(
            "Kirim foto dengan command /setthumbpap"
        )
        return

    data = load_data()
    data["thumbnail_pap"] = msg.photo[-1].file_id
    save_data(data)

    await msg.reply_text(
        "✅ Thumbnail PAP berhasil disimpan!"
    )


async def prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    msg = update.message
    data = load_data()
    key = str(uuid4())[:8]
    args = context.args

    if not args:
        await msg.reply_text("Gunakan: /prem teks [coin]")
        return

    if args[-1].isdigit():
        coin_required = int(args[-1])
        text_content = " ".join(args[:-1])
    else:
        coin_required = DEFAULT_COIN_PREM
        text_content = " ".join(args)

    if msg.text:
        data["content"][key] = {
            "type": "text",
            "content": text_content,
            "premium": True,
            "coin_required": coin_required,
        }

    elif msg.photo:
        data["content"][key] = {
            "type": "photo",
            "content": msg.photo[-1].file_id,
            "caption": msg.caption or "",
            "raw_caption": msg.caption or "",
            "premium": True,
            "coin_required": coin_required,
        }

    elif msg.video:
        data["content"][key] = {
            "type": "video",
            "content": msg.video.file_id,
            "caption": msg.caption or "",
            "raw_caption": msg.caption or "",
            "premium": True,
            "coin_required": coin_required,
        }

    else:
        await msg.reply_text("Format tidak didukung.")
        return

    save_data(data)

    bot_username = (
        BOT_USERNAME
        or (await context.bot.get_me()).username
    )

    link = f"https://t.me/{bot_username}?start={key}"

    caption = msg.text or msg.caption or ""

    if caption.startswith("#"):
        title = caption[1:].strip()
    else:
        title = caption.strip()

    title = html_escape(title)

    await msg.reply_text(
        f"{title}\n{link}" if title else link
    )


async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "Format: /gift userid jumlah/premium"
        )
        return

    target = context.args[0]
    value = context.args[1]
    data = load_data()

    if value.lower() == "premium":
        if target not in data["premium_users"]:
            data["premium_users"].append(target)
            save_data(data)

        await update.message.reply_text(
            f"Berhasil Memberi Status Premium Kepada {target}"
        )
        return

    try:
        jumlah = int(value)
        if jumlah < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Jumlah coin harus berupa angka >= 0."
        )
        return

    add_coin(data, target, jumlah)

    await update.message.reply_text(
        f"Berhasil Memberi {jumlah} Coin kepada {target}"
    )


async def minus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "Format: /minus userid jumlah"
        )
        return

    target = context.args[0]

    try:
        jumlah = int(context.args[1])
        if jumlah < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Jumlah coin harus berupa angka >= 0."
        )
        return

    data = load_data()
    data["coin"][str(target)] = max(
        0,
        get_coin(data, target) - jumlah,
    )
    save_data(data)

    await update.message.reply_text(
        f"Coin {target} Telah Dikurangi {jumlah} Coin"
    )


async def unprem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Format: /unprem userid"
        )
        return

    target = context.args[0]
    data = load_data()

    if target in data.get("premium_users", []):
        data["premium_users"].remove(target)
        save_data(data)

        await update.message.reply_text(
            f"Anda Telah Menghapus Status Premium {target}"
        )
    else:
        await update.message.reply_text(
            f"{target} tidak memiliki status premium."
        )


# ================= STATS =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        return

    data = load_data()

    total_users = len(data["users"])
    total_clicks = data.get("clicks", 0)
    total_coin = sum(data.get("coin", {}).values())
    total_premium = len(data.get("premium_users", []))

    referral_counts = data.get("referral_count", {})

    referral_text = "\n".join(
        f"{uid}: {max(count, 1)} referral"
        for uid, count in referral_counts.items()
    ) or "Belum ada referral"

    await update.message.reply_text(
        f"📊 Stats Bot:\n"
        f"Total Users: {total_users}\n"
        f"Total Clicks: {total_clicks}\n"
        f"Total Coin: {total_coin}\n"
        f"Total Premium: {total_premium}\n\n"
        f"📌 Referral Counts:\n{referral_text}"
    )


# ================= NORMAL CONTENT =================

async def normal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != "private":
        return

    user = update.effective_user

    if user.id != OWNER_ID and user.id not in POST_ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "KOLEKSI VIRAL",
                    url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                )
            ]
        ])

        await update.message.reply_text(
            "Klik tombol di bawah untuk membuka koleksi lain:",
            reply_markup=keyboard,
        )
        return

    data = load_data()
    msg = update.message
    key = str(uuid4())[:8]

    if msg.text:
        data["content"][key] = {
            "type": "text",
            "content": msg.text,
        }

    elif msg.photo:
        data["content"][key] = {
            "type": "photo",
            "content": msg.photo[-1].file_id,
            "raw_caption": msg.caption or "",
        }

    elif msg.video:
        data["content"][key] = {
            "type": "video",
            "content": msg.video.file_id,
            "raw_caption": msg.caption or "",
        }

    else:
        await msg.reply_text("Format tidak didukung.")
        return

    save_data(data)

    bot_username = (
        BOT_USERNAME
        or (await context.bot.get_me()).username
    )

    link = f"https://t.me/{bot_username}?start={key}"

    caption = msg.text or msg.caption or ""

    if caption.startswith("#"):
        title = caption[1:].strip()
    else:
        title = caption.strip()

    title = html_escape(title)
    caption_text = f"{title}\n{link}" if title else link

    pending_id = str(uuid4())[:8]

    PENDING_POST[pending_id] = {
        "text": caption_text,
        "link": link,
        "key": key,
        "title": title,
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 POST KE CHANNEL",
                callback_data=f"postmain_{pending_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔥 POST KE CH PAP",
                callback_data=f"postpap_{pending_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 LINK SAJA",
                callback_data=f"linkonly_{pending_id}",
            )
        ],
    ])

    await msg.reply_text(
        caption_text,
        reply_markup=keyboard,
    )


# ================= STARTUP =================

async def post_init(application):
    global BOT_USERNAME

    me = await application.bot.get_me()
    BOT_USERNAME = me.username

    print(f"Bot @{BOT_USERNAME} berhasil terhubung.")


def main():
    if not TOKEN or TOKEN == "token botfather":
        raise RuntimeError(
            "BOT_TOKEN belum diset. "
            "Buka Replit Secrets dan tambahkan BOT_TOKEN."
        )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("prem", prem))
    app.add_handler(CommandHandler("gift", gift))
    app.add_handler(CommandHandler("minus", minus))
    app.add_handler(CommandHandler("unprem", unprem))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(
        CommandHandler("broadcast", broadcast, block=False)
    )

    app.add_handler(CallbackQueryHandler(callback))

    app.add_handler(
        MessageHandler(
            filters.PHOTO & filters.CaptionRegex(r"^/setthumbmain"),
            setthumbmain,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO & filters.CaptionRegex(r"^/setthumbpap"),
            setthumbpap,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO | filters.VIDEO,
            normal,
        )
    )

    print("Bot polling dimulai...")

    app.run_polling(
        drop_pending_updates=True,
        poll_interval=0.1,
        timeout=30,
    )


if __name__ == "__main__":
    main()
