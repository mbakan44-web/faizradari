import os
import sys
import time
import json
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import bot
import ilan_radari

def dispatch_all():
    results = {}

    card_png = str(Path(__file__).parent / "ilan_radari_magfi_1080x1080.png")
    promo_video = str(Path(__file__).parent / "ilan_radari_magfi_video_15sn.mp4")
    raw_video_url = f"https://raw.githubusercontent.com/mbakan44-web/faizradari/main/ilan_radari_magfi_video_15sn.mp4?v={int(time.time())}"

    # 1. WHATSAPP (Faiz Radarı Kanalı - Bilgilendirme)
    print("\n[1/5] WhatsApp Faiz Radarı Kanalı paylaşılıyor...")
    wa_promo_cap = (
        "📢 *BİLGİLENDİRME: YENİ 'İLAN RADARI' SAYFAMIZ AÇILDI!* 🎯\n\n"
        "Değerli takipçilerimiz; Türkiye genelindeki güncel *kamu personel alımlarını, İŞKUR iş ilanlarını, banka personel alımlarını* ve *meslek meslek maaş / promosyon tablolarını* artık yeni *İlan Radarı* kanallarımızda paylaşıyoruz.\n\n"
        "📋 *İlan Radarı'nda Neler Var?*\n"
        "1️⃣ *Bakanlık, Hastane & Üniversite Alımları:* KPSS'li sözleşmeli personel ve memur ilanları\n"
        "2️⃣ *İŞKUR & Belediye İlanları:* KPSS şartsız sürekli işçi ve personel alımları\n"
        "3️⃣ *Banka Kariyer İlanları:* Gişe yetkilisi, çağrı merkezi ve uzman yardımcısı alımları\n"
        "4️⃣ *Maaş & Haklar Rehberi:* Kamu maaş zamları, emekli promosyon ligi ve kıdem tazminatı tabloları\n\n"
        "👇 *Aşağıdaki linklerden ücretsiz katılabilirsiniz:*\n"
        "🔹 *Telegram:* https://t.me/ilanradari\n"
        "🟢 *WhatsApp:* https://whatsapp.com/channel/0029Vb9rhBs90x2y0jH3O31J"
    )
    try:
        bot.post_to_whatsapp(card_png, wa_promo_cap)
        results["WhatsApp_Faiz_Radari"] = "Başarılı"
    except Exception as e:
        results["WhatsApp_Faiz_Radari"] = f"Hata: {e}"

    # 2. WHATSAPP (İlan Radarı Kanalı - Güncel İlan Tablosu)
    print("\n[2/5] WhatsApp İlan Radarı Kanalı güncel ilanlar paylaşılıyor...")
    try:
        jobs = ilan_radari.fetch_live_job_announcements(limit=6)
        if jobs:
            img_table = ilan_radari.render_daily_jobs_table_image(jobs, str(Path(__file__).parent / "latest_ilan_table.png"))
            now_str = time.strftime("%d.%m.%Y")
            top_hook = jobs[0]["title"]
            bullet_lines = []
            for i, j in enumerate(jobs[:5]):
                t_sub = j["title"][:72]
                bullet_lines.append(f"{i+1}️⃣ *{t_sub}* (_{j['tag']}_)")
            bullets = "\n".join(bullet_lines)
            table_cap = (
                f"🔥 *{top_hook}*\n"
                f"📋 _Günün Öne Çıkan Personel Alımları ({now_str}):_\n\n"
                f"{bullets}\n\n"
                "🏛️ *Resmi Başvuru Portalları:*\n"
                "• https://isealimkariyerkapisi.cbiko.gov.tr (e-Devlet)\n"
                "• https://esube.iskur.gov.tr (İŞKUR)"
            )
            ilan_radari.post_ilan_to_whatsapp(img_table, table_cap)
            results["WhatsApp_Ilan_Radari"] = "Başarılı"
    except Exception as e:
        results["WhatsApp_Ilan_Radari"] = f"Hata: {e}"

    # 3. X (Twitter - @faizradari - 15sn Video + Tanıtım)
    print("\n[3/5] X (Twitter) paylaşılıyor...")
    try:
        x_text = (
            "📢 Bilgilendirme: Yeni 'İlan Radarı' Sayfamız Açıldı!\n\n"
            "Güncel kamu personel alımlarını, İŞKUR iş ilanlarını, banka alımlarını ve meslek meslek maaş/promosyon tablolarını artık İlan Radarı sayfamızda paylaşıyoruz:\n\n"
            "• Bakanlık, Belediye & Hastane Alımları\n"
            "• İŞKUR & Banka İş İlanları\n"
            "• Maaş & Emekli Promosyon Tabloları\n\n"
            "👉 @ilanradari ile takipte kalın!"
        )
        bot.post_to_x(promo_video, x_text)
        results["X_Twitter"] = "Başarılı"
    except Exception as e:
        results["X_Twitter"] = f"Hata: {e}"

    # 4. INSTAGRAM (@faizradari via Buffer - Reel Video)
    print("\n[4/5] Instagram (Buffer) paylaşılıyor...")
    ig_caption = (
        "📢 Bilgilendirme: Yeni 'İlan Radarı' Sayfamız Açıldı! 🎯\n\n"
        "Türkiye genelindeki güncel kamu personel alımlarını, İŞKUR iş ilanlarını, banka personel alımlarını ve meslek meslek maaş/promosyon tablolarını artık yeni İlan Radarı kanalımızda tek tabloda paylaşıyoruz:\n\n"
        "1️⃣ Bakanlık, Belediye, Şehir Hastanesi ve Üniversite personel alımları\n"
        "2️⃣ İŞKUR KPSS'li ve KPSS şartsız güncel memur & işçi ilanları\n"
        "3️⃣ Banka personel alımları, maaş zamları ve emekli promosyon ligi\n\n"
        "👉 Katılmak için Telegram arama kısmına @ilanradari yazarak veya profilimizdeki linkten ücretsiz kanalımıza hemen katılabilirsiniz!\n\n"
        "İş arayan arkadaşlarınızla paylaşmayı unutmayın 👇\n\n"
        "#işilanları #personelalımı #kpss #işkur #kariyer #ilanradari #kamupersoneli"
    )
    try:
        ok_ig = bot.post_to_buffer_instagram(raw_video_url, ig_caption, is_video=True)
        results["Instagram"] = "Başarılı" if ok_ig else "Buffer Hata"
    except Exception as e:
        results["Instagram"] = f"Hata: {e}"

    # 5. TIKTOK (@faizradari via Buffer - Dikey Video)
    print("\n[5/5] TikTok (Buffer) paylaşılıyor...")
    tiktok_caption = (
        "Türkiye'nin en hızlı kamu ve iş ilanı radarı açıldı! Güncel personel alımları ve maaş tabloları için İlan Radarı'nı takip edin! 🎯 #işilanları #personelalımı #kpss #işkur #kariyer"
    )
    try:
        ok_tt = bot.post_to_buffer_tiktok(raw_video_url, tiktok_caption, is_video=True)
        results["TikTok"] = "Başarılı" if ok_tt else "Buffer Hata"
    except Exception as e:
        results["TikTok"] = f"Hata: {e}"

    print("\n--- TÜM SONUÇLAR ---")
    for k, v in results.items():
        print(f"{k}: {v}")
    return results

if __name__ == "__main__":
    dispatch_all()
