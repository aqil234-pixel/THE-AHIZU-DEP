import os
import logging
import asyncio
import random
import socket
import time
import psutil
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import MessageHandler, filters
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR, 
    filename='bot_errors.log', 
    filemode='a'
)

# --- KONFIGURASI UTAMA ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
ADMIN_WA = os.getenv("ADMIN_WA")
GROQ_API_KEY = os.getenv("API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NAMA_FOLDER_FOTO = "assets" 
PATH_FOTO_LENGKAP = os.path.join(BASE_DIR, NAMA_FOLDER_FOTO)

# --- 2. DATABASE SEMENTARA (Memory) ---
DATABASE_ORDER = {}

CHOOSING_FISH, ASKING_NAME, ASKING_ADDRESS, ASKING_QUANTITY, CHOOSING_PAYMENT = range(5)

KATALOG = {
    "betta": {
        "nama": "Ikan Cupang Nemo", 
        "harga": 50000, 
        "foto": "cupang.jpg", 
        "deskripsi": "Ikan cupang hias dengan corak warna-warni mirip ikan badut (Nemo). Lincah, sehat, dan warna tembus!" # <-- Baris baru
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

# --- 3. ALUR CLIENT (USER) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id 
    
    teks = (
        "Selamat datang di *dreamlandfish.myd* 🐟\n"
        "Pusat ikan hias terbaik impian Anda!\n\n"
        "💡 _Tanya seputar ikan? Langsung ketik aja di chat, Admin AI kami siap bantu!_"
    )
    
    keyboard = [
        [InlineKeyboardButton("🖼️ Lihat Katalog", callback_data='lihat_katalog')],
        [InlineKeyboardButton("🛒 Pesan Ikan", callback_data='lihat_katalog')],
        [InlineKeyboardButton("🤖 Cara Chat dengan AI", callback_data='bantuan_ai')] 
    ]
    
    # --- LOGIKA KHUSUS ADMIN ---
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("🐞 CEK BUG (Admin Only)", callback_data="admin_cek_bug")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # --- LOGIKA MUNCULIN GAMBAR LOGO ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(BASE_DIR, "assets", "logo_dream.jpg")

    # Eksekusi pengiriman pesan (Bisa kirim Logo + Teks sekaligus)
    if update.message:
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=teks, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(teks, reply_markup=reply_markup, parse_mode='Markdown')
            
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        # Hapus pesan sebelumnya agar chat bersih
        try: await query.delete_message()
        except: pass
            
        if os.path.exists(logo_path):
             with open(logo_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo, caption=teks, reply_markup=reply_markup, parse_mode='Markdown')
        else:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=teks, reply_markup=reply_markup, parse_mode='Markdown')

    return ConversationHandler.END

async def bantuan_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Ini bakal ngeluarin pop-up buat ngasih tau cara pakainya
    await query.answer(text="💡 CARA PENGGUNAAN:\n\nNggak perlu klik menu apa-apa, Kak! Langsung aja ketik pertanyaan Kakak (misal: 'Bang ikan cupang makanannya apa?') lalu kirim. Nanti AI kami bakal otomatis balas! 🤖✨", show_alert=True)

async def menu_katalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Hapus pesan menu sebelumnya biar ga nyepam
    try: await query.delete_message()
    except: pass
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="📋 **KATALOG KAMI:**", parse_mode='Markdown')
    
    for k, v in KATALOG.items():
        foto_path = os.path.join(PATH_FOTO_LENGKAP, v['foto'])
        teks_ikan = f"🔹 **{v['nama']}**\n💰 Harga: Rp{v['harga']:,}"
        
        # Tombol di bawah gambar
        keyboard = [
            [InlineKeyboardButton("📖 Lihat Deskripsi", callback_data=f"desc_{k}")],
            [InlineKeyboardButton(f"🛒 Pesan {v['nama']}", callback_data=f"beli_{k}")],
        ]
        
        try:
            with open(foto_path, 'rb') as f:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=teks_ikan, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except FileNotFoundError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{teks_ikan}\n*(Gambar tdk ditemukan)*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
    return CHOOSING_FISH

async def tampilkan_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split("_")[1] 
    
    if key in KATALOG:
        ikan = KATALOG[key]
        deskripsi = ikan.get("deskripsi", "Deskripsi untuk ikan ini belum tersedia.")
        
       
        teks_popup = (
            f"🐟 {ikan['nama'].upper()}\n"
            f"💰 Harga: Rp{ikan['harga']:,}\n"
            f"\n"
            f"📝 KETERANGAN:\n"
            f"{deskripsi}"
        )
        await query.answer(text=teks_popup, show_alert=True)
    else:
        await query.answer(text="⚠️ Deskripsi tidak ditemukan.", show_alert=True)

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

# --- FLOW PEMESANAN ---
async def minta_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("beli_", "")
    context.user_data['ikan_dipilih'] = KATALOG[key]
    
    await query.message.reply_text(f"📝 Anda akan memesan **{KATALOG[key]['nama']}**.\n\nSilakan ketik Nama Lengkap Anda:", parse_mode='Markdown')
    return ASKING_NAME

async def minta_alamat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nama_user'] = update.message.text
    await update.message.reply_text("📍 Silakan ketik Alamat Lengkap pengiriman Anda:", parse_mode='Markdown')
    return ASKING_ADDRESS

async def minta_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Simpan alamat dari input sebelumnya
    context.user_data['alamat_user'] = update.message.text
    
    # Bikin tombol pilihan jumlah (misal 1 sampai 5)
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="qty_1"),
            InlineKeyboardButton("2", callback_data="qty_2"),
            InlineKeyboardButton("3", callback_data="qty_3")
        ],
        [
            InlineKeyboardButton("4", callback_data="qty_4"),
            InlineKeyboardButton("5", callback_data="qty_5"),
            InlineKeyboardButton("10", callback_data="qty_10")
        ]
    ]
    
    teks = (
        "🔢 **Pilih Jumlah Pesanan:**\n\n"
        "_( SILAHKAN BUAT PESANAN )_"
    )
    
    await update.message.reply_text(teks, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ASKING_QUANTITY

async def minta_pembayaran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- CEK APAKAH USER KLIK TOMBOL ATAU NGETIK MANUAL ---
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        # Hapus pesan menu jumlah biar rapi dan nggak nyangkut
        try:
            await query.delete_message()
        except:
            pass
            
        jumlah = int(query.data.split("_")[1]) 
    else:
        # Kalau user ngetik manual
        if not update.message.text.isdigit():
            await update.message.reply_text("⚠️ Masukkan angka yang valid!")
            return ASKING_QUANTITY
        jumlah = int(update.message.text)

    # --- SIMPAN DAN HITUNG ---
    context.user_data['qty'] = jumlah
    total_harga = context.user_data['ikan_dipilih']['harga'] * context.user_data['qty']
    context.user_data['total_harga'] = total_harga
    
    teks_bayar = (
        f"💳 **PEMBAYARAN**\n"
         f"━━━━━━━━━━━━━\n"
        f"Total Tagihan: **Rp{total_harga:,}**\n"
         f"━━━━━━━━━━━━━\n"
        f"Silakan transfer ke:\n"
        f"🏦 BCA: `123456789` (A/N Dreamland)\n"
        f"🏦 Mandiri: `123456789` (A/N Dreamland)\n"
        f"📱 Atau scan QRIS di bawah ini.\n"
        f"━━━━━━━━━━━━━"
    )
    
    keyboard = [[InlineKeyboardButton("✅ Selesai Transfer & Buat Nota", callback_data='buat_nota')]]
    
    qris_path = os.path.join(PATH_FOTO_LENGKAP, "qris.jpg")
    try:
        with open(qris_path, 'rb') as f:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=teks_bayar, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=teks_bayar, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    return CHOOSING_PAYMENT
    
async def buat_nota_akhir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Bikin Order ID unik
    order_id = f"ORD-{random.randint(1000, 9999)}"
    
    # Simpan ke Database Memory
    DATABASE_ORDER[order_id] = {
        'nama': context.user_data['nama_user'],
        'alamat': context.user_data['alamat_user'],
        'ikan': context.user_data['ikan_dipilih']['nama'],
        'qty': context.user_data['qty'],
        'total': context.user_data['total_harga'],
        'status_bayar': "⏳ Menunggu Verifikasi",
        'status_barang': "📦 Sedang Diproses"
    }
    
    # Render Nota
    nota = (
        f"🧾 **NOTA PEMESANAN ({order_id})**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Nama: {DATABASE_ORDER[order_id]['nama']}\n"
        f"📍 Alamat: {DATABASE_ORDER[order_id]['alamat']}\n"
        f"🐟 Pesanan: {DATABASE_ORDER[order_id]['ikan']}\n"
        f"🔢 Jumlah: {DATABASE_ORDER[order_id]['qty']} ekor\n"
        f"💰 Total: Rp{DATABASE_ORDER[order_id]['total']:,}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 Status Bayar: {DATABASE_ORDER[order_id]['status_bayar']}\n"
        f"🚚 Status Barang: {DATABASE_ORDER[order_id]['status_barang']}\n\n"
        f"✨ _Terima kasih telah berbelanja di DreamlandFish!_\n"
        
    )
    
    keyboard_nota = [
        [InlineKeyboardButton("🔍 Cek Status Terkini", callback_data=f"cekstatus_{order_id}")],
        [InlineKeyboardButton("💬 Hubungi Admin", url=f"https://wa.me/{ADMIN_WA}")]
    ]
    
    # Hapus pesan foto QRIS sebelumnya
    await query.delete_message()
    # Kirim pesan teks nota yang baru
    await context.bot.send_message(chat_id=update.effective_chat.id, text=nota, reply_markup=InlineKeyboardMarkup(keyboard_nota), parse_mode='Markdown')
    
    # --- NOTIFIKASI ADMIN (DENGAN TOMBOL UPDATE STATUS) ---
    admin_notif = f"🚨 **ORDER BARU MASUK!** 🚨\nID: {order_id}\nNama: {DATABASE_ORDER[order_id]['nama']}\nTotal: Rp{DATABASE_ORDER[order_id]['total']:,}"
    admin_keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi Lunas", callback_data=f"setlunas_{order_id}")],
        [InlineKeyboardButton("🚚 Kirim Barang", callback_data=f"setkirim_{order_id}")]
    ]
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notif, reply_markup=InlineKeyboardMarkup(admin_keyboard))
    except: pass
    
    context.user_data.clear()
    return ConversationHandler.END

# --- 4. CALLBACK GLOBAL (TIDAK MASUK CONVERSATION) ---

async def cek_status_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.split("_")[1]
    
    if order_id in DATABASE_ORDER:
        data = DATABASE_ORDER[order_id]
        status_msg = (
            f"🔍 **STATUS UPDATE ({order_id})**\n"
             f"━━━━━━━━━━━━━\n"
            f"💳 PEMBAYARAN: {data['status_bayar']}\n"
            f"🚚 PENGIRIMAN: {data['status_barang']}\n"
             f"━━━━━━━━━━━━━\n"
        )
        await query.message.reply_text(status_msg, parse_mode='Markdown')
    else:
        await query.message.reply_text("❌ Pesanan tidak ditemukan.")

async def admin_update_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Hanya admin yang bisa klik tombol ini
    if update.effective_user.id != ADMIN_ID:
        return
        
    action, order_id = query.data.split("_")
    
    if order_id in DATABASE_ORDER:
        if action == "setlunas":
            DATABASE_ORDER[order_id]['status_bayar'] = "✅ LUNAS"
            await query.edit_message_text(f"✅ {order_id} telah di-set LUNAS.")
        elif action == "setkirim":
            DATABASE_ORDER[order_id]['status_barang'] = "🚀 SUDAH DIKIRIM"
            await query.edit_message_text(f"🚀 {order_id} telah di-set DIKIRIM.")


async def batal_ke_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def check_connectivity(host="8.8.8.8", port=53, timeout=3):
    """Cek apakah bot bisa 'melihat' internet luar"""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return "✅ ONLINE"
    except Exception:
        return "❌ OFFLINE"

async def get_bot_diagnostics():
    """Bikin teks laporan ala terminal VS Code"""
    start_time = time.time()
    
    # Cek Jaringan
    tg_status = check_connectivity("api.telegram.org", 443)
    google_status = check_connectivity("google.com", 80)
    
    # Hitung Latency (ping sederhana)
    latency = round((time.time() - start_time) * 1000, 2)
    
    # Cek Kapasitas Log
    log_size = "0 KB"
    if os.path.exists('bot_errors.log'):
        log_size = f"{os.path.getsize('bot_errors.log') / 1024:.2f} KB"

    # Template laporan ala Terminal
    report = (
        "<code>[DREAMLAND DIAGNOSTICS]</code>\n"
        "<code>------------------------</code>\n"
        f"🌐 <b>Telegram API:</b> <code>{tg_status}</code>\n"
        f"🌍 <b>Google DNS:</b>   <code>{google_status}</code>\n"
        f"⚡ <b>Latency:</b>      <code>{latency}ms</code>\n"
        f"📁 <b>Log Size:</b>     <code>{log_size}</code>\n"
        f"🤖 <b>AI Status:</b>     <code>{'READY' if GROQ_API_KEY else 'MISSING'}</code>\n"
        "<code>------------------------</code>\n"
        f"⏰ <b>Server Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>"
    )
    return report

async def admin_cek_bug_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if str(update.effective_user.id) != str(ADMIN_ID):
        await query.message.reply_text("⛔ Restricted Area!")
        return

    # 1. Kirim Laporan Diagnostik (Teks ala Terminal)
    status_report = await get_bot_diagnostics()
    await query.message.reply_text(status_report, parse_mode="HTML")

    # 2. Kirim File Log (Jika ada error)
    log_file = 'bot_errors.log'
    if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
        with open(log_file, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                caption="📄 <b>Full Error Log</b>",
                parse_mode="HTML"
            )
    else:
        await query.message.reply_text("✨ <b>Terminal Clean:</b> No errors detected.")
# --- 5. MAIN ROUTING ---

def main():
    if not TOKEN:
        print("❌ TOKEN KOSONG!")
        return

    app = Application.builder().token(TOKEN).build()
    
    # Handlers Perintah & Tombol
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_cek_bug_callback, pattern='^admin_cek_bug$'))
    app.add_handler(CallbackQueryHandler(menu_katalog, pattern='^lihat_katalog$'))
    app.add_handler(CallbackQueryHandler(tampilkan_deskripsi, pattern='^desc_')) # Harus ada ini!
    app.add_handler(CallbackQueryHandler(cek_status_order, pattern='^cekstatus_'))
    app.add_handler(CallbackQueryHandler(admin_update_status, pattern='^(setlunas_|setkirim_)'))
    app.add_handler(CallbackQueryHandler(bantuan_ai, pattern='^bantuan_ai$'))

    # Alur Pesanan (Conversation)
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(minta_nama, pattern='^beli_')],
        states={
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, minta_alamat)],
            ASKING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, minta_jumlah)],
            ASKING_QUANTITY: [
                CallbackQueryHandler(minta_pembayaran, pattern='^qty_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, minta_pembayaran)
            ],
            CHOOSING_PAYMENT: [CallbackQueryHandler(buat_nota_akhir, pattern='^buat_nota$')]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    app.add_handler(conv_handler)

    # Chat AI (WAJIB PALING BAWAH)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_ai))

    print("🚀 Bot Dreamland RUNNING...")
    app.run_polling()
    
if __name__ == '__main__':
    main()