import os
import logging
import asyncio
import random
import socket
import time
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# --- SETUP PATH & ENV ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Konfigurasi Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR, 
    filename='bot_errors.log', 
    filemode='a'
)

# --- KONFIGURASI UTAMA ---
TOKEN = os.getenv("BOT_TOKEN")
# Pastikan ADMIN_ID terbaca sebagai string untuk perbandingan yang aman
ADMIN_ID = os.getenv("ADMIN_ID") 
ADMIN_WA = os.getenv("ADMIN_WA")
GROQ_API_KEY = os.getenv("API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

NAMA_FOLDER_FOTO = "assets" 
PATH_FOTO_LENGKAP = os.path.join(BASE_DIR, NAMA_FOLDER_FOTO)

# --- DATABASE SEMENTARA ---
DATABASE_ORDER = {}
CHOOSING_FISH, ASKING_NAME, ASKING_ADDRESS, ASKING_QUANTITY, CHOOSING_PAYMENT = range(5)

KATALOG = {
    "betta": {
        "nama": "Ikan Cupang Nemo", 
        "harga": 50000, 
        "foto": "cupang.jpg", 
        "deskripsi": "Ikan cupang hias dengan corak warna-warni mirip ikan badut (Nemo). Lincah, sehat, dan warna tembus!"
    },
    "guppy": {
        "nama": "Guppy Albino", 
        "harga": 35000, 
        "foto": "guppy.jpg",
        "deskripsi": "Ikan guppy mata merah (albino) grade A dengan ekor lebar yang indah. Perawatan sangat mudah."
    },
    "arowana": {
        "nama": "Arwana Silver", 
        "harga": 150000, 
        "foto": "arowana.jpg", 
        "deskripsi": "Arwana silver anakan ukuran 10-15cm. Ikan predator eksotis, makan rakus dan lincah."
    },
}

# --- FUNGSI DIAGNOSTIK (ALA VS CODE) ---
def check_connectivity(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return "✅ ONLINE"
    except:
        return "❌ OFFLINE"

async def get_bot_diagnostics():
    start_time = time.time()
    tg_status = check_connectivity("api.telegram.org", 443)
    latency = round((time.time() - start_time) * 1000, 2)
    log_size = f"{os.path.getsize('bot_errors.log') / 1024:.2f} KB" if os.path.exists('bot_errors.log') else "0 KB"
    
    return (
        "<code>[DREAMLAND DIAGNOSTICS]</code>\n"
        "<code>------------------------</code>\n"
        f"🌐 <b>Telegram API:</b> <code>{tg_status}</code>\n"
        f"⚡ <b>Latency:</b>      <code>{latency}ms</code>\n"
        f"📁 <b>Log Size:</b>     <code>{log_size}</code>\n"
        f"🤖 <b>AI Status:</b>     <code>{'READY' if GROQ_API_KEY else 'MISSING'}</code>\n"
        "<code>------------------------</code>"
    )

# --- HANDLER UTAMA ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- FIX BUG: Ambil user_id dulu ---
    user_id = update.effective_user.id 
    
    teks = (
        "Selamat datang di *dreamlandfish.myd* 🐟\n"
        "Pusat ikan hias terbaik impian Anda!\n\n"
        "💡 _Tanya seputar ikan? Langsung ketik aja di chat, Admin AI kami siap bantu!_"
    )
    
    keyboard = [
        [InlineKeyboardButton("🖼️ Lihat Katalog", callback_data='lihat_katalog')],
        [InlineKeyboardButton("🤖 Cara Chat dengan AI", callback_data='bantuan_ai')] 
    ]
    
    # Logika Admin
    if str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("🐞 CEK BUG (Admin Only)", callback_data="admin_cek_bug")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    logo_path = os.path.join(BASE_DIR, "assets", "logo_dream.jpg")

    # Kirim pesan (pake foto kalau ada, teks kalau nggak ada)
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as photo:
            if update.message:
                await update.message.reply_photo(photo=photo, caption=teks, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.callback_query.message.reply_photo(photo=photo, caption=teks, reply_markup=reply_markup, parse_mode='Markdown')
                try: await update.callback_query.message.delete()
                except: pass
    else:
        if update.message:
            await update.message.reply_text(teks, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.callback_query.edit_message_text(teks, reply_markup=reply_markup, parse_mode='Markdown')

    return ConversationHandler.END

async def admin_cek_bug_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if str(update.effective_user.id) != ADMIN_ID:
        await query.message.reply_text("⛔ Restricted Area!")
        return

    report = await get_bot_diagnostics()
    await query.message.reply_text(report, parse_mode="HTML")

    if os.path.exists('bot_errors.log') and os.path.getsize('bot_errors.log') > 0:
        with open('bot_errors.log', 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, caption="📄 Full Log")
    else:
        await query.message.reply_text("✨ Terminal Clean: No errors.")

async def chat_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pesan_user = update.message.text
    
    # 1. Kita rakit daftar produk dari KATALOG biar AI tahu apa yang kita jual
    daftar_produk = ""
    for k, v in KATALOG.items():
        daftar_produk += f"- {v['nama']}: Rp{v['harga']:,} ({v['deskripsi']})\n"

    # 2. Bikin Prompt yang lebih detail dan galak (biar gak bahas hal di luar toko)
    system_prompt = f"""
Kamu adalah 'gammy', asisten admin toko ikan 'Dreamlandfish.myd'. 
Gaya bicara: Gaul, santai, pake bahasa anak muda (pake 'saya/anda' atau 'kak' yang asik), ramah, dan informatif.

TUGAS UTAMA:
1. Menjawab pertanyaan tentang ikan yang ada di katalog kami.
2. Memberikan tips perawatan ikan secara umum.
3. Mengarahkan orang untuk klik tombol 'Lihat Katalog' jika mereka mau beli.

DATA KATALOG KAMI:
{daftar_produk}

ATURAN PENTING:
- JANGAN jawab kalau ditanya hal di luar ikan (politik, agama, teknologi, dll). Bilang aja "Waduh, gue cuma jago urusan ikan nih, kak! Tanya soal ikan aja yuk."
- Kalau ikan yang ditanya GAK ADA di katalog, bilang jujur tapi tawarkan ikan yang mirip.
- Jawabnya singkat-singkat aja, jangan kayak koran.
- Bisa diajak bercanda tapi tetep sopan.
"""
    
    try:
       
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pesan_user}
            ],
            model="llama-3.1-8b-instant",
        )
        
        balasan_ai = chat_completion.choices[0].message.content
        await update.message.reply_text(balasan_ai)
        
    except Exception as e:
        logging.error(f"Error Groq: {e}")
        await update.message.reply_text("Waduh, otak gue lagi nge-lag dikit nih. Coba tanya lagi dong! 😅")


async def menu_katalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    for k, v in KATALOG.items():
        foto_path = os.path.join(PATH_FOTO_LENGKAP, v['foto'])
        teks_ikan = f"🔹 **{v['nama']}**\n💰 Harga: Rp{v['harga']:,}"
        keyboard = [[InlineKeyboardButton("📖 Deskripsi", callback_data=f"desc_{k}")],
                    [InlineKeyboardButton(f"🛒 Pesan {v['nama']}", callback_data=f"beli_{k}")]]
        
        try:
            with open(foto_path, 'rb') as f:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=teks_ikan, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{teks_ikan}\n⚠️ Gambar tidak ditemukan", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CHOOSING_FISH
    
async def tampilkan_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Mengambil ID ikan dari callback data (misal: desc_betta -> betta)
    key = query.data.split("_")[1] 
    
    if key in KATALOG:
        ikan = KATALOG[key]
        deskripsi = ikan.get("deskripsi", "Deskripsi belum tersedia.")
        
        teks_popup = (
            f"🐟 {ikan['nama'].upper()}\n"
            f"💰 Harga: Rp{ikan['harga']:,}\n\n"
            f"📝 KETERANGAN:\n{deskripsi}"
        )
        # show_alert=True agar muncul sebagai pop-up kotak di layar
        await query.answer(text=teks_popup, show_alert=True)
    else:
        await query.answer(text="⚠️ Deskripsi tidak ditemukan.", show_alert=True)

    
# --- MAIN ---
def main():
    if not TOKEN: return print("❌ TOKEN KOSONG!")
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_cek_bug_callback, pattern='^admin_cek_bug$'))
    app.add_handler(CallbackQueryHandler(menu_katalog, pattern='^lihat_katalog$'))
    app.add_handler(CallbackQueryHandler(tampilkan_deskripsi, pattern='^desc_'))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_ai))
    
    print("🚀 Bot Dreamland RUNNING...")
    app.run_polling()

if __name__ == '__main__':
    main()