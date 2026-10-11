# bot_tele_du_doan.py
# Bot Telegram dự đoán XSMN dùng pyTelegramBotAPI
# Yêu cầu: pip install pyTelegramBotAPI requests flask waitress

import os
import logging
import threading
import requests
import random
import telebot
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from flask import Flask
from waitress import serve

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

API_URL = "https://api.383.im/lottery/region/mn.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

TEN_DAI = {
    "tien-giang": "Tiền Giang", "kien-giang": "Kiên Giang",
    "lam-dong": "Đà Lạt", "tp-hcm": "TP.HCM", "binh-phuoc": "Bình Phước",
    "hau-giang": "Hậu Giang", "long-an": "Long An", "vinh-long": "Vĩnh Long",
    "binh-duong": "Bình Dương", "tra-vinh": "Trà Vinh", "tay-ninh": "Tây Ninh",
    "an-giang": "An Giang", "binh-thuan": "Bình Thuận", "can-tho": "Cần Thơ",
    "dong-thap": "Đồng Tháp", "soc-trang": "Sóc Trăng", "bac-lieu": "Bạc Liêu",
    "ben-tre": "Bến Tre", "vung-tau": "Vũng Tàu", "ca-mau": "Cà Mau",
    "dong-nai": "Đồng Nai"
}

LICH_QUAY = {
    0: ["tp-hcm", "dong-thap", "ca-mau", "ben-tre", "vung-tau", "bac-lieu"],
    1: ["ben-tre", "vung-tau", "bac-lieu", "da-lat", "tra-vinh"],
    2: ["dong-nai", "can-tho", "soc-trang", "tay-ninh"],
    3: ["an-giang", "binh-thuan", "tay-ninh", "binh-duong"],
    4: ["binh-duong", "tay-ninh", "vinh-long", "tra-vinh", "binh-thuan"],
    5: ["tp-hcm", "long-an", "binh-phuoc", "hau-giang"],
    6: ["tien-giang", "kien-giang", "lam-dong"]
}

# Khởi tạo bot
bot = telebot.TeleBot(TOKEN)

# Flask app
app_web = Flask(__name__)

@app_web.route("/")
def index():
    return "Bot XSMN đang chạy", 200

@app_web.route("/health")
def health():
    return {"status": "ok"}, 200

# ── CÁC HÀM DỰ ĐOÁN ──

def tai_du_lieu():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error("Lỗi tải dữ liệu: %s", e)
        return None

def tach_theo_dai(data):
    ket_qua = {}
    for item in data.get("items", []):
        ngay = item["d"]
        for p in item.get("ps", []):
            ma = p["i"]
            ket_qua.setdefault(ma, []).append({"ngay": ngay, "giai": p["g"]})
    return ket_qua

def loto_cua_ky(ky):
    ds = []
    for giai, arr in ky["giai"].items():
        for so in arr:
            if len(so) >= 2:
                ds.append(so[-2:])
    return ds

def tt_tan_suat(ds, n=15):
    return [so for so, _ in Counter(ds).most_common(n)]

def tt_gan(ds_theo_ky, n=15):
    tat_ca = [f"{i:02d}" for i in range(100)]
    ket_qua = []
    for so in tat_ca:
        gan = 0
        for ky in ds_theo_ky:
            if so in ky: break
            gan += 1
        ket_qua.append((so, gan))
    ket_qua.sort(key=lambda x: -x[1])
    return [so for so, _ in ket_qua[:n]]

def tt_markov(ds_theo_ky, n=15):
    chuyen = defaultdict(Counter)
    for ky in ds_theo_ky:
        ds = sorted(ky)
        for i in range(len(ds) - 1):
            chuyen[ds[i]][ds[i+1]] += 1
    tong = Counter()
    for so, tiep in chuyen.items():
        for so_t, dem in tiep.items():
            tong[so_t] += dem
    return [so for so, _ in tong.most_common(n)]

def tt_tong_de(ds_db, n=15):
    tong = [int(so[0]) + int(so[1]) for so in ds_db]
    counter = Counter(tong)
    ket_qua = []
    for t, _ in counter.most_common(5):
        for i in range(100):
            so = f"{i:02d}"
            if int(so[0]) + int(so[1]) == t and so not in ket_qua:
                ket_qua.append(so)
    return ket_qua[:n]

def tt_dau_duoi(ds, n=5):
    dau = Counter(); duoi = Counter()
    for so in ds:
        dau[so[0]] += 1; duoi[so[1]] += 1
    ds_dau = [d for d, _ in dau.most_common(n)]
    ds_duoi = [d for d, _ in duoi.most_common(n)]
    ket_qua = []
    for d in ds_dau:
        for u in ds_duoi:
            so = d + u
            if so not in ket_qua: ket_qua.append(so)
    return ket_qua[:15]

def tt_cham(ds_db, n=15):
    cham = Counter()
    for so in ds_db:
        cham[so[0]] += 1; cham[so[1]] += 1
    ds_cham = [c for c, _ in cham.most_common(5)]
    ket_qua = []
    for i in range(100):
        so = f"{i:02d}"
        if so[0] in ds_cham or so[1] in ds_cham: ket_qua.append(so)
    return ket_qua[:n]

def tt_bac_nho(ds_theo_ky, ds_db, n=15):
    ds = []
    for ky in ds_theo_ky: ds.extend(ky)
    phieu = Counter()
    for so in tt_tan_suat(ds, 20): phieu[so] += 3
    for so in tt_gan(ds_theo_ky, 20): phieu[so] += 2
    for so in tt_markov(ds_theo_ky, 20): phieu[so] += 2
    for so in tt_tong_de(ds_db, 15): phieu[so] += 1
    for so in tt_dau_duoi(ds, 5): phieu[so] += 1
    for so in tt_cham(ds_db, 15): phieu[so] += 1
    return [so for so, _ in phieu.most_common(n)]

def du_doan_db(ds_db, n=3):
    top = [so for so, _ in Counter(ds_db).most_common(n)]
    while len(top) < n:
        so = f"{random.randint(0, 99):02d}"
        if so not in top: top.append(so)
    return top

def du_doan_g8(ds_g8, n=3):
    top = [so for so, _ in Counter(ds_g8).most_common(n)]
    while len(top) < n:
        so = f"{random.randint(0, 99):02d}"
        if so not in top: top.append(so)
    return top

def du_doan_xien(ds, n=3):
    counter = Counter(ds)
    ds_chon = list(counter.keys()); trong_so = list(counter.values())
    cap = []
    while len(cap) < n:
        a = random.choices(ds_chon, weights=trong_so, k=1)[0]
        b = random.choices(ds_chon, weights=trong_so, k=1)[0]
        if a != b: cap.append(tuple(sorted([a, b])))
    return list(dict.fromkeys(cap))[:n]

def tao_tin_nhan_ngay_tiep(data):
    ngay_moi = data["items"][0]["d"]
    d = datetime.strptime(ngay_moi, "%Y-%m-%d")
    ngay_tiep = d + timedelta(days=1)
    ngay_hien_thi = ngay_tiep.strftime("%d/%m/%Y")
    ds_dai = LICH_QUAY.get(ngay_tiep.weekday(), [])
    du_lieu_dai = tach_theo_dai(data)

    text = "═" * 32 + "\n"
    text += f"  DỰ ĐOÁN XSMN NGÀY {ngay_hien_thi}\n"
    text += f"  SỐ ĐÀI: {len(ds_dai)}\n"
    text += "═" * 32 + "\n\n"

    for ma in ds_dai:
        ds_ky = du_lieu_dai.get(ma, [])
        if not ds_ky: continue
        ds_theo_ky = [loto_cua_ky(k) for k in ds_ky]
        ds_all = []
        for ky in ds_theo_ky: ds_all.extend(ky)
        ds_db = []; ds_g8 = []
        for k in ds_ky:
            for so in k["giai"].get("db", []):
                if len(so) >= 2: ds_db.append(so[-2:])
            for so in k["giai"].get("g8", []):
                if len(so) >= 2: ds_g8.append(so[-2:])

        ten = TEN_DAI.get(ma, ma)
        db = du_doan_db(ds_db, 3)
        g8 = du_doan_g8(ds_g8, 3)
        loto = tt_bac_nho(ds_theo_ky, ds_db, 6)
        xien = du_doan_xien(ds_all, 3)

        text += f"┌─ ĐÀI: {ten.upper()}\n"
        text += f"│  Ngày: {ngay_hien_thi}\n"
        text += f"├─ 2 số cuối ĐB: {' - '.join(db)}\n"
        text += f"├─ Giải 8:       {' - '.join(g8)}\n"
        text += f"├─ Loto 2 số:    {' - '.join(loto)}\n"
        text += f"└─ Xiên:\n"
        for cap in xien:
            text += f"     {cap[0]} - {cap[1]}\n"
        text += "\n"

    text += "═" * 32 + "\n"
    text += "Chỉ mang tính tham khảo."
    return text

# ── HANDLER TELEBOT ──

@bot.message_handler(commands=['start'])
def handle_start(message):
    text = (
        "Bot dự đoán XSMN.\n"
        "/dudoan - dự đoán ngày tiếp theo\n"
        "/thongke - thống kê loto 30 kỳ\n"
        "/gan - loto gan\n"
        "/xien - gợi ý xiên"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['dudoan'])
def handle_dudoan(message):
    data = tai_du_lieu()
    if not data:
        bot.reply_to(message, "Lỗi tải dữ liệu.")
        return
    tin = tao_tin_nhan_ngay_tiep(data)
    bot.reply_to(message, tin)

@bot.message_handler(commands=['thongke'])
def handle_thongke(message):
    data = tai_du_lieu()
    if not data:
        bot.reply_to(message, "Lỗi tải dữ liệu.")
        return
    ds = []
    for item in data.get("items", []):
        for p in item.get("ps", []):
            for giai, arr in p["g"].items():
                for so in arr:
                    if len(so) >= 2: ds.append(so[-2:])
    top = Counter(ds).most_common(10)
    text = "Top loto về nhiều (30 kỳ):\n"
    for so, lan in top:
        text += f"  {so}: {lan} lần\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['gan'])
def handle_gan(message):
    data = tai_du_lieu()
    if not data:
        bot.reply_to(message, "Lỗi tải dữ liệu.")
        return
    ds_theo_ky = []
    for item in data.get("items", []):
        ds_ky = []
        for p in item.get("ps", []):
            for giai, arr in p["g"].items():
                for so in arr:
                    if len(so) >= 2: ds_ky.append(so[-2:])
        ds_theo_ky.append(ds_ky)
    ds_gan = tt_gan(ds_theo_ky, 10)
    text = "Loto gan:\n" + "\n".join(f"  {so}" for so in ds_gan)
    bot.reply_to(message, text)

@bot.message_handler(commands=['xien'])
def handle_xien(message):
    data = tai_du_lieu()
    if not data:
        bot.reply_to(message, "Lỗi tải dữ liệu.")
        return
    ds = []
    for item in data.get("items", []):
        for p in item.get("ps", []):
            for giai, arr in p["g"].items():
                for so in arr:
                    if len(so) >= 2: ds.append(so[-2:])
    cap = du_doan_xien(ds, 5)
    text = "Gợi ý xiên:\n"
    for c in cap:
        text += f"  {c[0]} - {c[1]}\n"
    bot.reply_to(message, text)

# ── CHẠY ──

def chay_web():
    serve(app_web, host="0.0.0.0", port=PORT, threads=4)

def chay_bot():
    bot.infinity_polling()

def main():
    if not TOKEN:
        logging.error("Thiếu BOT_TOKEN")
        return
    # Chạy web server trong thread
    t_web = threading.Thread(target=chay_web, daemon=True)
    t_web.start()
    logging.info("Web server port %s", PORT)
    # Chạy bot polling
    logging.info("Bot đang chạy...")
    chay_bot()

if __name__ == "__main__":
    main()
