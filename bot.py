import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import requests
import schedule
from dotenv import load_dotenv

from calculator import format_tl
from scraper import (
    fetch_market_tickers,
    get_consumer_loan_offers,
    get_bank_spread_offers,
    CACHE_FILE,
)
from image_generator import render_loan_table_image, render_spread_table_image

load_dotenv(Path(__file__).parent / ".env", override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@faizradari").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def set_channel_logo(logo_path: str = "D:/faiz-radari/logo.jpg") -> bool:
    """Kanalın profil fotoğrafını otomatik günceller."""
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
    """Telegram paylaşımı için okunaklı, 1024 karakter sınırına tam uyumlu metin ve yasal uyarı üretir."""
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    principal_str = format_tl(offers[0].principal)
    months = offers[0].months
    best = offers[0]
    worst = offers[-1]
    diff = worst.total_repayment - best.total_repayment

    lines = [
        f"📡 <b>FAİZ RADARI | GÜNCEL KREDİ TABLOSU</b> ({now_str})",
        f"💱 <b>Dolar:</b> {tickers.get('USD')} | <b>Euro:</b> {tickers.get('EUR')} | <b>Gram Altın:</b> {tickers.get('ALTIN')}\n",
        f"💳 <b>{principal_str} İhtiyaç Kredisi ({months} Ay Vade) En Uygun 5 Banka:</b>",
    ]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for idx, offer in enumerate(offers[:5]):
        rate_s = f"%{offer.monthly_rate:.2f}".replace(".", ",")
        lines.append(
            f"{medals[idx]} <b>{offer.bank_name}</b> ({rate_s}) ➔ Taksit: <code>{format_tl(offer.monthly_installment)}</code> | Toplam: <b>{format_tl(offer.total_repayment)}</b>"
        )

    lines.append(
        f"\n💡 <b>Radar Notu:</b> En uygun banka (<b>{best.bank_name}</b>) ile son sıradaki banka arasında "
        f"<b>{format_tl(diff)}</b> geri ödeme farkı var."
    )

    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            zero_list = cached.get("sifir_faiz_firsatlari", [])[:3]
            if zero_list:
                lines.append("\n🔥 <b>Yeni Müşteri %0 Faiz Fırsatları:</b>")
                for item in zero_list:
                    lines.append(f"• <b>{item['bank']}:</b> {item['amount']} ({item['term']})")
        except Exception:
            pass

    lines.append(
        "\n⚠️ <i>Yasal Uyarı: Veriler açık kaynaklardan derlenmiş olup bilgilendirme amaçlıdır, "
        "yatırım/finansal tavsiye değildir.</i>\n"
        "🔔 <b>Takip:</b> @faizradari"
    )
    return "\n".join(lines)


def build_spread_caption(usd_spreads, gold_spreads, tickers) -> str:
    """Bankaların Canlı Dolar & Altın Makas Tablosu için açıklama metni üretir."""
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

    lines.append("\n🪙 <b>En Düşük Gram Altın Makası Veren Bankalar / Kurumlar:</b>")
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


def send_loan_report(principal: float = 100_000, months: int = 12) -> dict:
    """Kredi faiz verilerini çeker, görsel tabloyu üretir ve Telegram kanalında paylaşır."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Kredi verileri çekiliyor ({format_tl(principal)} / {months} Ay)...")
    tickers = fetch_market_tickers()
    offers = get_consumer_loan_offers(principal=principal, months=months)

    img_path = render_loan_table_image(
        offers=offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_loan_table.png"),
    )
    caption = build_loan_caption(offers, tickers)

    with open(img_path, "rb") as photo_file:
        resp = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML",
            },
            files={"photo": photo_file},
            timeout=30,
        )
    result = resp.json()
    if result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"[BAŞARILI] Kredi Tablosu {CHANNEL_ID} kanalında paylaşıldı! (Mesaj ID: {msg_id})")
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

    with open(img_path, "rb") as photo_file:
        resp = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML",
            },
            files={"photo": photo_file},
            timeout=30,
        )
    result = resp.json()
    if result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"[BAŞARILI] Makas Tablosu {CHANNEL_ID} kanalında paylaşıldı! (Mesaj ID: {msg_id})")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")
    return result


def run_scheduler():
    """
    Sabah 09:00'dan akşam 21:00'e kadar her 2 saatte bir dönüşümlü olarak:
    - Banka Kredi Faiz Oranları Tablosu
    - Bankaların Canlı Dolar & Altın Makas Tablosu
    paylaşır (4 saatte 2 mesaj).
    """
    print("=========================================================")
    print(" Faiz Radarı Otonom Yayın Akışı Başlatıldı (09:00 - 21:00)")
    print(" 09:00 -> Kredi Faiz Tablosu (100.000 TL / 12 Ay)")
    print(" 11:00 -> Banka Dolar & Altın Makas Tablosu")
    print(" 13:00 -> Kredi Faiz Tablosu (150.000 TL / 12 Ay)")
    print(" 15:00 -> Banka Dolar & Altın Makas Tablosu")
    print(" 17:00 -> Kredi Faiz Tablosu (200.000 TL / 24 Ay)")
    print(" 19:00 -> Banka Dolar & Altın Makas Tablosu")
    print(" 21:00 -> Kredi Faiz Tablosu (100.000 TL / 24 Ay)")
    print("=========================================================")

    schedule.every().day.at("09:00").do(send_loan_report, principal=100_000, months=12)
    schedule.every().day.at("11:00").do(send_spread_report)
    schedule.every().day.at("13:00").do(send_loan_report, principal=150_000, months=12)
    schedule.every().day.at("15:00").do(send_spread_report)
    schedule.every().day.at("17:00").do(send_loan_report, principal=200_000, months=24)
    schedule.every().day.at("19:00").do(send_spread_report)
    schedule.every().day.at("21:00").do(send_loan_report, principal=100_000, months=24)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--set-logo" in sys.argv:
        set_channel_logo()
    if "--spread" in sys.argv:
        send_spread_report()
    elif "--auto-slot" in sys.argv:
        # Bulut / GitHub Actions çalışması için Türkiye saatine (UTC+3) göre hangi tablo sıradaysa onu atar
        from datetime import timezone, timedelta
        tr_hour = datetime.now(timezone(timedelta(hours=3))).hour
        if tr_hour in (11, 15, 19):
            send_spread_report()
        elif tr_hour == 13:
            send_loan_report(principal=150_000, months=12)
        elif tr_hour == 17:
            send_loan_report(principal=200_000, months=24)
        elif tr_hour == 21:
            send_loan_report(principal=100_000, months=24)
        else:
            send_loan_report(principal=100_000, months=12)
    elif "--schedule" in sys.argv:
        run_scheduler()
    else:
        send_loan_report(principal=100_000, months=12)
