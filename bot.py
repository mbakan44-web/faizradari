import os
import re
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from pathlib import Path
import requests
import schedule
import tweepy
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
    render_briefing_table_image,
    render_weekly_recap_image,
    render_breaking_news_image,
    render_vertical_story_image,
)

load_dotenv(Path(__file__).parent / ".env", override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@faizradari").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = Path(__file__).parent / ".last_update_id"

X_API_KEY = os.getenv("X_API_KEY", "").strip()
X_API_SECRET = os.getenv("X_API_SECRET", "").strip()
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip()
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN", "9HHe4hOHubOEGnfoSQ2CjR1ak1VxxqFK").strip()
WHATSAPP_CHANNEL_ID = os.getenv("WHATSAPP_CHANNEL_ID", "120363414327685491@newsletter").strip()

INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "702244471").strip()

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY", "V5XMW26ILFn0vGh-JEcGgMeopgyd2Q8HgHPyMTAOBAI").strip()
BUFFER_TIKTOK_CHANNEL_ID = os.getenv("BUFFER_TIKTOK_CHANNEL_ID", "6af3513f62b70b94b0e575f0").strip()
BUFFER_INSTAGRAM_CHANNEL_ID = os.getenv("BUFFER_INSTAGRAM_CHANNEL_ID", "6af362bc62b70b94b0e67a0e").strip()


def convert_to_whatsapp(text: str) -> str:
    """
    Telegram HTML etiketlerini WhatsApp uyumlu markdown formatına dönüştürür.
    WhatsApp etiketleri: *kalın*, _italik_.
    """
    t = re.sub(r'<b>(.*?)</b>', r'*\1*', text, flags=re.DOTALL)
    t = re.sub(r'<strong>(.*?)</strong>', r'*\1*', t, flags=re.DOTALL)
    t = re.sub(r'<i>(.*?)</i>', r'_\1_', t, flags=re.DOTALL)
    t = re.sub(r'<em>(.*?)</em>', r'_\1_', t, flags=re.DOTALL)
    t = re.sub(r'<code>(.*?)</code>', r'*\1*', t, flags=re.DOTALL)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(
        r'🔔\s*\*?Takip:\*?\s*@faizradari',
        '🔔 *Faiz Radarı WhatsApp Kanalı*\n'
        '• Anlık bültenler için sağ üstteki çan simgesine tıklayarak bildirimleri açmayı unutmayın!\n'
        '🤖 Kişiye özel net ödeme planı ve anlık hesaplama için Telegram Botumuz:\n'
        '👉 https://t.me/faizradari_bot',
        t
    )
    return t.strip()


def post_to_whatsapp(img_path: str, caption: str) -> None:
    """
    Whapi.cloud üzerinden WhatsApp Kanalına (@newsletter) otomatik görsel + metin paylaşır.
    """
    if not (WHAPI_TOKEN and WHATSAPP_CHANNEL_ID):
        return
    try:
        import base64
        wa_text = convert_to_whatsapp(caption)
        
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        payload = {
            "to": WHATSAPP_CHANNEL_ID,
            "media": f"data:image/png;base64,{img_b64}",
            "caption": wa_text
        }
        
        url = "https://gate.whapi.cloud/messages/image"
        headers = {
            "Authorization": f"Bearer {WHAPI_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "FaizRadari-Bot/1.0"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code in (200, 201):
            print(f"[BAŞARILI] Tablo ve açıklama WhatsApp Kanalında ({WHATSAPP_CHANNEL_ID}) paylaşıldı!")
        else:
            print(f"[UYARI] WhatsApp paylaşımı başarısız: HTTP {res.status_code} - {res.text[:200]}")
    except Exception as e:
        print(f"[UYARI] WhatsApp paylaşım hatası: {e}")


def post_to_instagram(image_url: str, caption: str) -> None:
    """
    Meta Graph API (Instagram Content Publishing API) üzerinden
    Instagram İşletme/İçerik Üreticisi hesabına otomatik gönderi paylaşır.
    """
    if not (INSTAGRAM_ACCOUNT_ID and INSTAGRAM_ACCESS_TOKEN and image_url):
        return
    try:
        # 1. Media Container oluştur
        create_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media"
        params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        }
        res1 = requests.post(create_url, data=params, timeout=30).json()
        creation_id = res1.get("id")
        if not creation_id:
            print(f"[UYARI] Instagram media container oluşturulamadı: {res1}")
            return

        # 2. Gönderiyi Yayınla
        pub_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        res2 = requests.post(pub_url, data={"creation_id": creation_id, "access_token": INSTAGRAM_ACCESS_TOKEN}, timeout=30).json()
        if res2.get("id"):
            print(f"[BAŞARILI] Gönderi Instagram hesabında yayınlandı! (ID: {res2.get('id')})")
        else:
            print(f"[UYARI] Instagram yayınlama hatası: {res2}")
    except Exception as e:
        print(f"[UYARI] Instagram API hatası: {e}")


def send_vertical_story_to_admin(square_img_path: str, title: str = "GÜNÜN FİNANS RAPORU", topic: str = "story") -> None:
    """
    Kare tabloyu 1080x1920 dikey TikTok & Instagram Reels/Story şablonuna dönüştürüp
    yönetici Telegram hesabına hazır etiket ve açıklamasıyla iletir.
    Böylece yönetici tek tıkla TikTok'ta trend müzik ekleyerek paylaşabilir.
    """
    if not ADMIN_CHAT_ID:
        return
    try:
        out_v = str(Path(__file__).parent / f"latest_vertical_{topic}.png")
        render_vertical_story_image(square_img_path, title=title, output_path=out_v)
        caption = (
            f"🎬 <b>TIKTOK & INSTAGRAM REELS İÇİN HAZIR DİKEY GÖRSEL</b> (9:16)\n\n"
            f"📌 <b>Örnek Başlık:</b>\n"
            f"Bankaların güncel faizleri ve maliyetleri güncellendi! Siz bu oranlar hakkında ne düşünüyorsunuz? 👇\n\n"
            f"📲 Canlı hesaplama profildeki linkte: @faizradari\n"
            f"#faiz #kredi #mevduat #finans #para #banka #ekonomi"
        )
        _post_photo_to_telegram(out_v, caption, target_chat_id=ADMIN_CHAT_ID)
        print(f"[BİLGİ] TikTok/Reels dikey şablonu yöneticiye ({ADMIN_CHAT_ID}) iletildi!")
    except Exception as e:
        print(f"[UYARI] Dikey hikaye yöneticiye iletilemedi: {e}")


def post_to_buffer_tiktok(image_url: str, caption: str) -> bool:
    """
    Buffer GraphQL API üzerinden TikTok (@faizradari) hesabına anında otomatik paylaşım yapar.
    """
    if not (BUFFER_API_KEY and BUFFER_TIKTOK_CHANNEL_ID and image_url):
        return False
    try:
        mutation = """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post {
                id
                status
              }
            }
            ... on MutationError {
              message
            }
          }
        }
        """
        variables = {
            "input": {
                "channelId": BUFFER_TIKTOK_CHANNEL_ID,
                "text": caption,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "needsApproval": False,
                "assets": [
                    {
                        "image": {
                            "url": image_url
                        }
                    }
                ]
            }
        }
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }
        res = requests.post("https://api.buffer.com", json={"query": mutation, "variables": variables}, headers=headers, timeout=30).json()
        post_data = res.get("data", {}).get("createPost", {})
        if "post" in post_data:
            print(f"[BAŞARILI] Gönderi Buffer üzerinden TikTok hesabına iletildi! (Post ID: {post_data['post']['id']})")
            return True
        else:
            print(f"[UYARI] Buffer TikTok gönderim hatası: {post_data.get('message', res)}")
            return False
    except Exception as e:
        print(f"[UYARI] Buffer API hatası: {e}")
        return False


def post_to_buffer_instagram(image_url: str, caption: str) -> bool:
    """
    Buffer GraphQL API üzerinden Instagram (@faizradari) hesabına anında otomatik feed gönderisi paylaşır.
    """
    if not (BUFFER_API_KEY and BUFFER_INSTAGRAM_CHANNEL_ID and image_url):
        return False
    try:
        mutation = """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post {
                id
                status
              }
            }
            ... on MutationError {
              message
            }
          }
        }
        """
        variables = {
            "input": {
                "channelId": BUFFER_INSTAGRAM_CHANNEL_ID,
                "text": caption,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "needsApproval": False,
                "metadata": {
                    "instagram": {
                        "type": "post",
                        "shouldShareToFeed": True
                    }
                },
                "assets": [
                    {
                        "image": {
                            "url": image_url
                        }
                    }
                ]
            }
        }
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }
        res = requests.post("https://api.buffer.com", json={"query": mutation, "variables": variables}, headers=headers, timeout=30).json()
        post_data = res.get("data", {}).get("createPost", {})
        if "post" in post_data:
            print(f"[BAŞARILI] Gönderi Buffer üzerinden Instagram hesabına iletildi! (Post ID: {post_data['post']['id']})")
            return True
        else:
            print(f"[UYARI] Buffer Instagram gönderim hatası: {post_data.get('message', res)}")
            return False
    except Exception as e:
        print(f"[UYARI] Buffer Instagram API hatası: {e}")
        return False


def sanitize_x_text(text: str) -> str:
    """
    X API pay-per-use maliyet optimizasyonu:
    Tweet içinde URL (http/https/t.me vb.) olduğunda 'ContentCreateWithUrl' olarak
    değerlendirilip 0,20$ faturalandırılır.
    URL içermeyen düz metin paylaşımları ise 'PostCreate' / 'ContentCreate' olarak
    yalnızca ~0,01$ - 0,015$ (20 kat daha ucuz) tutar.
    Bu fonksiyon tweet metnindeki tüm URL'leri ve link tetikleyen uzantıları temizler.
    """
    import re
    # 1. Telegram linklerini kanal etiketine dönüştür
    text = re.sub(r'https?://t\.me/faizradari_bot\S*', '@faizradari_bot', text)
    text = re.sub(r'https?://t\.me/faizradari\S*', '@faizradari', text)
    text = re.sub(r't\.me/faizradari\S*', '@faizradari', text)
    # 2. Banka .com kalıntılarını düzelt (örn. enpara.com -> Enpara)
    text = re.sub(r'enpara\.com', 'Enpara', text, flags=re.IGNORECASE)
    # 3. Herhangi bir http/https URL'sini tamamen sil
    text = re.sub(r'https?://\S+', '', text)
    # 4. t.me veya bit.ly gibi domain tetikleyicileri temizle
    text = re.sub(r'\b[a-zA-Z0-9-]+\.(com|org|net|me|io|co)\b', '', text)
    return text.strip()


def post_to_x(img_path: str = None, tweet_text: str = "") -> None:
    """
    X (Twitter) paylaşım motoru:
    - img_path verilmişse: Görsel + Metin paylaşır (Günde 1 kez).
    - img_path None ise: Yalnızca zengin metin paylaşır (~0.01$ düşük maliyetli, günde 6 kez).
    - tweet_text: sanitize_x_text ile URL'lerden arındırılarak 0.01$ tarifesinde kalması sağlanır.
    """
    if not (X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET):
        return
    try:
        # URL temizliği (0.20$ yerine 0.01$ PostCreate tarifesi için zorunlu)
        cleaned_text = sanitize_x_text(tweet_text)

        client_v2 = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )
        media_ids = None
        if img_path and Path(img_path).exists():
            auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
            api_v1 = tweepy.API(auth)
            media = api_v1.media_upload(filename=img_path)
            media_ids = [media.media_id]

        res = client_v2.create_tweet(text=cleaned_text, media_ids=media_ids)
        mode = "Görselli" if media_ids else "Metin"
        print(f"[BAŞARILI] {mode} Tweet X (@faizradari) hesabında paylaşıldı! (Tweet ID: {res.data.get('id')})")
    except Exception as e:
        print(f"[UYARI] X paylaşımı yapılamadı: {e}")


def configure_bot_profile():
    description = (
        "📡 FAİZ RADARI | İnteraktif Kredi & Mevduat Hesaplama Botu\n\n"
        "İstediğiniz tutar ve vadede tüm bankaların vergi ve masraflar dahil NET ödeme tablosunu "
        "anında hesaplamak için aşağıdaki 'BAŞLAT (START)' butonuna basın!\n\n"
        "📌 Örnek Kullanım:\n"
        "• İhtiyaç Kredisi: 150000 12\n"
        "• Konut Kredisi: konut 2000000 120\n"
        "• Taşıt Kredisi: tasit 400000 36\n"
        "• Vadeli Mevduat: mevduat 500000 32\n\n"
        "🤝 Reklam & Sponsorluk: Teklifinizi doğrudan bu bota mesaj olarak yazabilirsiniz.\n"
        "🔔 Resmi Kanalımız: @faizradari"
    )
    short_desc = "📊 Kredi/mevduat hesaplama ve reklam/işbirliği masası. Kanal: @faizradari"
    commands = [
        {"command": "start", "description": "Hesaplama menüsünü ve kullanım kılavuzunu aç"},
        {"command": "ihtiyac", "description": "İhtiyaç kredisi hesapla (Örn: /ihtiyac 150000 12)"},
        {"command": "konut", "description": "Konut kredisi hesapla (Örn: /konut 2000000 120)"},
        {"command": "tasit", "description": "Taşıt kredisi hesapla (Örn: /tasit 400000 36)"},
        {"command": "mevduat", "description": "Vadeli mevduat getirisi hesapla (Örn: /mevduat 500000 32)"},
        {"command": "makas", "description": "Canlı banka Dolar & Altın makas tablosunu getir"},
        {"command": "reklam", "description": "Reklam ve işbirliği teklifi ilet"},
    ]
    requests.post(f"{API_BASE}/setMyDescription", json={"description": description}, timeout=10)
    requests.post(f"{API_BASE}/setMyShortDescription", json={"short_description": short_desc}, timeout=10)
    requests.post(f"{API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    print("[OK] Bot karşılama ekranı ve komut menüsü güncellendi!")


def _default_reply_markup() -> str:
    x_share_text = (
        "📊 Bankaların güncel faiz oranları, net ödeme ve döviz/altın makas tablosu!\n\n"
        "Daha fazla ayrıntılı bilgi ve kredi hesaplaması için Telegram sayfamızı ziyaret edebilirsiniz 👇\n"
        "https://t.me/faizradari\n\n"
        "#kredi #faiz #mevduat #dolar #altın"
    )
    import urllib.parse
    encoded_x = urllib.parse.quote(x_share_text)
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "🧮 Kendi Kredini Hesapla",
                    "url": "https://t.me/faizradari_bot?start=hesapla",
                },
                {
                    "text": "🟢 WhatsApp Kanalımız",
                    "url": "https://whatsapp.com/channel/0029VbEfeZbDOQIhMaWcVg2I",
                },
            ],
            [
                {
                    "text": "🐦 X'te (Twitter) Paylaş",
                    "url": f"https://x.com/intent/tweet?text={encoded_x}",
                },
                {
                    "text": "📲 Arkadaşına Gönder",
                    "url": "https://t.me/share/url?url=https://t.me/faizradari&text=Bankalar%C4%B1n%20canl%C4%B1%20kredi%2C%20mevduat%20ve%20d%C3%B6viz%20makas%20tablolar%C4%B1%20@faizradari%20kanal%C4%B1nda!",
                },
            ],
        ]
    }
    return json.dumps(markup)


def _interactive_menu_markup() -> str:
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
                {"text": "🟢 WhatsApp Kanalımız", "url": "https://whatsapp.com/channel/0029VbEfeZbDOQIhMaWcVg2I"},
                {"text": "📢 Telegram Kanalı", "url": "https://t.me/faizradari"},
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


def should_attach_image_to_x(current_topic: str) -> bool:
    """
    X API maliyetini minimumda tutmak için:
    Günde tam 7 tweet atılır ama yalnızca GÜNDE 1 KEZ görsel eklenir.
    Haftanın gününe göre hangi konunun görsel alacağı döner:
    - Pazartesi: İhtiyaç Kredisi (09:00)
    - Salı: Konut Kredisi (13:00)
    - Çarşamba: Banka Dolar & Altın Makası (11:00)
    - Perşembe: Taşıt Kredisi (17:00)
    - Cuma: Vadeli Mevduat (21:00)
    - Cumartesi: Banka Dolar & Altın Makası (15:00)
    - Pazar: Vadeli Mevduat & %0 Faiz (21:00)
    """
    weekday = datetime.now(timezone(timedelta(hours=3))).weekday() # 0: Pazartesi ... 6: Pazar
    day_image_plan = {
        0: "ihtiyac",
        1: "bulten",
        2: "tasit",
        3: "konut",
        4: "makas",
        5: "mevduat",
        6: "bulten",
    }
    target_topic = day_image_plan.get(weekday, "ihtiyac")
    return current_topic == target_topic


def build_loan_x_text(offers) -> str:
    import random
    principal_str = format_tl(offers[0].principal)
    months = offers[0].months
    loan_type = offers[0].loan_type
    label_map = {"ihtiyac": "İhtiyaç Kredisi", "konut": "Konut Kredisi", "tasit": "Taşıt Kredisi"}
    lbl = label_map.get(loan_type, "Kredi")

    best = offers[0]
    worst = offers[-1]
    diff = worst.total_repayment - best.total_repayment
    diff_str = format_tl(diff)

    hooks = [
        f"🚨 {principal_str} kredi çeken biri, yanlış bankayı seçerse tam {diff_str} fazla ödüyor!",
        f"Bankaların faiz makası açıldı: {principal_str} {lbl} için bankalar arasında tam {diff_str} fark var.",
        f"Bugün {principal_str} kredi çekecek olsanız hangi bankayı seçerdiniz? En ucuz ile en pahalı arasında {diff_str} oynuyor.",
        f"{best.bank_name} şu an {principal_str}'de en avantajlı konumda. Aradaki fark tam {diff_str}!",
    ]
    hook = random.choice(hooks)

    lines = [
        hook + "\n",
        f"📌 Güncel {lbl} ({months} Ay Vade) En Uygun 3 Banka:",
    ]
    medals = ["🥇", "🥈", "🥉"]
    for idx, o in enumerate(offers[:3]):
        r_s = f"%{o.monthly_rate:.2f}".replace(".", ",")
        lines.append(f"{medals[idx]} {o.bank_name}: Aylık {r_s} | Taksit: {format_tl(o.monthly_installment)} | Toplam: {format_tl(o.total_repayment)}")

    ctas = [
        f"\nSizce mevcut piyasa koşullarında bu aylık taksitler ödenebilir mi? Düşünceleriniz neler?\n\n🧮 Kendi tutarınızı hesaplamak için Telegram: @faizradari",
        f"\nCebinizde kalacak {diff_str} az para değil. Hangi bankayla çalışıyorsunuz?\n\n📊 Canlı tablo takibi için Telegram: @faizradari",
        f"\nDetaylı masraf ve faiz dökümü için Telegram kanalımız: @faizradari",
        f"\nSiz olsaydınız hangi bankayı tercih ederdiniz? 👇\n\nDetaylı bülten: @faizradari (Telegram)",
    ]
    lines.append(random.choice(ctas))
    lines.append("\n#kredi #faiz #para")
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


def build_deposit_x_text(deposits) -> str:
    import random
    principal_str = format_tl(deposits[0].principal)
    days = deposits[0].days
    best = deposits[0]

    hooks = [
        f"Paranızı boşta tutmayın: {principal_str} anapara {days} günde bankalarda net kaç TL kazandırıyor?",
        f"{principal_str} için bankaların mevduat savaşı sürüyor! En yüksek faizle en düşük arasında ciddi fark var.",
        f"Mevduatta en yüksek getiriyi veren banka net {format_tl(best.net_return)} kazanç sunuyor. İşte ilk 3:",
    ]
    hook = random.choice(hooks)

    lines = [
        hook + "\n",
        f"🏆 {days} Günlük Vadeli Mevduat (Stopaj Düşülmüş Net Getiriler):",
    ]
    medals = ["🥇", "🥈", "🥉"]
    for idx, d in enumerate(deposits[:3]):
        r_s = f"%{d.annual_rate:.1f}".replace(".", ",")
        lines.append(f"{medals[idx]} {d.bank_name} ({r_s}): Net +{format_tl(d.net_return)} | Vade Sonu: {format_tl(d.total_balance)}")

    ctas = [
        f"\nSizce mevcut piyasada mevduat faizleri enflasyona karşı koruyor mu?\n\n📲 Günlük oranlar ve %0 faiz fırsatları için Telegram: @faizradari",
        f"\n🔥 Yeni müşterilere özel %0 faizli nakit fırsatları da devam ediyor.\nDetaylı hesaplama ve bülten için profilimizdeki Telegram linki: @faizradari",
        f"\nParanızı şu an mevduatta mı tutuyorsunuz yoksa altın/dövizde mi?\n\n📊 Analizler için Telegram kanalımız: @faizradari",
    ]
    lines.append(random.choice(ctas))
    lines.append("\n#mevduat #faiz #tasarruf")
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


def build_spread_x_text(usd_spreads, gold_spreads) -> str:
    import random
    u_best = usd_spreads[0] if usd_spreads else None
    g_best = gold_spreads[0] if gold_spreads else None

    hooks = [
        "Döviz ve altın alırken bankalara fazladan komisyon ödemeyin! İşte şu an en düşük makası veren bankalar:",
        "Akşam saatlerinde makaslar nasıl açılıyor? Banka banka güncel Dolar ve Gram Altın alış-satış farkları:",
        "Altın ve Dolar işlemlerinde makas aralığı en dar olan bankalar belli oldu 👇",
    ]
    hook = random.choice(hooks)

    lines = [
        hook + "\n",
        "💵 En Düşük Dolar (USD) Makası:",
    ]
    for idx, u in enumerate(usd_spreads[:3]):
        buy_s = f"{u.buy_price:.2f} ₺".replace(".", ",")
        sell_s = f"{u.sell_price:.2f} ₺".replace(".", ",")
        sp_s = f"{u.spread_tl:.2f} ₺ (%{u.spread_pct:.2f})".replace(".", ",")
        lines.append(f"• {u.bank_name}: Alış {buy_s} / Satış {sell_s} (Fark: {sp_s})")

    lines.append("\n🪙 En Düşük Gram Altın Makası:")
    for idx, g in enumerate(gold_spreads[:3]):
        buy_s = f"{g.buy_price:,.0f} ₺".replace(",", ".")
        sell_s = f"{g.sell_price:,.0f} ₺".replace(",", ".")
        sp_s = f"{g.spread_tl:,.0f} ₺ (%{g.spread_pct:.2f})".replace(".", ",")
        lines.append(f"• {g.bank_name}: Alış {buy_s} / Satış {sell_s} (Fark: {sp_s})")

    ctas = [
        "\nSiz altın veya döviz alırken hangi bankayı kullanıyorsunuz? Makasından memnun musunuz?\n\n👉 Anlık takip için Telegram kanalımız: @faizradari",
        "\nMesai saatleri dışında makas farkları ciddi oranda artmaktadır, dikkatli olun.\n\n📊 Canlı oranlar Telegram kanalımızda: @faizradari",
    ]
    lines.append(random.choice(ctas))
    lines.append("\n#altın #dolar #döviz")
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


def _post_animation_to_telegram(animation_path: str, caption: str, target_chat_id: str = CHANNEL_ID, reply_markup: str = None) -> dict:
    with open(animation_path, "rb") as anim_file:
        resp = requests.post(
            f"{API_BASE}/sendAnimation",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": reply_markup or _default_reply_markup(),
            },
            files={"animation": anim_file},
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
        post_to_x(
            alert_img,
            f"🚨 FLAŞ | {a.bank_name} Faiz İndirdi!\n%{a.old_rate:.2f} ➔ %{a.new_rate:.2f}\nDetaylar profilimizdeki linkte: @faizradari #kredi #faiz",
        )

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

    if target_chat_id == CHANNEL_ID:
        attach_img = img_path if should_attach_image_to_x(loan_type) else None
        post_to_x(attach_img, build_loan_x_text(offers))
        post_to_whatsapp(img_path, caption)
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
    if target_chat_id == CHANNEL_ID:
        attach_img = img_path if should_attach_image_to_x("mevduat") else None
        post_to_x(attach_img, build_deposit_x_text(deposits))
        post_to_whatsapp(img_path, caption)
        send_vertical_story_to_admin(img_path, title="GÜNCEL MEVDUAT FAİZLERİ", topic="mevduat")
        public_img_url = "https://raw.githubusercontent.com/mbakan44-web/faizradari/main/latest_vertical_story.png"
        dep_caption = "Bankaların en yüksek mevduat faiz oranları tablosu! 💰 Canlı hesaplama profildeki linkte: @faizradari #mevduat #faiz #para #birikim #ekonomi"
        post_to_buffer_tiktok(public_img_url, dep_caption)
        post_to_buffer_instagram(public_img_url, dep_caption)
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
    if target_chat_id == CHANNEL_ID:
        attach_img = img_path if should_attach_image_to_x("makas") else None
        post_to_x(attach_img, build_spread_x_text(usd_spreads, gold_spreads))
        post_to_whatsapp(img_path, caption)
    return result


def build_briefing_items() -> List[str]:
    """10 maddelik Sabah Raporu içeriklerini canlı scraper verilerinden derler."""
    tickers = fetch_market_tickers()
    dep_offers, zero_offers = get_deposit_offers(500_000, 32)
    iht_offers, _ = get_loan_offers("ihtiyac", 100_000, 12)
    konut_offers, _ = get_loan_offers("konut", 2_000_000, 120)
    tasit_offers, _ = get_loan_offers("tasit", 400_000, 36)
    usd_spreads, _ = get_bank_spread_offers()

    best_dep = dep_offers[0] if dep_offers else None
    best_iht = iht_offers[0] if iht_offers else None
    best_konut = konut_offers[0] if konut_offers else None
    best_tasit = tasit_offers[0] if tasit_offers else None
    best_usd = usd_spreads[0] if usd_spreads else None

    zero_banks = ", ".join([z["bank"] for z in zero_offers[:4]]) if zero_offers else "Enpara, Akbank, Garanti BBVA"

    items = [
        f"En Yüksek Mevduat: {best_dep.bank_name} (%{best_dep.annual_rate:.1f}); 500.000 TL anaparanın 32 günlük net getirisi +{format_tl(best_dep.net_return)}." if best_dep else "En Yüksek Mevduat: Alternatif Bank (%49,0); 500k TL 32 gün net getiri +17.850 TL.",
        f"En Uygun İhtiyaç Kredisi: {best_iht.bank_name} (%{best_iht.monthly_rate:.2f}); 100.000 TL 12 ay vadede taksit {format_tl(best_iht.monthly_installment)}, toplam {format_tl(best_iht.total_repayment)}." if best_iht else "En Uygun İhtiyaç Kredisi: Enpara (%3,49); 100k TL 12 ay taksit 10.850 TL.",
        f"En Uygun Konut Kredisi: {best_konut.bank_name} (%{best_konut.monthly_rate:.2f}); 2.000.000 TL 120 ay vadede taksit {format_tl(best_konut.monthly_installment)} ile piyasa lideri." if best_konut else "En Uygun Konut Kredisi: VakıfBank (%2,84); 2M TL 120 ay taksit 60.100 TL.",
        f"En Uygun Taşıt Kredisi: {best_tasit.bank_name} (%{best_tasit.monthly_rate:.2f}); 400.000 TL 36 ay vadede taksit {format_tl(best_tasit.monthly_installment)} seviyesinde." if best_tasit else "En Uygun Taşıt Kredisi: Akbank (%3,45); 400k TL 36 ay taksit 22.150 TL.",
        f"Yeni Müşteri %0 Faiz: {zero_banks} yeni müşterilere 50.000 TL'ye varan sıfır faizli nakit fırsatı sunuyor.",
        f"Döviz Piyasası: Dolar/TL {tickers.get('USD', '—')}, Euro/TL {tickers.get('EUR', '—')} bandında serbest piyasada işlem görüyor.",
        f"Kıymetli Madenler: Kapalıçarşı serbest piyasada Gram Altın {tickers.get('ALTIN', '—')} seviyesinde seyrediyor.",
        f"Banka Döviz Makası: Dolar alım-satımında en dar makas aralığını {best_usd.bank_name} ({best_usd.spread_tl:.2f} TL fark) ile sunuyor." if best_usd else "Banka Döviz Makası: Dolar alım-satımında en dar makas aralığını Enpara (0,38 TL fark) sunuyor.",
        "TCMB Politika Faizi: Bir Hafta Vadeli Repo Faizi %50,00 seviyesinde sabit; likidite adımları takip ediliyor.",
        "Kredi Kartı Faizleri: Kredi kartı Türk Lirası azami akdi faiz oranı %4,25, gecikme faizi ise %4,55 seviyesinde."
    ]
    return items


def build_briefing_caption(items: List[str] = None) -> str:
    import random
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    hooks = [
        "Piyasalarda güne başlarken faiz, kredi, mevduat ve dövizdeki en kritik 10 gelişmeyi sizler için tek tabloda derledik.",
        "Cebinizi ve yatırımlarınızı doğrudan ilgilendiren günün en önemli 10 finans & faiz başlığını özetledik.",
        "Bankaların güncel oranları, piyasa dengeleri ve öne çıkan fırsatlarla günün kapsamlı finans özeti hazır.",
        "Faiz Radarı masasında bugün: Mevduat getirileri, en uygun krediler ve piyasaların nabzı tek infografikte."
    ]
    hook = random.choice(hooks)
    lines = [
        f"📊 <b>FAİZ RADARI | GÜNÜN FİNANS RAPORU</b> ({now_str})\n",
        f"⚡ {hook}\n",
        "📌 <i>Tüm maddeleri ve detaylı piyasa oranlarını yukarıdaki infografik tablomuzdan inceleyebilirsiniz.</i>\n",
        "⚠️ <i>Bilgilendirme amaçlıdır, yatırım tavsiyesi içermez.</i>\n",
        "🔔 <b>Canlı Takip & Hesaplama:</b> @faizradari"
    ]
    return "\n".join(lines)


def build_briefing_x_text(items: List[str] = None) -> str:
    import random
    now_str = datetime.now().strftime("%d.%m.%Y")
    hooks = [
        f"📊 Günün Finans Raporu ({now_str})\n\nPiyasalarda güne başlarken faiz, kredi, mevduat ve dövizdeki en kritik 10 gelişmeyi sizler için derledik 👇\n\nCanlı oranlar ve hesaplama: @faizradari (Telegram)\n#faiz #kredi #mevduat #dolar #altın",
        f"📊 Günün Finans Raporu ({now_str})\n\nCebinizi ve yatırımlarınızı doğrudan ilgilendiren günün öne çıkan 10 finans başlığı hazır 👇\n\nDetaylı analiz & takip: @faizradari (Telegram)\n#faiz #kredi #mevduat #finans",
        f"📊 Günün Finans Raporu ({now_str})\n\nBankaların güncel faizleri, sıfır faizli fırsatlar ve piyasanın nabzı tek tabloda 👇\n\nCanlı takip ve bot hesaplama: @faizradari (Telegram)\n#faiz #kredi #mevduat"
    ]
    return random.choice(hooks)


def send_briefing_report(target_chat_id: str = CHANNEL_ID) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Günün Finans Raporu (10 Madde) verileri toplanıyor...")
    items = build_briefing_items()
    img_path = render_briefing_table_image(
        items=items,
        title="GÜNÜN FİNANS RAPORU",
        output_path=str(Path(__file__).parent / "latest_briefing_table.png")
    )
    caption = build_briefing_caption(items)
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if result.get("ok"):
        print(f"[BAŞARILI] Sabah Raporu {target_chat_id} hedefine paylaşıldı!")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")

    if target_chat_id == CHANNEL_ID:
        attach_img = img_path if should_attach_image_to_x("bulten") else None
        post_to_x(attach_img, build_briefing_x_text(items))
        post_to_whatsapp(img_path, caption)
        send_vertical_story_to_admin(img_path, title="GÜNÜN FİNANS RAPORU", topic="bulten")
        public_img_url = "https://raw.githubusercontent.com/mbakan44-web/faizradari/main/latest_vertical_story.png"
        tt_caption = "Bankaların güncel faiz oranları ve günün finans raporu! 📊 Canlı hesaplama profildeki linkte: @faizradari #faiz #kredi #mevduat #finans #ekonomi"
        post_to_buffer_tiktok(public_img_url, tt_caption)
        post_to_buffer_instagram(public_img_url, tt_caption)
    return result


def send_weekly_recap_report(target_chat_id: str = CHANNEL_ID) -> dict:
    """Pazar akşamı özel 'Haftanın Finans Karnesi' raporunu üretir ve paylaşır."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Pazar Özel: Haftalık Piyasa Karnesi verileri derleniyor...")
    tickers = fetch_market_tickers()
    dep_offers, zero_offers = get_deposit_offers(500_000, 32)
    iht_offers, _ = get_loan_offers("ihtiyac", 100_000, 12)
    konut_offers, _ = get_loan_offers("konut", 2_000_000, 120)
    usd_spreads, _ = get_bank_spread_offers()

    best_dep = dep_offers[0] if dep_offers else None
    best_loan = iht_offers[0] if iht_offers else None
    best_konut = konut_offers[0] if konut_offers else None
    best_usd = usd_spreads[0] if usd_spreads else None

    recap_data = {
        "best_dep_bank": f"{best_dep.bank_name} (%{best_dep.annual_rate:.1f})" if best_dep else "ON Dijital (%51.0)",
        "dep_net": f"{format_tl(best_dep.net_return)}" if best_dep else "20.121 TL",
        "zero_interest": "50.000 TL sıfır faizli nakit avans fırsatları.",
        "best_loan_bank": f"{best_loan.bank_name} (%{best_loan.monthly_rate:.2f})" if best_loan else "DenizBank (%2.89)",
        "loan_installment": f"{format_tl(best_loan.monthly_installment)}" if best_loan else "10.506 TL",
        "loan_total": f"{format_tl(best_loan.total_repayment)}" if best_loan else "126.641 TL",
        "konut_best": f"{best_konut.bank_name} (%{best_konut.monthly_rate:.2f}) ile {format_tl(best_konut.monthly_installment)} taksit." if best_konut else "QNB (%2.84)",
        "usd_price": f"{tickers.get('USD', '50.19 ₺')}",
        "eur_price": f"{tickers.get('EUR', '56.29 ₺')}",
        "gold_price": f"{tickers.get('ALTIN', '6.658 ₺')}",
        "best_spread": f"{best_usd.bank_name} ({best_usd.spread_tl:.2f} TL)" if best_usd else "Albaraka Türk (0.72 TL)"
    }

    img_path = render_weekly_recap_image(
        recap_data=recap_data,
        output_path=str(Path(__file__).parent / "latest_weekly_recap.png")
    )

    now_str = datetime.now().strftime("%d.%m.%Y")
    caption = (
        f"🏆 <b>FAİZ RADARI | HAFTANIN FİNANS KARNESİ</b> ({now_str})\n\n"
        "⚡ <i>Piyasaların bu haftaki şampiyonları, en yüksek mevduat getirileri, en uygun krediler ve haftalık altın/döviz karnesi hazır.</i>\n\n"
        "📌 <i>Tüm detaylar ve oranlar yukarıdaki infografik karnemizde yer almaktadır.</i>\n\n"
        "⚠️ <i>Bilgilendirme amaçlıdır, yatırım tavsiyesi içermez.</i>\n"
        "🔔 <b>Canlı Takip & Hesaplama:</b> @faizradari"
    )

    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)

    if target_chat_id == CHANNEL_ID:
        x_text = (
            f"🏆 Haftanın Finans & Faiz Karnesi ({now_str})\n\n"
            f"Piyasalarda bu haftanın kazananları, en yüksek mevduat ve en uygun krediler tek tabloda hazır 👇\n\n"
            f"Detaylı inceleme ve canlı oranlar: @faizradari (Telegram)\n"
            f"#faiz #kredi #mevduat #altın"
        )
        post_to_x(img_path, x_text)
        post_to_whatsapp(img_path, caption)
    return result


def send_celebration_report(target_chat_id: str = CHANNEL_ID) -> dict:
    """1.500+ Abone özel kutlama animasyonunu Telegram'a gönderir."""
    gif_path = str(Path(__file__).parent / "faiz_radari_1500_kutlama.gif")
    if not Path(gif_path).exists():
        from create_celebration_gif import generate_celebration_gif
        generate_celebration_gif(gif_path)

    caption = (
        "🎉 <b>1.500+ KİŞİLİK DEV BİR AİLE OLDUK!</b> 🚀\n\n"
        "⚡ <i>Faiz Radarı topluluğu olarak kısa sürede 1.500 değerli üyemizi geride bıraktık!</i>\n\n"
        "🤝 <b>Katkılarınız, güveniniz ve takibiniz için sonsuz teşekkürler.</b>\n\n"
        "📊 <b>Neler Yapıyoruz?</b>\n"
        "• Tüm bankaların güncel mevduat & kredi oranlarını anlık radarımıza alıyoruz.\n"
        "• Masrafsız, gizli kesintisiz en avantajlı finans fırsatlarını tarafsız sunuyoruz.\n"
        "• Dolar, altın ve makas analizleriyle paranızın değerini korumanıza destek oluyoruz.\n\n"
        "🔔 <i>Birlikte daha güçlüyüz. Canlı takip ve hesaplama için dostlarınızla paylaşmayı unutmayın:</i>\n"
        "👉 <b>@faizradari</b>"
    )
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    res = _post_animation_to_telegram(gif_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if res.get("ok"):
        print(f"[BAŞARILI] 1500 Kutlama GIF'i {target_chat_id} hedefine paylaşıldı!")
    else:
        print(f"[HATA] Telegram kutlama gönderimi başarısız: {res}")
    return res


def send_breaking_news_report(
    headline: str,
    details: str,
    category: str = "TCMB FAİZ KARARI",
    target_chat_id: str = CHANNEL_ID
) -> dict:
    """Flaş haber, TCMB faiz kararı veya önemli piyasa gelişmelerini anında paylaşır."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] FLAŞ HABER oluşturuluyor: {headline}...")
    img_path = render_breaking_news_image(
        headline=headline,
        details=details,
        category=category,
        output_path=str(Path(__file__).parent / "latest_breaking_news.png")
    )

    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    caption = (
        f"🚨 <b>FAİZ RADARI | FLAŞ GELİŞME</b> ({now_str})\n\n"
        f"📌 <b>{headline}</b>\n\n"
        f"📝 <b>Özet & Piyasa Etkisi:</b>\n{details}\n\n"
        "⚠️ <i>Kamuya açık resmi verilerden derlenmiştir, yatırım tavsiyesi içermez.</i>\n"
        "🔔 <b>Anlık Piyasa Bildirimleri:</b> @faizradari"
    )

    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)

    if target_chat_id == CHANNEL_ID:
        x_text = (
            f"🚨 FLAŞ | {headline}\n\n"
            f"{details[:160]}...\n\n"
            f"Detaylar ve canlı oranlar: @faizradari (Telegram)\n#faiz #tcmb #ekonomi"
        )
        post_to_x(img_path, x_text)
        post_to_whatsapp(img_path, caption)
    return result


def send_celebration_report(target_chat_id: str = CHANNEL_ID) -> dict:
    """1.500+ Abone özel kutlama animasyonunu Telegram'a gönderir."""
    gif_path = str(Path(__file__).parent / "faiz_radari_1500_kutlama.gif")
    if not Path(gif_path).exists():
        from create_celebration_gif import generate_celebration_gif
        generate_celebration_gif(gif_path)

    caption = (
        "🎉 <b>1.500+ KİŞİLİK DEV BİR AİLE OLDUK!</b> 🚀\n\n"
        "⚡ <i>Faiz Radarı topluluğu olarak kısa sürede 1.500 değerli üyemizi geride bıraktık!</i>\n\n"
        "🤝 <b>Katkılarınız, güveniniz ve takibiniz için sonsuz teşekkürler.</b>\n\n"
        "📊 <b>Neler Yapıyoruz?</b>\n"
        "• Tüm bankaların güncel mevduat & kredi oranlarını anlık radarımıza alıyoruz.\n"
        "• Masrafsız, gizli kesintisiz en avantajlı finans fırsatlarını tarafsız sunuyoruz.\n"
        "• Dolar, altın ve makas analizleriyle paranızın değerini korumanıza destek oluyoruz.\n\n"
        "🔔 <i>Birlikte daha güçlüyüz. Canlı takip ve hesaplama için dostlarınızla paylaşmayı unutmayın:</i>\n"
        "👉 <b>@faizradari</b>"
    )
    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    res = _post_animation_to_telegram(gif_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if res.get("ok"):
        print(f"[BAŞARILI] 1500 Kutlama GIF'i {target_chat_id} hedefine paylaşıldı!")
    else:
        print(f"[HATA] Telegram kutlama gönderimi başarısız: {res}")
    return res


def check_and_set_dispatch_lock(slot_topic: str) -> bool:
    """
    Mükerrer paylaşım koruması:
    Aynı gün ve saat içinde bu bülten zaten paylaşıldıysa True (kilitli / mükerrer) döner.
    İlk kez çalıştırılıyorsa kilidi günceller ve False döner (paylaşıma izin verir).
    """
    try:
        from scraper import _load_full_cache, _save_full_cache
        cache = _load_full_cache()
        now = datetime.now(timezone(timedelta(hours=3)))
        current_slot = f"{now.strftime('%Y-%m-%d_%H')}_{slot_topic}"
        last_slot = cache.get("last_dispatched_slot")

        if last_slot == current_slot:
            print(f"[MÜKERRER ENGELLEME] '{current_slot}' bülteni zaten az önce paylaşıldı. İkinci gönderim iptal edildi!")
            return True

        cache["last_dispatched_slot"] = current_slot
        cache["last_dispatched_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        _save_full_cache(cache)
        return False
    except Exception as e:
        print(f"[UYARI] Kilit kontrol hatası: {e}")
        return False


def run_scheduler():
    print("=================================================================")
    print(" Faiz Radarı Tam Kapsamlı Yayın Akışı (Telegram + X + WhatsApp) Başlatıldı")
    print("=================================================================")
    configure_bot_profile()

    schedule.every().day.at("09:00").do(send_loan_report, loan_type="ihtiyac", principal=100_000, months=12)
    schedule.every().day.at("11:00").do(send_briefing_report)
    schedule.every().day.at("13:00").do(send_loan_report, loan_type="tasit", principal=400_000, months=36)
    schedule.every().day.at("15:00").do(send_loan_report, loan_type="konut", principal=2_000_000, months=120)
    schedule.every().day.at("17:00").do(send_spread_report)
    schedule.every().day.at("19:00").do(send_deposit_report, principal=500_000, days=32)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--set-logo" in sys.argv:
        set_channel_logo()
    if "--set-webhook" in sys.argv:
        idx = sys.argv.index("--set-webhook")
        if idx + 1 < len(sys.argv):
            wh_url = sys.argv[idx + 1].strip()
            r = requests.post(f"{API_BASE}/setWebhook", json={"url": wh_url}, timeout=10).json()
            print("Webhook durumu:", r)
    elif "--test-x" in sys.argv:
        tickers = fetch_market_tickers()
        offers, _ = get_loan_offers("ihtiyac", 100_000, 12)
        img_p = render_loan_table_image(offers, tickers, str(Path(__file__).parent / "latest_loan_table.png"))
        post_to_x(img_p, build_loan_x_text(offers))
    elif "--bulten" in sys.argv or "--sabah" in sys.argv:
        send_briefing_report()
    elif "--spread" in sys.argv:
        send_spread_report()
    elif "--konut" in sys.argv:
        send_loan_report(loan_type="konut", principal=2_000_000, months=120)
    elif "--tasit" in sys.argv:
        send_loan_report(loan_type="tasit", principal=400_000, months=36)
    elif "--mevduat" in sys.argv:
        send_deposit_report(principal=500_000, days=32)
    elif "--haftalik" in sys.argv or "--karne" in sys.argv:
        send_weekly_recap_report()
    elif "--tiktok" in sys.argv or "--story" in sys.argv or "--instagram" in sys.argv or "--buffer" in sys.argv:
        p = str(Path(__file__).parent / "latest_briefing_table.png")
        if not Path(p).exists():
            p = str(Path(__file__).parent / "latest_deposit_table.png")
        send_vertical_story_to_admin(p, title="GÜNÜN FİNANS RAPORU", topic="bulten")
        public_img_url = "https://raw.githubusercontent.com/mbakan44-web/faizradari/main/latest_vertical_story.png"
        tt_caption = "Bankaların güncel faiz oranları tablosu! 📊 Canlı hesaplama profildeki linkte: @faizradari #faiz #kredi #mevduat #finans #ekonomi"
        post_to_buffer_tiktok(public_img_url, tt_caption)
        post_to_buffer_instagram(public_img_url, tt_caption)
    elif "--haber" in sys.argv:
        headline = "TCMB Politika Faizini Sabit Bıraktı"
        details = "Merkez Bankası piyasa beklentileri doğrultusunda politika faizini sabit tuttu. Sıkı para politikası duruşu korunuyor."
        category = "MERKEZ BANKASI FAİZ KARARI"
        for arg in sys.argv:
            if arg.startswith("--haber="):
                headline = arg.split("=", 1)[1].strip()
            elif arg.startswith("--detay="):
                details = arg.split("=", 1)[1].strip()
            elif arg.startswith("--kategori="):
                category = arg.split("=", 1)[1].strip()
        send_breaking_news_report(headline=headline, details=details, category=category)
    elif "--kutlama" in sys.argv:
        target = CHANNEL_ID if "--kanal" in sys.argv else ADMIN_CHAT_ID
        send_celebration_report(target_chat_id=target)
    elif "--auto-slot" in sys.argv:
        target_topic = None
        for arg in sys.argv:
            if arg.startswith("--topic="):
                target_topic = arg.split("=")[1].strip().lower()

        now_tr = datetime.now(timezone(timedelta(hours=3)))
        tr_hour = now_tr.hour
        tr_minute = now_tr.minute
        is_force = "--force" in sys.argv

        # 1. Gece Sessiz Saatler Koruma Kilidi (20:00 - 08:30 arası ASLA otomatik paylaşım yapılmaz)
        if not is_force and (tr_hour >= 20 or tr_hour < 8 or (tr_hour == 8 and tr_minute < 30)):
            print(f"[GECE SESSİZ SAAT KORUMASI] TR Saati {tr_hour:02d}:{tr_minute:02d}. Gece saatlerinde (20:00 - 08:30) bildirim/paylaşım engellendi.")
            sys.exit(0)

        # 2. Otomatik slot tespiti (Yalnızca 6 resmi yayın aralığı)
        if not target_topic or target_topic == "auto":
            if tr_hour in (8, 9):
                target_topic = "ihtiyac"
            elif tr_hour in (10, 11):
                target_topic = "bulten"
            elif tr_hour in (12, 13):
                target_topic = "tasit"
            elif tr_hour in (14, 15):
                target_topic = "konut"
            elif tr_hour in (16, 17):
                target_topic = "makas"
            elif tr_hour in (18, 19):
                # Pazar günü 19:00'da özel Haftalık Piyasa Karnesi yayınlanır
                target_topic = "haftalik" if now_tr.weekday() == 6 else "mevduat"
            else:
                print(f"[PLAN DIŞI SAAT] TR Saati {tr_hour:02d}:{tr_minute:02d} planlı 6 yayın slotuna denk gelmiyor. Paylaşım yapılmadı.")
                sys.exit(0)

        # Mükerrer Gönderim Kilidi (GitHub Cron + GAS çift tetiklemesini engeller)
        if check_and_set_dispatch_lock(target_topic):
            print(f"[BİLGİ] {target_topic.upper()} bülteni zaten yayınlandı, işlem güvenle sonlandırıldı.")
            sys.exit(0)

        if target_topic == "ihtiyac":
            send_loan_report(loan_type="ihtiyac", principal=100_000, months=12)
        elif target_topic in ("bulten", "sabah"):
            send_briefing_report()
        elif target_topic == "tasit":
            send_loan_report(loan_type="tasit", principal=400_000, months=36)
        elif target_topic == "konut":
            send_loan_report(loan_type="konut", principal=2_000_000, months=120)
        elif target_topic == "makas":
            send_spread_report()
        elif target_topic == "haftalik":
            send_weekly_recap_report()
        elif target_topic == "mevduat":
            send_deposit_report(principal=500_000, days=32)
    elif "--schedule" in sys.argv:
        run_scheduler()
    else:
        send_loan_report(loan_type="ihtiyac", principal=100_000, months=12)
