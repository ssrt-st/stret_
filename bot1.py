import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import yt_dlp

# ==================== الإعدادات الأساسية ====================
BOT_TOKEN = ""
ADMIN_ID =  # ضع آيدي حسابك في تليجرام هنا
CHANNEL_USERNAME = "@https://t.me/sofe_1m"  # معرف قناتك للتحقق من الاشتراك الإجباري

# ==================== قاعدة البيانات ====================
users = {}
ref_clicks = {}
testing_users = set()  # مجموعة لحفظ حالة الأدمن إذا كان في وضع التجربة
contest_data = {
    "active": False,
    "end_time": None
}

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "points": 0,
            "referred_by": None,
            "referrals_count": 0,
            "last_daily": None,
            "history": []
        }
    return users[user_id]

# ==================== التحقق من الاشتراك ====================
async def check_subscription(user_id, context):
    if user_id in testing_users:
        return True  # التجاوز الفوري أثناء وضع التجربة
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@ضع_معرف_قناتك_هنا":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return True

async def send_sub_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_channel = CHANNEL_USERNAME.replace('@', '')
    keyboard = [
        [InlineKeyboardButton("📢 اشترك في القناة أولاً", url=f"https://t.me/{clean_channel}")],
        [InlineKeyboardButton("✅ تحقق من الاشتراك الآن", callback_data="check_sub")]
    ]
    text = "⚠️ **عذراً عزيزي!**\nيجب عليك الاشتراك في قناة البوت أولاً لاستخدام الخدمات."

    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== الأوامر واللوحات ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    user = get_user(user_id)

    if not await check_subscription(user_id, context):
        await send_sub_request(update, context)
        return

    if args and user["referred_by"] is None:
        try:
            referrer = int(args[0])
            if referrer != user_id and referrer in users:
                user["referred_by"] = referrer
                users[referrer]["points"] += 1
                users[referrer]["referrals_count"] += 1
                users[referrer]["history"].append("🎉 +1 نقطة (إحالة مستخدم جديد)")

                if contest_data["active"]:
                    ref_clicks[referrer] = ref_clicks.get(referrer, 0) + 1

                await context.bot.send_message(
                    chat_id=referrer,
                    text=f"🎉 دخل شخص جديد عبر رابطك! حصلت على 1 نقطة.\nمجموع نقاطك: {users[referrer]['points']}"
                )
        except ValueError:
            pass

    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total_users_count = len(users)

    keyboard = [
        [InlineKeyboardButton("📥 تنزيل فيديو", callback_data="dl_info")],
        [InlineKeyboardButton("💰 جمع النقاط (رابطك)", callback_data="get_link"), InlineKeyboardButton("📊 رصيدي", callback_data="my_points")],
        [InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily_bonus"), InlineKeyboardButton("💳 شحن نقاط", callback_data="buy_points")],
        [InlineKeyboardButton("🚀 عروض ترشيق تيك توك", callback_data="boost_offers")],
        [InlineKeyboardButton("📜 سجل المعاملات", callback_data="history"), InlineKeyboardButton("🏆 المسابقة الحالية", callback_data="contest_info")]
    ]

    # إظهار زر لوحة الأدمن فقط إذا كان الأدمن وليس في "وضع التجربة"
    if user_id == ADMIN_ID and user_id not in testing_users:
        keyboard.append([InlineKeyboardButton("👑 لوحة الأدمن (مخفية)", callback_data="admin_panel")])
    elif user_id == ADMIN_ID and user_id in testing_users:
        keyboard.append([InlineKeyboardButton("🔙 الخروج من وضع التجربة والعودة للادارة", callback_data="exit_test_mode")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    status_text = " (وضع التجربة)" if user_id in testing_users else ""
    msg_text = (
        f"أهلاً بك في بوت التنزيل والترشيق الشامل! 👋{status_text}\n\n"
        f"👥 **عدد مستخدمي البوت الحالي:** `{total_users_count}` مستخدم\n"
        f"اختر من القائمة أدناه:"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    user = get_user(user_id)

    if data == "check_sub":
        if await check_subscription(user_id, context):
            await query.message.reply_text("✅ تم التحقق بنجاح! تم تفعيل البوت لك الآن.")
            await show_main_menu(update, context)
        else:
            await query.message.reply_text("❌ لم تشترك في القناة بعد! اشترك ثم اضغط مجدداً.")
        return

    if not await check_subscription(user_id, context):
        await send_sub_request(update, context)
        return

    if data == "dl_info":
        await query.message.reply_text("أرسل رابط الفيديو الآن بأعلى جودة ممتازة وسيرة يتم تنزيله فوراً.")

    elif data == "get_link":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await query.message.reply_text(f"شارِك هذا الرابط مع أصدقائك للحصول على 1 نقطة لكل شخص ينضم:\n\n`{ref_link}`", parse_mode="Markdown")

    elif data == "my_points":
        await query.message.reply_text(f"💳 عدد نقاطك الحالي: **{user['points']}** نقطة.", parse_mode="Markdown")

    elif data == "daily_bonus":
        now = datetime.now()
        last = user["last_daily"]
        if last is None or (now - last) >= timedelta(days=1):
            user["points"] += 1
            user["last_daily"] = now
            user["history"].append("🎁 +1 نقطة (مكافأة يومية)")
            await query.message.reply_text("🎉 حصلت على 1 نقطة مجانية كمكافأة يومية!")
        else:
            remaining = timedelta(days=1) - (now - last)
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await query.message.reply_text(f"⏳ حصلت على المكافأة اليومية بالفعل! عد بعد {hours} ساعة و {minutes} دقيقة.")

    elif data == "buy_points":
        msg = f"💳 **شحن النقاط المباشر:**\n\nارسل الكرت أو إثبات التحويل للمدير.\n\n🆔 الآيدي الخاص بك: `{user_id}`"
        keyboard = [[InlineKeyboardButton("📩 تواصل لشراء النقاط", url=f"tg://user?id={ADMIN_ID}")]]
        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "boost_offers":
        msg = (
            "🚀 **قائمة عروض ترشيق تيك توك:**\n\n"
            "📌 **العرض 1 (10 نقاط):** 5,000 مشاهدة + 50 لايك\n"
            "📌 **العرض 2 (20 نقطة):** 11,000 مشاهدة + 110 لايك\n"
            "📌 **العرض 3 (30 نقطة):** 17,000 مشاهدة + 500 لايك\n\n"
            f"💰 رصيدك الحالي: **{user['points']}** نقطة."
        )
        keyboard = [
            [InlineKeyboardButton("طلب العرض 1 (10 نقاط)", callback_data="req_offer_10")],
            [InlineKeyboardButton("طلب العرض 2 (20 نقطة)", callback_data="req_offer_20")],
            [InlineKeyboardButton("طلب العرض 3 (30 نقطة)", callback_data="req_offer_30")]
        ]
        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("req_offer_"):
        cost = int(data.split("_")[2])
        if user["points"] < cost:
            await query.message.reply_text(f"❌ رصيدك غير كافٍ! تحتاج إلى {cost} نقطة.")
            return

        admin_kbd = [
            [InlineKeyboardButton(f"🗑️ خصم وحذف {cost} نقاط من المستخدم", callback_data=f"deduct_{user_id}_{cost}")],
            [InlineKeyboardButton("💬 تواصل مع المستخدم", url=f"tg://user?id={user_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📥 **طلب ترشيق جديد وصلك!**\n\n"
                f"👤 آيدي المستخدم: `{user_id}`\n"
                f"🎯 العرض المطلوب: {cost} نقاط\n"
                f"💰 رصيده الحالي: {user['points']} نقطة"
            ),
            reply_markup=InlineKeyboardMarkup(admin_kbd),
            parse_mode="Markdown"
        )

        user_kbd = [[InlineKeyboardButton("💬 اضغط هنا لمراسلة المدير وإرسال الرابط", url=f"tg://user?id={ADMIN_ID}")]]
        await query.message.reply_text(
            f"✅ تم تسجيل طلبك! اضغط على الزر أدناه لمراسلة المدير وإرسال رابط مقطعك للتنفيذ.",
            reply_markup=InlineKeyboardMarkup(user_kbd)
        )

    elif data.startswith("deduct_") and user_id == ADMIN_ID:
        _, target_id, cost = data.split("_")
        target_id, cost = int(target_id), int(cost)
        t_user = get_user(target_id)

        if t_user["points"] >= cost:
            t_user["points"] -= cost
            t_user["history"].append(f"🔻 -{cost} نقطة (طلب ترشيق)")
            await query.message.edit_text(
                f"✅ **تم خصم وحذف {cost} نقطة بنجاح!**\n\n"
                f"👤 المستخدم: `{target_id}`\n"
                f"💳 رصيده المتبقي الآن: {t_user['points']} نقطة",
                parse_mode="Markdown"
            )
            await context.bot.send_message(chat_id=target_id, text=f"🎉 تم تنفيذ طلبك وخصم {cost} نقطة من رصيدك!")
        else:
            await query.message.edit_text("❌ النقاط غير كافية لدى المستخدم للخصم.")

    elif data == "history":
        hist = user["history"]
        if not hist:
            await query.message.reply_text("📜 ليس لديك أي سجل معاملات بعد.")
        else:
            text = "📜 **سجل المعاملات الخاص بك:**\n\n" + "\n".join(hist[-10:])
            await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "contest_info":
        if contest_data["active"] and contest_data["end_time"] > datetime.now():
            remaining = contest_data["end_time"] - datetime.now()
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await query.message.reply_text(
                f"🏆 **المسابقة جارية الآن!**\n\n"
                f"🎁 الجائزة: 10k مشاهدة أو 1k لايك تيك توك لأكثر شخص يدعو مستخدمين.\n"
                f"⏳ الوقت المتبقي: {hours} ساعة و {minutes} دقيقة."
            )
        else:
            await query.message.reply_text("لا توجد مسابقة شغالة حالياً.")

    # ==================== لوحة الأدمن والتحكم بالوضع ====================
    elif data == "admin_panel" and user_id == ADMIN_ID:
        admin_keyboard = [
            [InlineKeyboardButton("🧪 وضع التجربة (كمستخدم + 100k نقطة)", callback_data="enter_test_mode")],
            [InlineKeyboardButton("🏁 بدء مسابقة (24 ساعة)", callback_data="admin_start_contest")],
            [InlineKeyboardButton("🛑 إيقاف المسابقة فوراً", callback_data="admin_stop_contest")],
            [InlineKeyboardButton("➕ تعديل نقاط مستخدم", callback_data="admin_points_info")]
        ]
        await query.message.reply_text("⚙️ **لوحة التحكم الخاصة بالمدير:**", reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="Markdown")

    elif data == "enter_test_mode" and user_id == ADMIN_ID:
        testing_users.add(user_id)
        user["points"] = 100000
        user["history"].append("🧪 +100,000 نقطة (دخول وضع التجربة)")
        await query.message.reply_text("🧪 **تم تفعيل وضع التجربة كمستخدم بنجاح!**\nأُضيفت لحسابك 100,000 نقطة واختفت لوحة المدير. يمكنك الآن اختبار البوت كمستخدم عادي.")
        await show_main_menu(update, context)

    elif data == "exit_test_mode" and user_id == ADMIN_ID:
        testing_users.remove(user_id)
        await query.message.reply_text("🔙 **تم الخروج من وضع التجربة وتفعيل لوحة الأدمن مجدداً!**")
        await show_main_menu(update, context)

    elif data == "admin_start_contest" and user_id == ADMIN_ID:
        contest_data["active"] = True
        contest_data["end_time"] = datetime.now() + timedelta(hours=24)
        ref_clicks.clear()
        await query.message.reply_text("✅ تم بدء مسابقة 24 ساعة بنجاح!")

    elif data == "admin_stop_contest" and user_id == ADMIN_ID:
        contest_data["active"] = False
        contest_data["end_time"] = None
        await query.message.reply_text("🛑 تم إيقاف المسابقة الحالية بنجاح!")

    elif data == "admin_points_info" and user_id == ADMIN_ID:
        await query.message.reply_text("لخصم أو إضافة نقاط، استخدم الأمر:\n`/setpoints ID_المستخدم عدد_النقاط`", parse_mode="Markdown")

# ==================== أمر تخصيص النقاط للمدير ====================
async def set_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        target_id = int(context.args[0])
        new_pts = int(context.args[1])
        u = get_user(target_id)
        u["points"] = new_pts
        await update.message.reply_text(f"✅ تم تعديل نقاط المستخدم {target_id} إلى {new_pts} نقطة.")
    except Exception:
        await update.message.reply_text("❌ الاستخدام الصحيح:\n`/setpoints ID عدد_النقاط`", parse_mode="Markdown")

# ==================== معالج التنزيل بأعلى وأفضل جودة معالجة ====================
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_subscription(user_id, context):
        await send_sub_request(update, context)
        return

    url = update.message.text
    if not (url.startswith("http://") or url.startswith("https://")):
        return

    status_msg = await update.message.reply_text("⚡ جاري التنزيل والمعالجة بأعلى جودة ممكنة (Full HD/4K)، يرجى الانتظار...")

    # اختيار الجودة القسوى مع حماية الحد الأقصى لتليجرام
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # التأكد من عدم تجاوز حد 50 ميغابايت المسموح في تليجرام
        if os.path.getsize(filename) > 50 * 1024 * 1024:
            await status_msg.edit_text("⏳ الفيديو حجمه كبير جداً بجودته العالية، جاري تنزيل نسخة خفيفة تتناسب مع تليجرام...")

            # إعادة المحاولة بجودة تتناسب مع حجم 50MB
            ydl_opts_light = {
                'format': 'best[filesize<49M]/bestvideo[filesize<40M]+bestaudio/best',
                'outtmpl': 'downloads/%(id)s_light.%(ext)s',
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_light) as ydl_light:
                info_light = ydl_light.extract_info(url, download=True)
                filename = ydl_light.prepare_filename(info_light)

        await update.message.reply_video(video=open(filename, 'rb'))
        os.remove(filename)
        await status_msg.delete()
    except Exception:
        await status_msg.edit_text("❌ تعذر تنزيل الفيديو. تأكد من أن الرابط صحيح وغير محمي.")

# ==================== التشغيل ====================
if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpoints", set_points))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    print("البوت يعمل الآن بنجاح مع وضع التجربة وأعلى جودة ممكنة...")
    app.run_polling()
