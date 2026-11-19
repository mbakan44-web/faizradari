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

from calculator import format_tl, RateDropAlert
from scraper import (
    fetch_market_tickers,
    get_loan_offers,
    get_deposit_offers,
    get_bank_spread_offers,
    check_all_loan_rates_for_changes,
    has_rates_changed_since_last_publish,
    mark_rates_published,
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
    render_viral_insight_image,
    render_animated_reel_video,
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


def post_to_buffer_tiktok(media_url: str, caption: str, is_video: bool = False) -> bool:
    """
    Buffer GraphQL API üzerinden TikTok (@faizradari) hesabına anında otomatik paylaşım yapar.
    is_video=True olduğunda müzikli MP4 video olarak iletir, aksi halde dikey görsel olarak paylaşır.
    """
    if not (BUFFER_API_KEY and BUFFER_TIKTOK_CHANNEL_ID and media_url):
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
        asset_field = "video" if is_video else "image"
        variables = {
            "input": {
                "channelId": BUFFER_TIKTOK_CHANNEL_ID,
                "text": caption,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "needsApproval": False,
                "assets": [
                    {
                        asset_field: {
                            "url": media_url
                        }
                    }
                ]
            }
        }
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }
        res = requests.post("https://api.buffer.com", json={"query": mutation, "variables": variables}, headers=headers, timeout=35).json()
        post_data = res.get("data", {}).get("createPost", {})
        if "post" in post_data:
            print(f"[BAŞARILI] Gönderi Buffer üzerinden TikTok hesabına iletildi! (Post ID: {post_data['post']['id']} - {'Video' if is_video else 'Görsel'})")
            return True
        else:
            print(f"[UYARI] Buffer TikTok gönderim hatası: {post_data.get('message', res)}")
            # Video gönderimi başarısız olduysa ve görsel adresi varsa görsel olarak yedekle
            if is_video:
                img_fallback = media_url.replace(".mp4", ".png")
                print(f"[BİLGİ] TikTok video gönderilemedi, görsel yedeğe dönülüyor...")
                return post_to_buffer_tiktok(img_fallback, caption, is_video=False)
            return False
    except Exception as e:
        print(f"[UYARI] Buffer API hatası: {e}")
        return False


def post_to_buffer_instagram(media_url: str, caption: str, is_video: bool = True) -> bool:
    """
    Buffer GraphQL API üzerinden Instagram (@faizradari) hesabına anında otomatik paylaşım yapar.
    is_video=True olduğunda sesli Instagram Reel olarak yayınlar, aksi halde feed görseli olarak iletir.
    """
    if not (BUFFER_API_KEY and BUFFER_INSTAGRAM_CHANNEL_ID and media_url):
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
        asset_field = "video" if is_video else "image"
        post_type = "reel" if is_video else "post"
        variables = {
            "input": {
                "channelId": BUFFER_INSTAGRAM_CHANNEL_ID,
                "text": caption,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "needsApproval": False,
                "metadata": {
                    "instagram": {
                        "type": post_type,
                        "shouldShareToFeed": True
                    }
                },
                "assets": [
                    {
                        asset_field: {
                            "url": media_url
                        }
                    }
                ]
            }
        }
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json"
        }
        res = requests.post("https://api.buffer.com", json={"query": mutation, "variables": variables}, headers=headers, timeout=35).json()
        post_data = res.get("data", {}).get("createPost", {})
        if "post" in post_data:
            print(f"[BAŞARILI] Gönderi Buffer üzerinden Instagram hesabına iletildi! (Post ID: {post_data['post']['id']} - {'Reel' if is_video else 'Görsel'})")
            return True
        else:
            print(f"[UYARI] Buffer Instagram gönderim hatası: {post_data.get('message', res)}")
            if is_video:
                img_fallback = media_url.replace(".mp4", ".png")
                print(f"[BİLGİ] Instagram Reel gönderilemedi, görsel yedeğe dönülüyor...")
                return post_to_buffer_instagram(img_fallback, caption, is_video=False)
            return False
    except Exception as e:
        print(f"[UYARI] Buffer Instagram API hatası: {e}")
        return False


def build_social_hook_caption(topic: str, custom_summary: str = "") -> tuple[str, str]:
    """
    Instagram Reels için sade, spam içermeyen, kaydetmeye (Save) ve yoruma yönlendiren
    doğal finans açıklaması üretir (En fazla 4-5 hedefli hashtag, dış platform spamı yok).
    """
    if custom_summary:
        return custom_summary, ""

    hooks = {
        "ihtiyac": (
            "100.000 TL ihtiyaç kredisinde bankalar arasındaki faiz farkı cebinizden binlerce lira çıkmasına neden olabiliyor.\n\n"
            "Kredi çekmeden önce güncel listeyi kaydetmeyi unutmayın.\n\n"
            "Sizce bu faiz oranları önümüzdeki aylarda düşer mi? Yorumlarda konuşalım 👇\n\n"
            "#ihtiyackredisi #kredi #faiz #finans #ekonomi",
            ""
        ),
        "tasit": (
            "Araç alacaklar dikkat: Taşıt kredisinde bankalar arasındaki taksit farkı ciddi boyutlara ulaştı.\n\n"
            "Araba planı yapan arkadaşlarınızla paylaşın ve listeyi kaydedin.\n\n"
            "Bu oranlarla krediyle araç almak sizce mantıklı mı? 👇\n\n"
            "#tasitkredisi #araba #otomobil #finans #ekonomi",
            ""
        ),
        "konut": (
            "2.000.000 TL konut kredisinde en uygun banka ile diğerleri arasında yüz binlerce TL toplam geri ödeme farkı oluşuyor.\n\n"
            "Ev alma planınız varsa bu tabloyu kaydedin.\n\n"
            "Sizce bu taksitlerle ev almak mı, yoksa kirada kalıp birikim yapmak mı daha mantıklı? 👇\n\n"
            "#konutkredisi #emlak #ev #faiz #ekonomi",
            ""
        ),
        "mevduat": (
            "Vadeli mevduatta bankaların güncel oranları ve %17,5 stopaj sonrası 32 günlük net kazançlar belli oldu.\n\n"
            "Paranızı değerlendirmeden önce bu listeyi kaydedin.\n\n"
            "Siz birikiminizi mevduatta mı, altında mı yoksa dövizde mi tutuyorsunuz? 👇\n\n"
            "#mevduat #faiz #birikim #yatirim #finans",
            ""
        ),
        "makas": (
            "Dolar ve Gram Altın alım-satımında bankaların uyguladığı güncel makas aralıklarını tek ekranda karşılaştırdık.\n\n"
            "İşlem yapmadan önce farkları görmek için kaydedin.\n\n"
            "Altın ve döviz alırken hangi bankanın makasından memnunsunuz? 👇\n\n"
            "#altin #dolar #doviz #ekonomi #finans",
            ""
        ),
        "analiz": (
            "Günün cep hesabı hazır! Güncel banka oranları ve canlı piyasa verileriyle gerçek maliyet tablosu.\n\n"
            "Lazım olduğunda bakmak için kaydedin ve fikrinizi yorumlara yazın 👇\n\n"
            "#finans #ekonomi #faiz #yatirim #tasarruf",
            ""
        ),
        "bulten": (
            "Günün öne çıkan finans, kredi, mevduat ve piyasa verilerini tek ekranda özetledik.\n\n"
            "Piyasaların yönü sizce ne olur? Yorumlarda buluşalım 👇\n\n"
            "#ekonomi #finans #faiz #altin #dolar",
            ""
        ),
    }
    return hooks.get(topic, hooks["analiz"])


def dispatch_to_buffer_omnichannel(
    square_img_path: str,
    title: str,
    topic: str = "ihtiyac",
    reel_data: dict = None,
) -> None:
    """
    Instagram Reels için:
    1. Günlük spam kotasını kontrol eder (Günde EN FAZLA 2 yüksek kaliteli Reels).
    2. reel_data verilmişse %100 native 1080x1920 ANİMASYONLU Reels videosu üretir (kinetik kartlar + müzik).
    3. GitHub Actions ortamındaysa medya + rates_cache.json dosyalarını güvenle CDN'e pushlar.
    4. Instagram'a sesli animasyonlu Reels olarak yayınlar (TikTok ihtar kilidi kapalı kalır).
    """
    try:
        from scraper import _load_full_cache, _save_full_cache
        from image_generator import render_vertical_story_image, render_vertical_story_video
        import time

        now_tr = datetime.now(timezone(timedelta(hours=3)))
        today_str = now_tr.strftime("%Y-%m-%d")

        cache = _load_full_cache()
        ig_daily = cache.get("daily_instagram_posts", {})
        today_ig_list = ig_daily.get(today_str, [])

        # Spam koruması: Instagram'da günde en fazla 2 kaliteli Reels ve aynı konu 2 kez asla atılmaz!
        if topic in today_ig_list:
            print(f"[INSTAGRAM KORUMASI] '{topic}' bugün zaten Instagram'da paylaşıldı. Atlandı.")
            return
        if len(today_ig_list) >= 2:
            print(f"[INSTAGRAM GÜNLÜK LİMİT] Bugün ({today_str}) zaten {len(today_ig_list)} Reels paylaşıldı. Kalite/algoritma koruması için sınırlandı.")
            return

        v_path = str(Path(__file__).parent / "latest_vertical_story.png")
        video_path = str(Path(__file__).parent / "latest_story_video.mp4")

        # 1. Native Animasyonlu Reels (öncelikli) veya yedek temiz dikey video
        if reel_data:
            render_animated_reel_video(
                tag=reel_data.get("tag", "CANLI PİYASA VERİSİ"),
                hook_line1=reel_data.get("hook_line1", title),
                hook_line2=reel_data.get("hook_line2", "GÜNCEL ORANLAR"),
                subtitle=reel_data.get("subtitle", "Bankaların güncel karşılaştırması"),
                rows=reel_data.get("rows", []),
                cta_text=reel_data.get("cta_text", "KAYDET — Karar vermeden önce lazım olur!"),
                question_text=reel_data.get("question_text", "Sence hangi banka daha avantajlı? Yorumlara yaz!"),
                output_video_path=video_path,
                output_cover_path=v_path,
                duration_sec=8.0,
                fps=15,
            )
        else:
            render_vertical_story_image(square_image_path=square_img_path, title=title, output_path=v_path)
            try:
                render_vertical_story_video(v_image_path=v_path, output_path=video_path, duration=8)
            except Exception as ve:
                print(f"[UYARI] Dikey video oluşturulamadı, görsele devam edilecek: {ve}")

        # Önbelleği paylaşım öncesi güncelle (tekrar gönderimi önler)
        today_ig_list.append(topic)
        ig_daily = {k: v for k, v in ig_daily.items() if k >= (now_tr - timedelta(days=7)).strftime("%Y-%m-%d")}
        ig_daily[today_str] = today_ig_list
        cache["daily_instagram_posts"] = ig_daily
        _save_full_cache(cache)

        # 2. GitHub Actions ortamındaysa CDN'e pushla
        if os.getenv("GITHUB_ACTIONS") == "true":
            try:
                import subprocess
                subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
                subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
                subprocess.run(["git", "add", "rates_cache.json", "latest_vertical_story.png", "latest_story_video.mp4"], check=False)
                subprocess.run(["git", "commit", "-m", "Auto-update live animated Reel & cache for Buffer CDN"], check=False)
                subprocess.run(["git", "pull", "--rebase"], check=False)
                subprocess.run(["git", "push"], check=False)
                time.sleep(3)
            except Exception as pe:
                print(f"[UYARI] Buffer öncesi medya pushlanamadı: {pe}")

        timestamp = int(time.time())
        public_video_url = f"https://raw.githubusercontent.com/mbakan44-web/faizradari/main/latest_story_video.mp4?v={timestamp}"

        custom_cap = reel_data.get("caption", "") if reel_data else ""
        caption, _ = build_social_hook_caption(topic, custom_summary=custom_cap)

        # TikTok güvenlik kilidi (ihtar koruması)
        enable_tiktok = os.getenv("ENABLE_TIKTOK_POSTING", "false").lower() == "true"
        if enable_tiktok:
            post_to_buffer_tiktok(public_video_url, caption, is_video=True)
        else:
            print("[GÜVENLİK KİLİDİ] TikTok otomatik gönderimi hesap güvenliği için kapalı.")

        # Instagram: Animasyonlu sesli Reels olarak paylaş
        post_to_buffer_instagram(public_video_url, caption, is_video=True)
    except Exception as e:
        print(f"[UYARI] Buffer omnichannel gönderim hatası: {e}")


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
    # Günde 2-3 yüksek kaliteli, taze görselli paylaşım (algoritmik erişim için görsel şart!)
    return True


def build_loan_x_text(offers, changed_banks: List[str] = None) -> str:
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

    if changed_banks:
        b_str = ", ".join(changed_banks[:3])
        hook = f"{lbl} oranları güncellendi ({b_str}). {principal_str} için bankalar arasındaki maliyet farkı tam {diff_str}."
    else:
        hooks = [
            f"{principal_str} {lbl.lower()} çeken biri, yanlış bankayı seçerse tam {diff_str} fazla ödüyor.",
            f"Bankalar arasındaki faiz farkı açıldı: {principal_str} {lbl.lower()} toplam maliyetinde {diff_str} oynuyor.",
            f"{principal_str} ({months} ay) kredide en ucuz ile en pahalı banka arasında tam {diff_str} fark var.",
        ]
        hook = random.choice(hooks)

    lines = [
        hook + "\n",
        f"Güncel en uygun 3 banka ({months} ay vade):",
    ]
    for o in offers[:3]:
        r_s = f"%{o.monthly_rate:.2f}".replace(".", ",")
        lines.append(f"• {o.bank_name}: {r_s} | Taksit: {format_tl(o.monthly_installment)}")

    questions = [
        "\nBu aylık taksitlerle kredi çekmek sizce mantıklı mı?",
        f"\nCebinizde kalacak {diff_str} az para değil. Siz hangi bankayla çalışıyorsunuz?",
        "\nSizce önümüzdeki aylarda kredi faizleri düşer mi, yoksa bu bantta mı kalır?",
    ]
    lines.append(random.choice(questions))
    return "\n".join(lines)


def build_deposit_caption(deposits, zero_offers, tickers) -> str:
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    principal_str = format_tl(deposits[0].principal)
    days = deposits[0].days

    lines = [
        f"💰 <b>FAİZ RADARI | VADELİ MEVDUAT & %0 FAİZ FIRSATLARI</b> ({now_str})",
        f"📈 <b>{principal_str} Anaparanın {days} Günlük Net Mevduat Getirisi (%17,5 Stopaj Düşülmüş):</b>",
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


def build_deposit_x_text(deposits, changed_banks: List[str] = None) -> str:
    import random
    principal_str = format_tl(deposits[0].principal)
    days = deposits[0].days
    best = deposits[0]

    if changed_banks:
        b_str = ", ".join(changed_banks[:3])
        hook = f"Mevduat faizleri güncellendi ({b_str}). {principal_str} anaparanın {days} günlük en yüksek net getirisi {format_tl(best.net_return)} oldu."
    else:
        hooks = [
            f"{principal_str} anapara {days} günde bankalarda (%17,5 stopaj sonrası) net kaç TL kazandırıyor?",
            f"Vadeli mevduatta güncel oranlar: {principal_str} için en yüksek net getiri {format_tl(best.net_return)} seviyesinde.",
        ]
        hook = random.choice(hooks)

    lines = [
        hook + "\n",
        f"Güncel en yüksek {days} günlük net kazançlar:",
    ]
    for d in deposits[:3]:
        r_s = f"%{d.annual_rate:.1f}".replace(".", ",")
        lines.append(f"• {d.bank_name} ({r_s}): Net +{format_tl(d.net_return)}")

    questions = [
        "\nSizce mevcut mevduat getirileri enflasyona karşı koruyor mu?",
        "\nBugün nakdiniz olsa mevduatta mı tutardınız, yoksa altın/dövizde mi?",
    ]
    lines.append(random.choice(questions))
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
    g_best = gold_spreads[0] if gold_spreads else None
    g_worst = gold_spreads[-1] if gold_spreads else None

    if g_best and g_worst and (g_worst.spread_tl - g_best.spread_tl) >= 20:
        fark_100g = format_tl((g_worst.spread_tl - g_best.spread_tl) * 100)
        hook = f"Bugün bankadan 100 gram altın alırken yanlış bankayı seçerseniz sadece makas farkından anında {fark_100g} kaybediyorsunuz."
    else:
        hooks = [
            "Piyasa kapanışında Dolar ve Gram Altın makasları belli oldu. En dar makası sunan bankalar:",
            "Döviz ve altın alırken bankalara gereksiz makas ödemeyin. Günün en düşük alış-satış farkları:",
        ]
        hook = random.choice(hooks)

    lines = [
        hook + "\n",
        "En düşük Dolar makası:",
    ]
    for u in usd_spreads[:3]:
        sp_s = f"{u.spread_tl:.2f} TL".replace(".", ",")
        lines.append(f"• {u.bank_name}: {sp_s} fark")

    lines.append("\nEn düşük Gram Altın makası:")
    for g in gold_spreads[:3]:
        sp_s = f"{g.spread_tl:,.0f} TL".replace(",", ".")
        lines.append(f"• {g.bank_name}: {sp_s} fark")

    lines.append("\nSiz döviz ve altın işlemlerinde hangi bankayı kullanıyorsunuz?")
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


def dispatch_rate_change_alerts(alerts: List[RateDropAlert], target_chat_id: str = CHANNEL_ID) -> None:
    """
    Banka faiz indirimi alarmlarını anında tüm kanallara (Telegram, X, WhatsApp) duyurur.
    - Faiz artışları KESİNLİKLE paylaşılmaz.
    - Aynı banka + kredi türü + aynı (veya daha yüksek) oran için 7 gün içinde ASLA mükerrer alarm atılmaz!
    """
    drop_alerts = [a for a in alerts if a.is_drop and (a.old_rate - a.new_rate) >= 0.05]
    if not drop_alerts:
        return

    try:
        from scraper import _load_full_cache, _save_full_cache
        cache = _load_full_cache()
    except Exception:
        cache = {}

    now_tr = datetime.now(timezone(timedelta(hours=3)))
    today_str = now_tr.strftime("%Y-%m-%d")
    cutoff_str = (now_tr - timedelta(days=7)).strftime("%Y-%m-%d")

    last_alerted = cache.get("last_alerted_rates", {})
    unseen_alerts: List[RateDropAlert] = []

    for a in drop_alerts:
        key = f"{a.bank_name}_{a.loan_type}"
        prev_rec = last_alerted.get(key)
        new_r = round(float(a.new_rate), 2)
        # Son 7 gün içinde bu banka için aynı veya daha düşük bir oran zaten duyurulduysa ENGELLE!
        if prev_rec and prev_rec.get("date", "") >= cutoff_str and float(prev_rec.get("rate", 99.0)) <= new_r:
            print(f"[ALARM ENGELLEME] {a.bank_name} ({a.loan_type}) %{new_r:.2f} indirimi daha önce ({prev_rec.get('date')}) duyuruldu. Mükerrer alarm iptal!")
            continue
        unseen_alerts.append(a)
        last_alerted[key] = {"rate": new_r, "date": today_str}

    if not unseen_alerts:
        return

    # Önbelleği gönderimden ÖNCE kaydet (çökme/çift tetikleme durumunda tekrar atılmasını engeller)
    cache["last_alerted_rates"] = last_alerted
    try:
        _save_full_cache(cache)
    except Exception:
        pass

    alert_img = render_rate_drop_alert_image(
        alerts=unseen_alerts,
        output_path=str(Path(__file__).parent / "latest_alert.png"),
    )

    loan_names = {"ihtiyac": "İhtiyaç Kredisi", "tasit": "Taşıt Kredisi", "konut": "Konut Kredisi"}

    for a in unseen_alerts:
        lname = loan_names.get(a.loan_type, "Kredi")
        old_s = f"%{a.old_rate:.2f}".replace(".", ",")
        new_s = f"%{a.new_rate:.2f}".replace(".", ",")

        caption = (
            f"🚨 <b>FAİZ RADARI | FAİZ İNDİRİMİ ALARMI</b>\n\n"
            f"📉 <b>{a.bank_name.upper()} {lname.upper()} FAİZİNİ DÜŞÜRDÜ!</b>\n\n"
            f"📊 <b>Eski Oran:</b> {old_s} ➔ <b>Yeni Oran:</b> <b>{new_s}</b>\n"
            f"💰 <b>{format_tl(a.principal)} ({a.months} Ay)</b> kredide toplam geri ödeme "
            f"<b>{format_tl(a.total_savings)} azaldı!</b> (Yeni Taksit: {format_tl(a.new_offer.monthly_installment)})\n\n"
            f"⚠️ <i>Bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.</i>\n"
            f"🔔 <b>Anlık Takip:</b> @faizradari"
        )

        _post_photo_to_telegram(alert_img, caption, target_chat_id=target_chat_id)
        if target_chat_id == CHANNEL_ID:
            x_alert = (
                f"{a.bank_name}, {lname.lower()} faiz oranını {old_s} seviyesinden {new_s} seviyesine düşürdü.\n\n"
                f"{format_tl(a.principal)} ({a.months} ay) kredide toplam geri ödeme {format_tl(a.total_savings)} azaldı "
                f"(Yeni taksit: {format_tl(a.new_offer.monthly_installment)}).\n\n"
                f"Diğer bankalardan da indirim gelir mi?"
            )
            post_to_x(alert_img, x_alert)
            post_to_whatsapp(alert_img, caption)


def _tr_short_date() -> str:
    aylar = ["", "OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
    now_tr = datetime.now(timezone(timedelta(hours=3)))
    return f"{now_tr.day} {aylar[now_tr.month]}"


def send_loan_report(
    loan_type: str = "ihtiyac",
    principal: float = 100_000,
    months: int = 12,
    target_chat_id: str = CHANNEL_ID,
    force_publish: bool = False,
) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {loan_type.upper()} kredisi verileri çekiliyor ({format_tl(principal)} / {months} Ay)...")
    tickers = fetch_market_tickers()
    offers, alerts = get_loan_offers(loan_type=loan_type, principal=principal, months=months)

    if alerts and target_chat_id == CHANNEL_ID:
        dispatch_rate_change_alerts(alerts, target_chat_id=target_chat_id)

    changed_banks: List[str] = []
    if target_chat_id == CHANNEL_ID and not force_publish:
        changed, changed_banks = has_rates_changed_since_last_publish(loan_type, offers)
        if not changed:
            print(f"[ORAN DEĞİŞİKLİĞİ YOK] {loan_type.upper()} faiz oranlarında değişiklik yok. Mükerrer paylaşım engellendi!")
            return {"ok": True, "skipped": True, "reason": "no_rate_change"}

    img_path = render_loan_table_image(
        offers=offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_loan_table.png"),
    )
    caption = build_loan_caption(offers, tickers)
    if changed_banks:
        caption = f"🔄 <b>ORAN GÜNCELLEMESİ ({', '.join(changed_banks[:3])})</b>\n" + caption

    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if result.get("ok"):
        print(f"[BAŞARILI] {loan_type.upper()} Tablosu {target_chat_id} hedefine paylaşıldı!")
    else:
        print(f"[HATA] Telegram gönderimi başarısız: {result}")

    if target_chat_id == CHANNEL_ID:
        mark_rates_published(loan_type, offers)
        attach_img = img_path if should_attach_image_to_x(loan_type) else None
        post_to_x(attach_img, build_loan_x_text(offers, changed_banks=changed_banks))
        post_to_whatsapp(img_path, caption)

        # Native 9:16 Animasyonlu Instagram Reels verisi
        label_map = {"ihtiyac": "İHTİYAÇ KREDİSİ", "konut": "KONUT KREDİSİ", "tasit": "TAŞIT KREDİSİ"}
        lbl = label_map.get(loan_type, "KREDİ")
        diff_tl = format_tl(offers[-1].total_repayment - offers[0].total_repayment) if len(offers) >= 2 else ""
        reel_rows = [
            {
                "rank": str(i + 1),
                "title": o.bank_name,
                "sub": f"Taksit: {format_tl(o.monthly_installment)}",
                "value": f"%{o.monthly_rate:.2f}".replace(".", ","),
                "highlight": i == 0,
            }
            for i, o in enumerate(offers[:5])
        ]
        reel_data = {
            "tag": f"GÜNCEL {lbl} • {_tr_short_date()}",
            "hook_line1": f"{format_tl(principal)} KREDİDE",
            "hook_line2": f"{diff_tl} FARK VAR!" if diff_tl else "ORANLAR GÜNCELLENDİ!",
            "subtitle": f"{months} ay vade • Vergi ve masraflar dahil en uygun 5 banka",
            "rows": reel_rows,
            "cta_text": "KAYDET — Kredi çekmeden önce lazım olur!",
            "question_text": "Sence bu oranlar önümüzdeki ay düşer mi? Yorumlara yaz!",
        }
        dispatch_to_buffer_omnichannel(img_path, f"{lbl} FAİZ ORANLARI", topic=loan_type, reel_data=reel_data)
    return result


def send_deposit_report(
    principal: float = 500_000,
    days: int = 32,
    target_chat_id: str = CHANNEL_ID,
    force_publish: bool = False,
) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Mevduat verileri çekiliyor ({format_tl(principal)} / {days} Gün)...")
    tickers = fetch_market_tickers()
    deposits, zero_offers = get_deposit_offers(principal=principal, days=days)

    changed_banks: List[str] = []
    if target_chat_id == CHANNEL_ID and not force_publish:
        changed, changed_banks = has_rates_changed_since_last_publish("mevduat", deposits)
        if not changed:
            print("[ORAN DEĞİŞİKLİĞİ YOK] Mevduat faiz oranlarında değişiklik yok. Mükerrer paylaşım engellendi!")
            return {"ok": True, "skipped": True, "reason": "no_rate_change"}

    img_path = render_deposit_table_image(
        deposits=deposits,
        zero_offers=zero_offers,
        tickers=tickers,
        output_path=str(Path(__file__).parent / "latest_deposit_table.png"),
    )
    caption = build_deposit_caption(deposits, zero_offers, tickers)
    if changed_banks:
        caption = f"🔄 <b>MEVDUAT ORANLARI GÜNCELLENDİ ({', '.join(changed_banks[:3])})</b>\n" + caption

    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, caption, target_chat_id=target_chat_id, reply_markup=markup)
    if target_chat_id == CHANNEL_ID:
        mark_rates_published("mevduat", deposits)
        attach_img = img_path if should_attach_image_to_x("mevduat") else None
        post_to_x(attach_img, build_deposit_x_text(deposits, changed_banks=changed_banks))
        post_to_whatsapp(img_path, caption)

        best = deposits[0]
        reel_rows = [
            {
                "rank": str(i + 1),
                "title": d.bank_name,
                "sub": f"Net Kazanç: +{format_tl(d.net_return)}",
                "value": f"%{d.annual_rate:.1f}".replace(".", ","),
                "highlight": i == 0,
            }
            for i, d in enumerate(deposits[:5])
        ]
        reel_data = {
            "tag": f"CANLI MEVDUAT • {_tr_short_date()}",
            "hook_line1": f"{format_tl(principal)} MEVDUATTA",
            "hook_line2": f"AYLIK NET +{format_tl(best.net_return)}!",
            "subtitle": f"{days} günlük vade • %17,5 stopaj sonrası net kazanç",
            "rows": reel_rows,
            "cta_text": "KAYDET — Banka seçmeden önce lazım olur!",
            "question_text": "Birikimin mevduatta mı, altında mı? Yorumlara yaz!",
        }
        dispatch_to_buffer_omnichannel(img_path, "GÜNCEL MEVDUAT FAİZLERİ", topic="mevduat", reel_data=reel_data)
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

        # Gram Altın en dar makaslı 5 banka animasyonlu Reel
        src_list = gold_spreads[:5] if gold_spreads else usd_spreads[:5]
        is_gold = bool(gold_spreads)
        reel_rows = []
        for i, item in enumerate(src_list):
            if is_gold:
                sp_txt = f"{item.spread_tl:,.0f} TL".replace(",", ".")
                sub_txt = f"Alış {item.buy_price:,.0f} / Satış {item.sell_price:,.0f}".replace(",", ".")
            else:
                sp_txt = f"{item.spread_tl:.2f} TL".replace(".", ",")
                sub_txt = f"Alış {item.buy_price:.2f} / Satış {item.sell_price:.2f}".replace(".", ",")
            reel_rows.append({
                "rank": str(i + 1),
                "title": item.bank_name,
                "sub": sub_txt,
                "value": sp_txt,
                "highlight": i == 0,
            })

        reel_data = {
            "tag": f"CANLI MAKAS RADARI • {_tr_short_date()}",
            "hook_line1": "GRAM ALTIN ALIRKEN",
            "hook_line2": "EN AZ MAKAS KİMDE?",
            "subtitle": f"Serbest Piyasa Altın: {tickers.get('ALTIN', '—')} • Dolar: {tickers.get('USD', '—')}",
            "rows": reel_rows,
            "cta_text": "KAYDET — Altın almadan önce kontrol et!",
            "question_text": "Altın alırken hangi bankayı kullanıyorsun? Yorumlara yaz!",
        }
        dispatch_to_buffer_omnichannel(img_path, "BANKA DÖVİZ & ALTIN MAKASLARI", topic="makas", reel_data=reel_data)
    return result


def send_viral_insight_report(target_chat_id: str = CHANNEL_ID) -> dict:
    """
    Günün Cep Hesabı / Yüksek Etkileşimli Finans Analizi:
    Oranlar sabit kalsa bile her gün FARKLI, gerçek canlı verilerle hesaplanmış,
    merak uyandıran, kaydedilen ve yorum getiren 1080x1080 kart + 9:16 Animasyonlu Reels üretir.
    """
    now_tr = datetime.now(timezone(timedelta(hours=3)))
    day_idx = now_tr.weekday()  # 0: Pzt ... 6: Paz — her gün bambaşka senaryo!

    tickers = fetch_market_tickers()
    deps_1m, zero_offers = get_deposit_offers(1_000_000, 32)
    deps_500k, _ = get_deposit_offers(500_000, 32)
    iht_offers, _ = get_loan_offers("ihtiyac", 100_000, 12)
    konut_offers, _ = get_loan_offers("konut", 2_000_000, 120)
    usd_spreads, gold_spreads = get_bank_spread_offers()

    if day_idx == 0:
        # Pazartesi: 1 Milyon TL Mevduat Aylık Net Kazancı
        best = deps_1m[0]
        worst = deps_1m[-1]
        tag = "GÜNÜN CEP HESABI"
        headline = "1.000.000 TL MEVDUAT AYLIK NET KAÇ TL GETİRİR?"
        big_lbl = "EN YÜKSEK 32 GÜNLÜK NET KAZANÇ (%17,5 STOPAJ SONRASI)"
        big_val = f"+{format_tl(best.net_return)}  ({best.bank_name} %{best.annual_rate:.1f})"
        rows = [
            {"rank": str(i + 1), "title": d.bank_name, "sub": f"Yıllık %{d.annual_rate:.1f} • Stopaj sonrası net", "value": f"+{format_tl(d.net_return)}", "highlight": i == 0}
            for i, d in enumerate(deps_1m[:5])
        ]
        question = "1 Milyon TL'niz olsa mevduata mı koyardınız, altına mı?"
        hook1, hook2 = "1 MİLYON TL MEVDUAT", f"AYLIK +{format_tl(best.net_return)}!"
        sub = "32 günlük vade • %17,5 stopaj sonrası net kazançlar"
        x_text = (
            f"1.000.000 TL'si olan biri bugün 32 günlük vadeli mevduattan (%17,5 stopaj düşüldükten sonra) ayda net {format_tl(best.net_return)} kazanıyor.\n\n"
            f"En yüksek getiri sunan 3 banka:\n"
            f"• {deps_1m[0].bank_name} (%{deps_1m[0].annual_rate:.1f}): +{format_tl(deps_1m[0].net_return)}\n"
            f"• {deps_1m[1].bank_name} (%{deps_1m[1].annual_rate:.1f}): +{format_tl(deps_1m[1].net_return)}\n"
            f"• {deps_1m[2].bank_name} (%{deps_1m[2].annual_rate:.1f}): +{format_tl(deps_1m[2].net_return)}\n\n"
            f"Bugün 1 milyon TL'niz olsa mevduata mı yatırırdınız, yoksa altın/ev mi?"
        )
    elif day_idx == 1:
        # Salı: 2 Milyon TL Konut Kredisi mi, Kirada Oturup Faize Koymak mı?
        best_k = konut_offers[0]
        deps_2m, _ = get_deposit_offers(2_000_000, 32)
        best_d2 = deps_2m[0]
        tag = "EV Mİ, MEVDUAT MI?"
        headline = "2 MİLYON TL KONUT KREDİSİ Mİ, MEVDUAT GETİRİSİ Mİ?"
        big_lbl = f"2 MİLYON TL AYLIK MEVDUAT GELİRİ vs KONUT TAKSİTİ"
        big_val = f"Faiz: +{format_tl(best_d2.net_return)}  |  Taksit: {format_tl(best_k.monthly_installment)}"
        rows = [
            {"rank": "A", "title": f"2M TL Mevduat ({best_d2.bank_name})", "sub": f"%{best_d2.annual_rate:.1f} ile 32 günde net gelir", "value": f"+{format_tl(best_d2.net_return)}", "highlight": True},
            {"rank": "B", "title": f"2M TL Konut ({best_k.bank_name})", "sub": f"%{best_k.monthly_rate:.2f} • 120 ay aylık taksit", "value": format_tl(best_k.monthly_installment), "highlight": False},
            {"rank": "C", "title": "10 Yılda Toplam Ödeme", "sub": f"{best_k.bank_name} toplam kredi geri ödemesi", "value": format_tl(best_k.total_repayment), "highlight": False},
            {"rank": "D", "title": f"Alternatif ({konut_offers[2].bank_name})", "sub": f"%{konut_offers[2].monthly_rate:.2f} ile 120 ay taksit", "value": format_tl(konut_offers[2].monthly_installment), "highlight": False},
        ]
        question = "Sizce ev almak mı, yoksa 2 milyonu mevduatta tutup kira ödemek mi?"
        hook1, hook2 = "2 MİLYON TL HESABI:", "EV Mİ, MEVDUAT MI?"
        sub = f"Aylık faiz geliri +{format_tl(best_d2.net_return)} • Konut taksiti {format_tl(best_k.monthly_installment)}"
        x_text = (
            f"Günün en çok tartışılan hesabı:\n\n"
            f"2.000.000 TL'yi 32 günlük mevduata koyan biri aylık net {format_tl(best_d2.net_return)} kazanıyor ({best_d2.bank_name} %{best_d2.annual_rate:.1f}).\n\n"
            f"Aynı tutarda 120 ay konut kredisi çekenin aylık taksiti ise {format_tl(best_k.monthly_installment)} ({best_k.bank_name} %{best_k.monthly_rate:.2f}), toplam geri ödemesi {format_tl(best_k.total_repayment)}.\n\n"
            f"Siz olsanız bugün ev mi alırdınız, yoksa kirada kalıp parayı işletir miydiniz?"
        )
    elif day_idx == 2:
        # Çarşamba: 100 Gram Altın Alırken Makas Farkından Ne Kadar Gidiyor?
        g_list = gold_spreads if len(gold_spreads) >= 4 else usd_spreads
        g_best = g_list[0]
        g_worst = g_list[-1]
        loss_100 = (g_worst.spread_tl - g_best.spread_tl) * 100
        tag = "ALTIN MAKAS HESABI"
        headline = "100 GRAM ALTINDA BANKA MAKASI KAÇ TL GÖTÜRÜYOR?"
        big_lbl = "EN DAR MAKAS İLE EN GENİŞ MAKAS ARASINDAKİ 100 GRAM FARKI"
        big_val = f"Tam {format_tl(loss_100)} Anında Fark!"
        rows = [
            {"rank": str(i + 1), "title": g.bank_name, "sub": f"100 gr al-sat maliyeti: {format_tl(g.spread_tl * 100)}", "value": f"{g.spread_tl:,.0f} TL/gr".replace(",", "."), "highlight": i == 0}
            for i, g in enumerate(g_list[:5])
        ]
        question = "Altın alırken bankayı mı, yoksa fiziki kuyumcuyu mu tercih ediyorsunuz?"
        hook1, hook2 = "100 GRAM ALTINDA", f"{format_tl(loss_100)} MAKAS FARKI!"
        sub = f"Canlı Gram Altın: {tickers.get('ALTIN', '—')} • Bankaların 100 gram maliyeti"
        x_text = (
            f"Bugün bankadan 100 gram altın alıp satarken doğru bankayı seçmezseniz sadece makas farkından {format_tl(loss_100)} fazla ödüyorsunuz.\n\n"
            f"100 gram altında bankaların güncel makas maliyeti:\n"
            f"• {g_list[0].bank_name}: {format_tl(g_list[0].spread_tl * 100)}\n"
            f"• {g_list[1].bank_name}: {format_tl(g_list[1].spread_tl * 100)}\n"
            f"• {g_list[-1].bank_name}: {format_tl(g_list[-1].spread_tl * 100)}\n\n"
            f"Siz altın alırken bankayı mı tercih ediyorsunuz, yoksa fiziki kuyumcuyu mu?"
        )
    elif day_idx == 3:
        # Perşembe: 100.000 TL İhtiyaç Kredisi Gerçek Maliyet Farkı
        best_l = iht_offers[0]
        worst_l = iht_offers[-1]
        diff_l = worst_l.total_repayment - best_l.total_repayment
        tag = "KREDİ MALİYET ANALİZİ"
        headline = "100.000 TL KREDİDE YANLIŞ BANKA SEÇMENİN BEDELİ"
        big_lbl = "12 AY VADEDE EN UCUZ İLE EN PAHALI BANKA FARKI"
        big_val = f"Tam {format_tl(diff_l)} Fazla Ödeme!"
        rows = [
            {"rank": str(i + 1), "title": o.bank_name, "sub": f"Taksit: {format_tl(o.monthly_installment)} • Toplam: {format_tl(o.total_repayment)}", "value": f"%{o.monthly_rate:.2f}".replace(".", ","), "highlight": i == 0}
            for i, o in enumerate(iht_offers[:5])
        ]
        question = "Sizce 100.000 TL kredi için bu aylık taksitler ödenebilir mi?"
        hook1, hook2 = "100.000 TL KREDİDE", f"{format_tl(diff_l)} FARK VAR!"
        sub = "12 ay vade • Vergi ve masraflar dahil gerçek toplam maliyet"
        x_text = (
            f"100.000 TL ihtiyaç kredisi (12 ay) çeken iki kişiden biri diğerine göre tam {format_tl(diff_l)} fazla geri ödeme yapıyor.\n\n"
            f"Bugün en düşük toplam geri ödeme sunan 3 banka:\n"
            f"• {iht_offers[0].bank_name} (%{iht_offers[0].monthly_rate:.2f}): {format_tl(iht_offers[0].total_repayment)}\n"
            f"• {iht_offers[1].bank_name} (%{iht_offers[1].monthly_rate:.2f}): {format_tl(iht_offers[1].total_repayment)}\n"
            f"• {iht_offers[2].bank_name} (%{iht_offers[2].monthly_rate:.2f}): {format_tl(iht_offers[2].total_repayment)}\n\n"
            f"Acil nakit ihtiyacınız olsa kredi mi çekersiniz, yoksa kart/taksitli avans mı?"
        )
    elif day_idx == 4:
        # Cuma: 10.000 Dolar Alım-Satımında Banka Makası Farkı
        u_list = usd_spreads if len(usd_spreads) >= 4 else gold_spreads
        u_best = u_list[0]
        u_worst = u_list[-1]
        diff_10k = (u_worst.spread_tl - u_best.spread_tl) * 10_000
        tag = "DÖVİZ MAKAS ANALİZİ"
        headline = "10.000 DOLAR ALIRKEN MAKAS FARKI KAÇ TL?"
        big_lbl = "EN DÜŞÜK İLE EN YÜKSEK BANKA ARASINDA 10.000$ FARKI"
        big_val = f"Tam {format_tl(diff_10k)} Makas Farkı!"
        rows = [
            {"rank": str(i + 1), "title": u.bank_name, "sub": f"10.000$ al-sat farkı: {format_tl(u.spread_tl * 10_000)}", "value": f"{u.spread_tl:.2f} TL".replace(".", ","), "highlight": i == 0}
            for i, u in enumerate(u_list[:5])
        ]
        question = "Döviz işlemlerinde hangi bankanın kurundan memnunsunuz?"
        hook1, hook2 = "10.000 DOLARDA", f"{format_tl(diff_10k)} MAKAS FARKI!"
        sub = f"Canlı Dolar/TL: {tickers.get('USD', '—')} • En dar makaslı 5 banka"
        x_text = (
            f"Bankadan 10.000 Dolar alım-satımı yaparken banka tercihinize göre sadece makastan {format_tl(diff_10k)} fark oluşuyor.\n\n"
            f"10.000$ işlemde en düşük makas maliyeti:\n"
            f"• {u_list[0].bank_name}: {format_tl(u_list[0].spread_tl * 10_000)}\n"
            f"• {u_list[1].bank_name}: {format_tl(u_list[1].spread_tl * 10_000)}\n"
            f"• {u_list[2].bank_name}: {format_tl(u_list[2].spread_tl * 10_000)}\n\n"
            f"Siz döviz alırken mobil bankacılığı mı, yoksa döviz bürosunu mu kullanıyorsunuz?"
        )
    elif day_idx == 5:
        # Cumartesi: Yeni Müşterilere %0 Faizli Nakit Fırsatları Özeti
        tag = "SIFIR FAİZ FIRSATLARI"
        headline = "YENİ MÜŞTERİLERE %0 FAİZLİ NAKİT LİMİTLERİ"
        big_lbl = "BANKALARIN GÜNCEL SIFIR FAİZLİ HOŞ GELDİN PAKETLERİ"
        big_val = "50.000 TL'ye Varan %0 Faiz!"
        rows = [
            {"rank": str(i + 1), "title": z["bank"], "sub": z["detail"][:46], "value": z["amount"], "highlight": i == 0}
            for i, z in enumerate(zero_offers[:5])
        ]
        question = "Bankaların %0 faizli hoş geldin kampanyalarından yararlandınız mı?"
        hook1, hook2 = "YENİ MÜŞTERİLERE", "50.000 TL %0 FAİZ!"
        sub = "3-6 ay vade • Güncel hoş geldin kampanyası sunan bankalar"
        x_text = (
            f"Bankaların yeni müşterilere özel %0 faizli kredi ve taksitli nakit avans kampanyaları devam ediyor.\n\n"
            f"Öne çıkan güncel limitler:\n"
            + "\n".join([f"• {z['bank']}: {z['amount']} ({z['term']})" for z in zero_offers[:4]])
            + "\n\nSiz bu hoş geldin kampanyalarından faydalandınız mı, onay süreci nasıldı?"
        )
    else:
        # Pazar: 500.000 TL Mevduat En Yüksek vs En Düşük Banka Farkı
        best5 = deps_500k[0]
        worst5 = deps_500k[-1]
        diff_y = (best5.net_return - worst5.net_return) * 12
        tag = "HAFTA SONU CEP HESABI"
        headline = "500.000 TL'DE BANKA DEĞİŞTİRMEMENİN YILLIK MALİYETİ"
        big_lbl = "EN YÜKSEK İLE LİSTEDEKİ 8. BANKA ARASINDA YILLIK NET FARK"
        big_val = f"Yılda {format_tl(diff_y)} Ekstra Kazanç!"
        rows = [
            {"rank": str(i + 1), "title": d.bank_name, "sub": f"Aylık net: +{format_tl(d.net_return)}", "value": f"%{d.annual_rate:.1f}".replace(".", ","), "highlight": i == 0}
            for i, d in enumerate(deps_500k[:5])
        ]
        question = "Yüksek faiz için başka bankaya geçer misiniz, yoksa alışkanlık mı?"
        hook1, hook2 = "500.000 TL'DE YILDA", f"{format_tl(diff_y)} FARK!"
        sub = "32 günlük vadeli mevduat • %17,5 stopaj sonrası net getiri"
        x_text = (
            f"500.000 TL'sini düşük faizli bankada tutan biri ile en yüksek faizli bankaya taşıyan arasında 1 yılda yaklaşık {format_tl(diff_y)} net gelir farkı oluşuyor.\n\n"
            f"500.000 TL'nin 32 günlük güncel net kazançları:\n"
            f"• {deps_500k[0].bank_name} (%{deps_500k[0].annual_rate:.1f}): +{format_tl(deps_500k[0].net_return)}\n"
            f"• {deps_500k[1].bank_name} (%{deps_500k[1].annual_rate:.1f}): +{format_tl(deps_500k[1].net_return)}\n"
            f"• {deps_500k[2].bank_name} (%{deps_500k[2].annual_rate:.1f}): +{format_tl(deps_500k[2].net_return)}\n\n"
            f"Siz yüksek oran için banka değiştiriyor musunuz?"
        )

    img_path = render_viral_insight_image(
        tag=tag,
        headline=headline,
        big_metric_label=big_lbl,
        big_metric_value=big_val,
        rows=rows[:4],
        question=question,
        output_path=str(Path(__file__).parent / "latest_insight.png"),
    )

    tg_caption = (
        f"💡 <b>FAİZ RADARI | {tag}</b> ({_tr_short_date()})\n\n"
        f"📌 <b>{headline}</b>\n"
        f"🔥 <b>{big_val}</b>\n\n"
        + "\n".join([f"• <b>{r['title']}:</b> {r['value']} ({r['sub']})" for r in rows[:4]])
        + f"\n\n💬 <b>{question}</b>\n\n"
        "⚠️ <i>Canlı banka verilerinden derlenmiştir, yatırım tavsiyesi değildir.</i>\n"
        "🔔 <b>Takip:</b> @faizradari"
    )

    markup = _default_reply_markup() if target_chat_id == CHANNEL_ID else _interactive_menu_markup()
    result = _post_photo_to_telegram(img_path, tg_caption, target_chat_id=target_chat_id, reply_markup=markup)
    if result.get("ok"):
        print(f"[BAŞARILI] Günün Cep Hesabı Analizi ({tag}) {target_chat_id} hedefine paylaşıldı!")

    if target_chat_id == CHANNEL_ID:
        post_to_x(img_path, x_text)
        post_to_whatsapp(img_path, tg_caption)

        ig_cap = (
            f"{headline}\n\n"
            f"{big_val}\n\n"
            f"Karar vermeden önce bu hesabı kaydetmeyi unutmayın.\n\n"
            f"{question} 👇\n\n"
            "#finans #ekonomi #faiz #mevduat #yatirim"
        )
        reel_data = {
            "tag": f"{tag} • {_tr_short_date()}",
            "hook_line1": hook1,
            "hook_line2": hook2,
            "subtitle": sub,
            "rows": rows[:5],
            "cta_text": "KAYDET — Lazım olduğunda elinin altında olsun!",
            "question_text": question,
            "caption": ig_cap,
        }
        dispatch_to_buffer_omnichannel(img_path, headline, topic="analiz", reel_data=reel_data)

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
        f"En Yüksek Mevduat: {best_dep.bank_name} (%{best_dep.annual_rate:.1f}); 500.000 TL anaparanın 32 günlük net getirisi +{format_tl(best_dep.net_return)}." if best_dep else "En Yüksek Mevduat: Ziraat Dinamik (%45,0); 500k TL 32 gün net getiri +16.274 TL.",
        f"En Uygun İhtiyaç Kredisi: {best_iht.bank_name} (%{best_iht.monthly_rate:.2f}); 100.000 TL 12 ay vadede taksit {format_tl(best_iht.monthly_installment)}, toplam {format_tl(best_iht.total_repayment)}." if best_iht else "En Uygun İhtiyaç Kredisi: DenizBank (%2,89); 100k TL 12 ay taksit 10.506 TL.",
        f"En Uygun Konut Kredisi: {best_konut.bank_name} (%{best_konut.monthly_rate:.2f}); 2.000.000 TL 120 ay vadede taksit {format_tl(best_konut.monthly_installment)} ile piyasa lideri." if best_konut else "En Uygun Konut Kredisi: VakıfBank (%2,84); 2M TL 120 ay taksit 58.843 TL.",
        f"En Uygun Taşıt Kredisi: {best_tasit.bank_name} (%{best_tasit.monthly_rate:.2f}); 400.000 TL 36 ay vadede taksit {format_tl(best_tasit.monthly_installment)} seviyesinde." if best_tasit else "En Uygun Taşıt Kredisi: Garanti BBVA (%3,25); 400k TL 36 ay taksit 21.450 TL.",
        f"Yeni Müşteri %0 Faiz: {zero_banks} yeni müşterilere 50.000 TL'ye varan sıfır faizli nakit fırsatı sunuyor.",
        f"Döviz Piyasası: Dolar/TL {tickers.get('USD', '—')}, Euro/TL {tickers.get('EUR', '—')} bandında serbest piyasada işlem görüyor.",
        f"Kıymetli Madenler: Kapalıçarşı serbest piyasada Gram Altın {tickers.get('ALTIN', '—')} seviyesinde seyrediyor.",
        f"Banka Döviz Makası: Dolar alım-satımında en dar makas aralığını {best_usd.bank_name} ({best_usd.spread_tl:.2f} TL fark) ile sunuyor." if best_usd else "Banka Döviz Makası: En dar makas aralığı anlık takip ediliyor.",
        "Mevduat Stopaj Oranı: 6 aya kadar vadeli TL mevduatlarda güncel yasal stopaj oranı %17,5 seviyesinde uygulanıyor.",
        "Kredi Kartı Faizleri: Kredi kartı dönem borcu ve nakit avans akdi/gecikme faiz oranları yakından izleniyor."
    ]
    return items


def build_briefing_caption(items: List[str] = None) -> str:
    import random
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    hooks = [
        "Piyasalarda güne başlarken faiz, kredi, mevduat ve dövizdeki en kritik 10 gelişmeyi tek tabloda derledik.",
        "Cebinizi ve yatırımlarınızı doğrudan ilgilendiren günün en önemli 10 finans başlığı hazır.",
        "Bankaların güncel oranları, piyasa kurları ve öne çıkan fırsatlarla sabah finans özeti yayında.",
    ]
    hook = random.choice(hooks)
    lines = [
        f"📊 <b>FAİZ RADARI | GÜNÜN FİNANS RAPORU</b> ({now_str})\n",
        f"⚡ {hook}\n",
        "📌 <i>Detaylı oranları yukarıdaki infografikten inceleyebilirsiniz.</i>\n",
        "⚠️ <i>Bilgilendirme amaçlıdır, yatırım tavsiyesi içermez.</i>\n",
        "🔔 <b>Takip:</b> @faizradari"
    ]
    return "\n".join(lines)


def build_briefing_x_text(items: List[str] = None) -> str:
    now_str = datetime.now().strftime("%d.%m.%Y")
    # Temiz haber odası formatı: Telegram spamı yok, hashtag kalabalığı yok!
    highlights = []
    if items and len(items) >= 7:
        for it in (items[0], items[1], items[5], items[6]):
            short = it.split(";")[0].strip()
            highlights.append(f"• {short}")
    body = "\n".join(highlights) if highlights else "Güncel kredi, mevduat, dolar ve gram altın verileri tek tabloda."
    return (
        f"Günün Finans Özeti ({now_str})\n\n"
        f"{body}\n\n"
        f"Güne başlarken piyasalardaki beklentiniz nedir?"
    )


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
        # Sabah raporu Telegram + WhatsApp + X'e gider (Instagram kotası sadece animasyonlu Reels'lere ayrılır!)
        post_to_x(img_path, build_briefing_x_text(items))
        post_to_whatsapp(img_path, caption)
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
        "konut_best": f"{best_konut.bank_name} (%{best_konut.monthly_rate:.2f}) ile {format_tl(best_konut.monthly_installment)} taksit." if best_konut else "VakıfBank (%2.84)",
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
        dispatch_to_buffer_omnichannel(img_path, "HAFTALIK FİNANS KARNESİ", topic="mevduat")
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
        dispatch_to_buffer_omnichannel(img_path, "HAFTALIK FİNANS KARNESİ", topic="mevduat")
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
    KESİN GÜNLÜK MÜKERRER ENGELLEYİCİ:
    - Eğer bu konu (ihtiyac, konut, tasit, mevduat, makas, bulten, analiz, haftalik)
      BUGÜN içinde herhangi bir saatte daha önce paylaşıldıysa True (KİLİTLİ) döner!
    - Aynı gün içinde aynı konunun ikinci kez paylaşılmasını %100 engeller (GAS + GitHub Cron çakışmaları dahil).
    """
    try:
        from scraper import _load_full_cache, _save_full_cache
        cache = _load_full_cache()
        now = datetime.now(timezone(timedelta(hours=3)))
        today_str = now.strftime("%Y-%m-%d")
        cutoff_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        daily_map = cache.get("daily_dispatched", {})
        # Eski günleri temizle (son 7 gün tutulur)
        daily_map = {k: v for k, v in daily_map.items() if k >= cutoff_str}
        today_list = daily_map.get(today_str, [])

        if slot_topic in today_list:
            print(f"[GÜNLÜK ENGELLEYİCİ] '{slot_topic.upper()}' paylaşımı bugün ({today_str}) zaten yapıldı! Mükerrer gönderim iptal edildi.")
            return True

        if slot_topic == "makas" and cache.get("last_makas_date") == today_str:
            print(f"[GÜNLÜK MAKAS LİMİTİ] Makas tablosu bugün ({today_str}) zaten paylaşıldı!")
            return True

        today_list.append(slot_topic)
        daily_map[today_str] = today_list
        cache["daily_dispatched"] = daily_map
        cache["last_dispatched_slot"] = f"{today_str}_{now.strftime('%H')}_{slot_topic}"
        cache["last_dispatched_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        if slot_topic == "makas":
            cache["last_makas_date"] = today_str
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

    schedule.every().day.at("09:00").do(send_briefing_report)
    schedule.every().day.at("11:00").do(send_loan_report, loan_type="ihtiyac", principal=100_000, months=12)
    schedule.every().day.at("13:00").do(send_viral_insight_report)
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
    elif "--analiz" in sys.argv:
        send_viral_insight_report()
    elif "--spread" in sys.argv:
        send_spread_report()
    elif "--konut" in sys.argv:
        send_loan_report(loan_type="konut", principal=2_000_000, months=120, force_publish="--force" in sys.argv)
    elif "--tasit" in sys.argv:
        send_loan_report(loan_type="tasit", principal=400_000, months=36, force_publish="--force" in sys.argv)
    elif "--mevduat" in sys.argv:
        send_deposit_report(principal=500_000, days=32, force_publish="--force" in sys.argv)
    elif "--haftalik" in sys.argv or "--karne" in sys.argv:
        send_weekly_recap_report()
    elif "--haber" in sys.argv:
        headline = "TCMB Politika Faizi Gelişmesi"
        details = "Merkez Bankası piyasa beklentileri doğrultusunda kararını açıkladı."
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

        # 1.5. Canlı Oran İndirim Taraması (SADECE gerçek yeni faiz indirimi varsa 1 kez duyurur; artışları paylaşmaz!)
        try:
            live_rate_alerts = check_all_loan_rates_for_changes()
            if live_rate_alerts:
                print(f"[FLAŞ İNDİRİM TESPİTİ] {len(live_rate_alerts)} adet banka faiz indirimi aday olarak bulundu.")
                dispatch_rate_change_alerts(live_rate_alerts, target_chat_id=CHANNEL_ID)
        except Exception as e:
            print(f"[UYARI] Otomatik faiz değişim tarama hatası: {e}")

        # 2. Otomatik slot tespiti (Kalite Odaklı & Sıfır Spam Akışı)
        today_str = now_tr.strftime("%Y-%m-%d")
        from scraper import _load_full_cache
        cache = _load_full_cache()
        last_makas_date = cache.get("last_makas_date")

        # Makas Kuralı: Günde kesinlikle SADECE 1 KEZ ve yalnızca 16:00-17:59 (Piyasa Kapanışı) saatinde!
        if target_topic == "makas" and not is_force:
            if last_makas_date == today_str or tr_hour not in (16, 17):
                print(f"[MAKAS KORUMASI] Makas tablosu sadece günde 1 kez saat 17:00 slotunda paylaşılır.")
                target_topic = "auto"

        if not target_topic or target_topic == "auto":
            if tr_hour in (8, 9):
                target_topic = "bulten"       # 09:00 Günün Finans Özeti (Her gün taze kur & piyasa)
            elif tr_hour in (10, 11):
                target_topic = "ihtiyac"      # 11:00 İhtiyaç Kredisi (Yalnızca oran değiştiyse paylaşılır!)
            elif tr_hour in (12, 13):
                target_topic = "analiz"       # 13:00 Günün Cep Hesabı / Viral Analiz + Animasyonlu Reels #1
            elif tr_hour in (14, 15):
                target_topic = "konut_tasit"  # 15:00 Konut & Taşıt (Yalnızca oran değiştiyse paylaşılır!)
            elif tr_hour in (16, 17):
                target_topic = "makas"        # 17:00 Canlı Dolar & Altın Makas + Animasyonlu Reels #2 (Günde 1x)
            elif tr_hour in (18, 19):
                target_topic = "haftalik" if now_tr.weekday() == 6 else "mevduat"  # 19:00 Pazar Karne / Mevduat (Değiştiyse!)
            else:
                print(f"[PLAN DIŞI SAAT] TR Saati {tr_hour:02d}:{tr_minute:02d} planlı yayın saatlerine denk gelmiyor. Paylaşım yapılmadı.")
                sys.exit(0)

        # 3. Kesin Günlük Mükerrer Engelleyici (Aynı konu aynı gün içinde ASLA 2 kez paylaşılmaz!)
        if not is_force and check_and_set_dispatch_lock(target_topic):
            print(f"[BİLGİ] {target_topic.upper()} bugün zaten yayınlandı, işlem güvenle sonlandırıldı.")
            sys.exit(0)

        if target_topic in ("bulten", "sabah"):
            send_briefing_report()
        elif target_topic == "analiz":
            send_viral_insight_report()
        elif target_topic == "ihtiyac":
            send_loan_report(loan_type="ihtiyac", principal=100_000, months=12, force_publish=is_force)
        elif target_topic == "tasit":
            send_loan_report(loan_type="tasit", principal=400_000, months=36, force_publish=is_force)
        elif target_topic == "konut":
            send_loan_report(loan_type="konut", principal=2_000_000, months=120, force_publish=is_force)
        elif target_topic == "konut_tasit":
            send_loan_report(loan_type="konut", principal=2_000_000, months=120, force_publish=is_force)
            send_loan_report(loan_type="tasit", principal=400_000, months=36, force_publish=is_force)
        elif target_topic == "makas":
            send_spread_report()
        elif target_topic == "haftalik":
            send_weekly_recap_report()
        elif target_topic == "mevduat":
            send_deposit_report(principal=500_000, days=32, force_publish=is_force)
    elif "--check-rate-changes" in sys.argv:
        alerts = check_all_loan_rates_for_changes()
        if alerts:
            print(f"[SONUÇ] {len(alerts)} banka faiz indirimi tespit edildi.")
            target = CHANNEL_ID if "--kanal" in sys.argv else ADMIN_CHAT_ID
            dispatch_rate_change_alerts(alerts, target_chat_id=target)
        else:
            print("[SONUÇ] Faiz oranlarında yeni bir indirim tespit edilmedi.")
    elif "--schedule" in sys.argv:
        run_scheduler()
    else:
        send_viral_insight_report()
