import os
import re
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
import schedule
from dotenv import load_dotenv

from calculator import format_tl
from scraper import (
    fetch_market_tickers,
    get_loan_offers,
    get_deposit_offers,
    get_bank_spread_offers,
)
from image_generator import (
    render_loan_table_image,
    render_deposit_table_image,
    render_spread_table_image,
    render_rate_drop_alert_image,
)

load_dotenv(Path(__file__).parent / ".env", override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@faizradari").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = Path(__file__).parent / ".last_update_id"


def configure_bot_profile():
    """
    Telegram'da bota girildiğinde 'Bu bot ne yapabilir?' (What can this bot do?) ekranını
    ve sol alttaki '/' komut menüsünü otomatik ayarlar.
    """
    description = (
        "📡 FAİZ RADARI | İnteraktif Kredi & Mevduat Hesaplama Botu\n\n"
        "İstediğiniz tutar ve vadede tüm bankaların vergi ve masraflar dahil NET ödeme tablosunu "
        "anında hesaplamak için aşağıdaki 'BAŞLAT (START)' butonuna basın!\n\n"
        "📌 Örnek Kullanım:\n"
        "• İhtiyaç Kredisi: 150000 12\n"
        "• Konut Kredisi: konut 2000000 120\n"
        "• Taşıt Kredisi: tasit 400000 36\n"
        "• Vadeli Mevduat: mevduat 500000 32\n\n"
        "🔔 Resmi Kanalımız: @faizradari"
    )
    short_desc = "📊 İstediğiniz tutar ve vadede banka kredi/mevduat net ödeme tablosu hesaplayıcı. Kanal: @faizradari"
    commands = [
        {"command": "start", "description": "Hesaplama menüsünü ve kullanım kılavuzunu aç"},
        {"command": "ihtiyac", "description": "İhtiyaç kredisi hesapla (Örn: /ihtiyac 150000 12)"},
        {"command": "konut", "description": "Konut kredisi hesapla (Örn: /konut 2000000 120)"},
        {"command": "tasit", "description": "Taşıt kredisi hesapla (Örn: /tasit 400000 36)"},
        {"command": "mevduat", "description": "Vadeli mevduat getirisi hesapla (Örn: /mevduat 500000 32)"},
        {"command": "makas", "description": "Canlı banka Dolar & Altın makas tablosunu getir"},
    ]
    requests.post(f"{API_BASE}/setMyDescription", json={"description": description}, timeout=10)
    requests.post(f"{API_BASE}/setMyShortDescription", json={"short_description": short_desc}, timeout=10)
    requests.post(f"{API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    print("[OK] Bot karşılama ekranı ve komut menüsü güncellendi!")


def _default_reply_markup() -> str:
    """Her kanal paylaşımının altına eklenecek etkileşimli butonlar."""
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "🧮 Kendi Kredini Hesapla",
                    "url": "https://t.me/faizradari_bot?start=hesapla",
                },
                {
                    "text": "📲 Tabloyu Arkadaşına Gönder",
                    "url": "https://t.me/share/url?url=https://t.me/faizradari&text=Bankalar%C4%B1n%20canl%C4%B1%20kredi%2C%20mevduat%20ve%20d%C3%B6viz%20makas%20tablolar%C4%B1%20@faizradari%20kanal%C4%B1nda!",
                },
            ]
        ]
    }
    return json.dumps(markup)


def _interactive_menu_markup() -> str:
    """Bota özelden mesaj atan kullanıcıya çıkacak tek-tıkla hazır hesaplama butonları."""
    markup = {
        "inline_keyboard": [
            [
                {"text": "💳 100.000 TL (12 Ay)", "callback_data": "calc:ihtiyac:100000:12"},
                {"text": "💳 250.000 TL (24 Ay)", "callback_data": "calc:ihtiyac:250000:24"},
            ],
            [
                {"text": "🏠 2.000.000 TL Konut (120 Ay)", "callback_data": "calc:konut:2000000:120"},
                {"text": "🚗 400.000 TL Taşıt (36 Ay)", "callback_data": "calc:tasit:400000:36"},
            ],
            [
                {"text": "💰 500.000 TL Mevduat (32 Gün)", "callback_data": "calc:mevduat:500000:32"},
                {"text": "💱 Canlı Dolar & Altın Makası", "callback_data": "calc:makas:0:0"},
            ],
            [
                {"text": "📢 Faiz Radarı Kanalına Katıl", "url": "https://t.me/faizradari"}
            ],
        ]
    }
    return json.dumps(markup)


def set_channel_logo(logo_path: str = "D:/faiz-radari/logo.jpg") -> bool:
    p = Path(logo_path)
    if not p.exists():
        return False
    with open(p, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/setChatPhoto",
            data={"chat_id": CHANNEL_ID},
            files={"photo": f},
            timeout=20,
        )
    res = resp.json()
    if res.get("ok"):
        print("[OK] Kanal profil logosu başarıyla güncellendi!")
        return True
    print("[UYARI] Logo güncellenemedi:", res.get("description"))
    return False


def build_loan_caption(offers, tickers) -> str:
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    principal_str = format_tl(offers[0].principal)
    months = offers[0].months
    loan_type = offers[0].loan_type
    best = offers[0]
    worst = offers[-1]
    diff = worst.total_repayment - best.total_repayment

    title_map = {
        "ihtiyac": ("💳", "İHTİYAÇ KREDİSİ TABLOSU", "İhtiyaç Kredisi"),
        "konut": ("🏠", "KONUT (EV) KREDİSİ TABLOSU", "Konut Kredisi"),
        "tasit": ("🚗", "TAŞIT (ARAÇ) KREDİSİ TABLOSU", "Taşıt Kredisi"),
    }
    icon, header_title, label_name = title_map.get(loan_type, title_map["ihtiyac"])

    lines = [
        f"{icon} <b>FAİZ RADARI | GÜNCEL {header_title}</b> ({now_str})",
        f"💱 <b>Dolar:</b> {tickers.get('USD')} | <b>Euro:</b> {tickers.get('EUR')} | <b>Gram Altın:</b> {tickers.get('ALTIN')}\n",
        f"📊 <b>{principal_str} {label_name} ({months} Ay Vade) En Uygun 5 Banka:</b>",
    ]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for idx, offer in enumerate(offers[:5]):
        rate_s = f"%{offer.monthly_rate:.2f}".replace(".", ",")
        lines.append(
            f"{medals[idx]} <b>{offer.bank_name}</b> ({rate_s}) ➔ Taksit: <code>{format_tl(offer.monthly_installment)}</code> | Toplam: <b>{format_tl(offer.total_repayment)}</b>"
        )

    lines.append(
        f"\n💡 <b>Radar Notu:</b> En uygun banka (<b>{best.bank_name}</b>) ile son sıradaki banka arasında "
        f"tam <b>{format_tl(diff)}</b> toplam ödeme farkı bulunuyor."
    )

    lines.append(
        "\n⚠️ <i>Yasal Uyarı: Veriler açık kaynaklardan derlenmiş olup bilgilendirme amaçlıdır, "
        "yatırım/finansal tavsiye değildir.</i>\n"
        "🔔 <b>Takip:</b> @faizradari"
    )
    return "\n".join(lines)


def build_deposit_caption(deposits, zero_offers, tickers) -> str:
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    principal_str = format_tl(deposits[0].principal)
    days = deposits[0].days

    lines = [
        f"💰 <b>FAİZ RADARI | VADELİ MEVDUAT & %0 FAİZ FIRSATLARI</b> ({now_str})",
        f"📈 <b>{principal_str} Anaparanın {days} Günlük Net Mevduat Getirisi (Stopaj Düşülmüş):</b>",
    ]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for idx, dep in enumerate(deposits[:5]):
        rate_s = f"%{dep.annual_rate:.1f}".replace(".", ",")
        lines.append(
            f"{medals[idx]} <b>{dep.bank_name}</b> ({rate_s}) ➔ Net Kazanç: <b>+{format_tl(dep.net_return)}</b> | Toplam: <code>{format_tl(dep.total_balance)}</code>"
        )

    if zero_offers:
        lines.append("\n🔥 <b>Yeni Müşterilere Özel %0 Faizli Nakit Fırsatları:</b>")
        for item in zero_offers[:4]:
            lines.append(f"• <b>{item['bank']}:</b> {item['amount']} ({item['term']})")

    lines.append(
        "\n⚠️ <i>Yasal Uyarı: Mevduat oranları ve hoş geldin kampanyaları müşteri segmentine göre değişebilir, "
        "yatırım tavsiyesi değildir.</i>\n"
        "🔔 <b>Takip:</b> @faizradari"
    )
    return "\n".join(lines)


def build_spread_caption(usd_spreads, gold_spreads, tickers) -> str:
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    lines = [
        f"💱 <b>FAİZ RADARI | BANKA DOLAR & ALTIN MAKAS TABLOSU</b> ({now_str})",
        f"📊 <b>Serbest Piyasa Ref:</b> Dolar: <b>{tickers.get('USD')}</b> | Gram Altın: <b>{tickers.get('ALTIN')}</b>\n",
        "💵 <b>En Düşük Dolar (USD) Makası Veren Bankalar:</b>",
    ]
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    for idx, u in enumerate(usd_spreads[:4]):
        buy_s = f"{u.buy_price:.2f} ₺".replace(".", ",")
        sell_s = f"{u.sell_price:.2f} ₺".replace(".", ",")
        sp_s = f"{u.spread_tl:.2f} ₺ (%{u.spread_pct:.2f})".replace(".", ",")
        lines.append(f"{medals[idx]} <b>{u.bank_name}:</b> Alış <code>{buy_s}</code> | Satış <code>{sell_s}</code> ➔ Makas: <b>{sp_s}</b>")

    lines.append("\n🪙 <b>En Düşük Gram Altın Makası Veren Bankalar:</b>")
    for idx, g in enumerate(gold_spreads[:4]):
        buy_s = f"{g.buy_price:,.0f} ₺".replace(",", ".")
        sell_s = f"{g.sell_price:,.0f} ₺".replace(",", ".")
        sp_s = f"{g.spread_tl:,.0f} ₺ (%{g.spread_pct:.2f})".replace(",", ".")
        lines.append(f"{medals[idx]} <b>{g.bank_name}:</b> Alış <code>{buy_s}</code> | Satış <code>{sell_s}</code> ➔ Makas: <b>{sp_s}</b>")

    lines.append(
        "\n⚠️ <i>Yasal Uyarı: Banka alış-satış kurları açık kaynaklardan anlık çekilmektedir, "
        "mesai saatleri dışında makaslar açılabilir. Yatırım tavsiyesi değildir.</i>\n"
        "🔔 <b>Takip:</b> @faizradari"
    )
    return "\n".join(lines)


def _post_photo_to_telegram(img_path: str, caption: str, target_chat_id: str = CHANNEL_ID, reply_markup: str = None) -> dict:
    with open(img_path, "rb") as photo_file:
        resp = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": reply_markup or _default_reply_markup(),
            },
            files={"photo": photo_file},
            timeout=30,
        )
    return resp.json()


def send_loan_report(loan_type: str = "ihtiyac", principal: float = 100_000, months: int = 12, target_chat_id: str = CHANNEL_ID) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {loan_type.upper()} kredisi verileri çekiliyor ({format_tl(principal)} / {months} Ay)...")
    tickers = fetch_market_tickers()
    offers, alerts = get_loan_offers(loan_type=loan_type, principal=principal, months=months)

    if alerts and target_chat_id == CHANNEL_ID:
        alert_img = render_rate_drop_alert_image(
            alerts=alerts,
            output_path=str(Path(__file__).parent / "latest_alert.png"),
        )
        a = alerts[0]
        alert_caption = (
            f"🚨 <b>FLAŞ ALARM | {a.bank_name.upper()} FAİZ İNDİRDİ!</b>\n\n"
            f"📉 <b>Eski Oran:</b> %{a.old_rate:.2f} ➔ <b>Yeni Oran:</b> <b>%{a.new_rate:.2f}</b>\n"
            f"💰 <b>{format_tl(a.principal)} ({a.months} Ay)</b> kredide toplam geri ödeme "
            f"<b>{format_tl(a.total_savings)}</b> azaldı!\n\n"
            f"⚠️ <i>Bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.</i>\n"
            f"🔔 @faizradari"
        )
        _post_photo_to_telegram(alert_img, alert_caption, target_chat_id=CHANNEL_ID)

    img_path = render_loan_table_image(
        offers=offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_loan_table.png"),
    )
    caption = build_loan_caption(offers, tickers)
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if result.get("ok"):
        print(f"[BAŞARILI] {loan_type.upper()} Tablosu {target_chat_id} hedefine paylaşıldı!")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")
    return result


def send_deposit_report(principal: float = 500_000, days: int = 32, target_chat_id: str = CHANNEL_ID) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Mevduat verileri çekiliyor ({format_tl(principal)} / {days} Gün)...")
    tickers = fetch_market_tickers()
    deposits, zero_offers = get_deposit_offers(principal=principal, days=days)

    img_path = render_deposit_table_image(
        deposits=deposits,
        zero_offers=zero_offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_deposit_table.png"),
    )
    caption = build_deposit_caption(deposits, zero_offers, tickers)
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    return result


def send_spread_report(target_chat_id: str = CHANNEL_ID) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Banka Dolar & Altın makas verileri çekiliyor...")
    tickers = fetch_market_tickers()
    usd_spreads, gold_spreads = get_bank_spread_offers()

    img_path = render_spread_table_image(
        usd_spreads=usd_spreads,
        gold_spreads=gold_spreads,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_spread_table.png"),
    )
    caption = build_spread_caption(usd_spreads, gold_spreads, tickers)
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    return result


def send_welcome_guide(chat_id: int) -> None:
    """Kullanıcı bota /start dediğinde nasıl hesaplama yapacağını anlatan rehber ve butonları gönderir."""
    welcome_text = (
        "👋 <b>Faiz Radarı Hesaplama Botuna Hoş Geldiniz!</b>\n\n"
        "İstediğiniz kredi veya mevduat tutarını tüm bankalar için <b>vergi ve dosya masrafları dahil</b> "
        "anında hesaplayıp size özel tablo olarak üretirim.\n\n"
        "📌 <b>Nasıl Hesaplama Yapılır?</b>\n"
        "Bana doğrudan şu formatlarda mesaj yazıp gönderebilirsiniz:\n\n"
        "💳 <b>İhtiyaç Kredisi için:</b>\n"
        "👉 <code>150000 12</code> <i>(150.000 TL 12 Ay Vade)</i>\n"
        "👉 <code>300000 24</code> <i>(300.000 TL 24 Ay Vade)</i>\n\n"
        "🏠 <b>Konut (Ev) Kredisi için:</b>\n"
        "👉 <code>konut 2500000 120</code> <i>(2.500.000 TL 120 Ay Vade)</i>\n\n"
        "🚗 <b>Taşıt (Araç) Kredisi için:</b>\n"
        "👉 <code>tasit 500000 36</code> <i>(500.000 TL 36 Ay Vade)</i>\n\n"
        "💰 <b>Vadeli Mevduat Getirisi için:</b>\n"
        "👉 <code>mevduat 750000 32</code> <i>(750.000 TL 32 Gün Vade)</i>\n\n"
        "👇 <i>Veya aşağıdaki hazır butonlardan birine hemen tıklayabilirsiniz:</i>"
    )
    requests.post(
        f"{API_BASE}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": welcome_text,
            "parse_mode": "HTML",
            "reply_markup": json.loads(_interactive_menu_markup()),
        },
        timeout=15,
    )


def handle_user_query(chat_id: int, text: str) -> None:
    """Kullanıcının yazdığı metni (ör. '250000 18' veya 'konut 3000000 120') ayrıştırıp tabloyu gönderir."""
    clean = text.strip().lower()
    if clean.startswith("/start") or clean.startswith("/yardim") or clean.startswith("/help"):
        send_welcome_guide(chat_id)
        return
    if clean.startswith("/makas") or clean == "makas":
        send_spread_report(target_chat_id=str(chat_id))
        return

    # İçindeki sayıları yakala (nokta/virgül temizleyerek)
    nums = [int(n.replace(".", "").replace(",", "")) for n in re.findall(r"\d[\d\.,]*", clean)]
    if len(nums) >= 2:
        amount = float(nums[0])
        term = int(nums[1])
        # Tutar ve vade sınır kontrolü
        amount = max(5_000.0, min(amount, 50_000_000.0))
        term = max(1, min(term, 360))

        if "konut" in clean or "ev" in clean:
            send_loan_report("konut", principal=amount, months=term, target_chat_id=str(chat_id))
        elif "tasit" in clean or "taşıt" in clean or "arac" in clean or "araç" in clean:
            send_loan_report("tasit", principal=amount, months=term, target_chat_id=str(chat_id))
        elif "mevduat" in clean or "faiz" in clean:
            send_deposit_report(principal=amount, days=term, target_chat_id=str(chat_id))
        else:
            send_loan_report("ihtiyac", principal=amount, months=term, target_chat_id=str(chat_id))
    else:
        send_welcome_guide(chat_id)


def process_pending_updates() -> None:
    """Bota gelen yeni kullanıcı mesajlarını ve buton tıklamalarını işler."""
    offset = 0
    if OFFSET_FILE.exists():
        try:
            offset = int(OFFSET_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            offset = 0

    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params={"offset": offset, "timeout": 2}, timeout=8).json()
        if not resp.get("ok"):
            return
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            OFFSET_FILE.write_text(str(offset), encoding="utf-8")

            if "message" in upd and "text" in upd["message"]:
                msg = upd["message"]
                if msg.get("chat", {}).get("type") == "private":
                    handle_user_query(msg["chat"]["id"], msg["text"])

            elif "callback_query" in upd:
                cb = upd["callback_query"]
                chat_id = cb["message"]["chat"]["id"]
                data = cb.get("data", "")
                requests.post(f"{API_BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"], "text": "Tablonuz hazırlanıyor..."}, timeout=5)
                parts = data.split(":")
                if len(parts) == 4 and parts[0] == "calc":
                    kind, amt, trm = parts[1], float(parts[2]), int(parts[3])
                    if kind == "makas":
                        send_spread_report(target_chat_id=str(chat_id))
                    elif kind == "mevduat":
                        send_deposit_report(principal=amt, days=trm, target_chat_id=str(chat_id))
                    else:
                        send_loan_report(kind, principal=amt, months=trm, target_chat_id=str(chat_id))
    except Exception as e:
        print("[UYARI] Update işleme hatası:", e)


def run_scheduler():
    print("=================================================================")
    print(" Faiz Radarı Tam Kapsamlı Yayın Akışı & İnteraktif Bot Başlatıldı")
    print("=================================================================")
    configure_bot_profile()

    schedule.every().day.at("09:00").do(send_loan_report, loan_type="ihtiyac", principal=100_000, months=12)
    schedule.every().day.at("11:00").do(send_spread_report)
    schedule.every().day.at("13:00").do(send_loan_report, loan_type="konut", principal=2_000_000, months=120)
    schedule.every().day.at("15:00").do(send_spread_report)
    schedule.every().day.at("17:00").do(send_loan_report, loan_type="tasit", principal=400_000, months=36)
    schedule.every().day.at("19:00").do(send_spread_report)
    schedule.every().day.at("21:00").do(send_deposit_report, principal=500_000, days=32)

    while True:
        schedule.run_pending()
        process_pending_updates()
        time.sleep(3)


if __name__ == "__main__":
    if "--set-logo" in sys.argv:
        set_channel_logo()
    if "--listen-only" in sys.argv:
        configure_bot_profile()
        print("İnteraktif Kredi Hesaplama Botu (@faizradari_bot) dinlemede...")
        while True:
            process_pending_updates()
            time.sleep(2)
    elif "--setup-bot" in sys.argv:
        configure_bot_profile()
        process_pending_updates()
    elif "--spread" in sys.argv:
        send_spread_report()
    elif "--konut" in sys.argv:
        send_loan_report(loan_type="konut", principal=2_000_000, months=120)
    elif "--tasit" in sys.argv:
        send_loan_report(loan_type="tasit", principal=400_000, months=36)
    elif "--mevduat" in sys.argv:
        send_deposit_report(principal=500_000, days=32)
    elif "--set-webhook" in sys.argv:
        idx = sys.argv.index("--set-webhook")
        if idx + 1 < len(sys.argv):
            wh_url = sys.argv[idx + 1].strip()
            r = requests.post(f"{API_BASE}/setWebhook", json={"url": wh_url}, timeout=10).json()
            print("Webhook durumu:", r)
    elif "--auto-slot" in sys.argv:
        tr_hour = datetime.now(timezone(timedelta(hours=3))).hour
        if tr_hour in (11, 15, 19):
            send_spread_report()
        elif tr_hour in (12, 13, 14):
            send_loan_report(loan_type="konut", principal=2_000_000, months=120)
        elif tr_hour in (16, 17, 18):
            send_loan_report(loan_type="tasit", principal=400_000, months=36)
        elif tr_hour >= 20:
            send_deposit_report(principal=500_000, days=32)
        else:
            send_loan_report(loan_type="ihtiyac", principal=100_000, months=12)
    elif "--schedule" in sys.argv:
        run_scheduler()
    else:
        send_loan_report(loan_type="ihtiyac", principal=100_000, months=12)
