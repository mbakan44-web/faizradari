import os
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
    CACHE_FILE,
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


def _default_reply_markup() -> str:
    """Her kanal paylaşımının altına eklenecek etkileşimli butonlar."""
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "🧮 Kendi Kredini Hesapla",
                    "url": "https://t.me/faizradari_bot",
                },
                {
                    "text": "📲 Tabloyu Arkadaşına Gönder",
                    "url": "https://t.me/share/url?url=https://t.me/faizradari&text=Bankalar%C4%B1n%20canl%C4%B1%20kredi%2C%20mevduat%20ve%20d%C3%B6viz%20makas%20tablolar%C4%B1%20@faizradari%20kanal%C4%B1nda!",
                },
            ]
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


def _post_photo_to_telegram(img_path: str, caption: str) -> dict:
    with open(img_path, "rb") as photo_file:
        resp = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _default_reply_markup(),
            },
            files={"photo": photo_file},
            timeout=30,
        )
    return resp.json()


def send_loan_report(loan_type: str = "ihtiyac", principal: float = 100_000, months: int = 12) -> dict:
    """İhtiyaç, Konut veya Taşıt kredisi tablosunu üretir, varsa faiz indirimi alarmını da gönderir."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {loan_type.upper()} kredisi verileri çekiliyor ({format_tl(principal)} / {months} Ay)...")
    tickers = fetch_market_tickers()
    offers, alerts = get_loan_offers(loan_type=loan_type, principal=principal, months=months)

    # Eğer faiz indirimi yakalandıysa önce FLAŞ ALARM gönder!
    if alerts:
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
        _post_photo_to_telegram(alert_img, alert_caption)

    img_path = render_loan_table_image(
        offers=offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_loan_table.png"),
    )
    caption = build_loan_caption(offers, tickers)
    result = _post_photo_to_telegram(img_path, caption)
    if result.get("ok"):
        print(f"[BAŞARILI] {loan_type.upper()} Tablosu {CHANNEL_ID} kanalında paylaşıldı! (Mesaj ID: {result['result']['message_id']})")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")
    return result


def send_deposit_report(principal: float = 500_000, days: int = 32) -> dict:
    """Vadeli Mevduat + %0 Faizli Nakit Fırsatları tablosunu üretir ve paylaşır."""
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
    result = _post_photo_to_telegram(img_path, caption)
    if result.get("ok"):
        print(f"[BAŞARILI] Mevduat Tablosu {CHANNEL_ID} kanalında paylaşıldı! (Mesaj ID: {result['result']['message_id']})")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")
    return result


def send_spread_report() -> dict:
    """Bankaların canlı Dolar ve Gram Altın makas verilerini çeker, görsel tabloyu üretir ve paylaşır."""
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
    result = _post_photo_to_telegram(img_path, caption)
    if result.get("ok"):
        print(f"[BAŞARILI] Makas Tablosu {CHANNEL_ID} kanalında paylaşıldı! (Mesaj ID: {result['result']['message_id']})")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")
    return result


def run_scheduler():
    """
    Sabah 09:00'dan akşam 21:00'e kadar her 2 saatte bir:
    - 09:00 -> İhtiyaç Kredisi Tablosu (100.000 TL / 12 Ay)
    - 11:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu
    - 13:00 -> Konut (Ev) Kredisi Tablosu (2.000.000 TL / 120 Ay)
    - 15:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu
    - 17:00 -> Taşıt (Araç) Kredisi Tablosu (400.000 TL / 36 Ay)
    - 19:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu
    - 21:00 -> Vadeli Mevduat Getiri Tablosu (500.000 TL / 32 Gün) & %0 Faiz Fırsatları
    """
    print("=================================================================")
    print(" Faiz Radarı Tam Kapsamlı Yayın Akışı Başlatıldı (09:00 - 21:00)")
    print(" 09:00 -> İhtiyaç Kredisi Tablosu (100.000 TL / 12 Ay)")
    print(" 11:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu")
    print(" 13:00 -> Konut (Ev) Kredisi Tablosu (2.000.000 TL / 120 Ay)")
    print(" 15:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu")
    print(" 17:00 -> Taşıt (Araç) Kredisi Tablosu (400.000 TL / 36 Ay)")
    print(" 19:00 -> Bankaların Canlı Dolar & Altın Makas Tablosu")
    print(" 21:00 -> Vadeli Mevduat Getirisi (500.000 TL / 32 Gün) & %0 Faiz")
    print("=================================================================")

    schedule.every().day.at("09:00").do(send_loan_report, loan_type="ihtiyac", principal=100_000, months=12)
    schedule.every().day.at("11:00").do(send_spread_report)
    schedule.every().day.at("13:00").do(send_loan_report, loan_type="konut", principal=2_000_000, months=120)
    schedule.every().day.at("15:00").do(send_spread_report)
    schedule.every().day.at("17:00").do(send_loan_report, loan_type="tasit", principal=400_000, months=36)
    schedule.every().day.at("19:00").do(send_spread_report)
    schedule.every().day.at("21:00").do(send_deposit_report, principal=500_000, days=32)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--set-logo" in sys.argv:
        set_channel_logo()
    if "--spread" in sys.argv:
        send_spread_report()
    elif "--konut" in sys.argv:
        send_loan_report(loan_type="konut", principal=2_000_000, months=120)
    elif "--tasit" in sys.argv:
        send_loan_report(loan_type="tasit", principal=400_000, months=36)
    elif "--mevduat" in sys.argv:
        send_deposit_report(principal=500_000, days=32)
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
