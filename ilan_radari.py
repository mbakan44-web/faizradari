import os
import re
import sys
import json
import html as html_lib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from dotenv import load_dotenv

from image_generator import _load_font

load_dotenv(Path(__file__).parent / ".env", override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
ILAN_CHANNEL_ID = os.getenv("ILAN_CHANNEL_ID", "@ilanradari").strip()
FAIZ_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@faizradari").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "702244471").strip()

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN", "9HHe4hOHubOEGnfoSQ2CjR1ak1VxxqFK").strip()
ILAN_WHATSAPP_CHANNEL_ID = os.getenv("ILAN_WHATSAPP_CHANNEL_ID", "120363432658946070@newsletter").strip()
ILAN_WHATSAPP_INVITE_URL = "https://whatsapp.com/channel/0029Vb9rhBs90x2y0jH3O31J"


def convert_ilan_to_whatsapp(text: str) -> str:
    """Telegram HTML etiketlerini WhatsApp uyumlu metne dönüştürür ve ana Telegram kanalımıza yönlendirme ekler."""
    # WhatsApp'ta tarih ve saat görünmesin (kullanıcı kuralı)
    t = re.sub(r'📅[^\n]*\n?', '', text)
    t = re.sub(r'\(\d{1,2}\.\d{1,2}\.\d{4}[^\)]*\)', '', t)
    t = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', r'*\2*:\n\1', t, flags=re.DOTALL)
    t = re.sub(r'<b>(.*?)</b>', r'*\1*', t, flags=re.DOTALL)
    t = re.sub(r'<strong>(.*?)</strong>', r'*\1*', t, flags=re.DOTALL)
    t = re.sub(r'<i>(.*?)</i>', r'_\1_', t, flags=re.DOTALL)
    t = re.sub(r'<em>(.*?)</em>', r'_\1_', t, flags=re.DOTALL)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = (
        t.strip()
        + "\n\n🔔 *İlan Radarı Resmi Kanalları*\n"
        + "• Yeni ilanları kaçırmamak için sağ üstteki çan simgesine tıklayarak bildirimleri açmayı unutmayın!\n"
        + "📢 Tüm personel alım tabloları ve anlık ilan bildirimleri için Ana Telegram Kanalımız:\n"
        + "👉 https://t.me/ilanradari"
    )
    return t.strip()


def post_ilan_to_whatsapp(img_path: str, caption: str) -> bool:
    """Whapi.cloud üzerinden İlan Radarı WhatsApp Kanalına (120363432658946070@newsletter) otomatik paylaşım yapar."""
    if not (WHAPI_TOKEN and ILAN_WHATSAPP_CHANNEL_ID and Path(img_path).exists()):
        return False
    try:
        import base64
        wa_text = convert_ilan_to_whatsapp(caption)
        ext = "jpeg" if str(img_path).lower().endswith((".jpg", ".jpeg")) else "png"
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload = {
            "to": ILAN_WHATSAPP_CHANNEL_ID,
            "media": f"data:image/{ext};base64,{img_b64}",
            "caption": wa_text,
        }
        headers = {
            "Authorization": f"Bearer {WHAPI_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "IlanRadari-Bot/1.0",
        }
        r = requests.post("https://gate.whapi.cloud/messages/image", json=payload, headers=headers, timeout=35)
        ok = r.status_code in (200, 201)
        if ok:
            print(f"[BAŞARILI] İlan Radarı WhatsApp Kanalına ({ILAN_WHATSAPP_CHANNEL_ID}) paylaşıldı!")
        else:
            print(f"[UYARI] İlan Radarı WhatsApp paylaşım hatası ({r.status_code}): {r.text[:160]}")
        return ok
    except Exception as e:
        print(f"[UYARI] İlan Radarı WhatsApp API hatası: {e}")
        return False

ILAN_CACHE_FILE = Path(__file__).parent / "ilan_cache.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_ilan_cache() -> Dict:
    if ILAN_CACHE_FILE.exists():
        try:
            return json.loads(ILAN_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"dispatched_headlines": [], "daily_dispatched": {}}


def save_ilan_cache(data: Dict) -> None:
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    ILAN_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_kw(text: str) -> set:
    stops = {"ve", "ile", "için", "bir", "bu", "da", "de", "mi", "mı", "mu", "mü", "ne", "son", "yeni", "güncel"}
    words = re.findall(r"[a-zçğıöşü0-9]{3,}", text.lower())
    return {w for w in words if w not in stops}


def _is_dup_headline(title: str, existing_list: List[str]) -> bool:
    kw1 = _extract_kw(title)
    if not kw1:
        return False
    for old_t in existing_list[-50:]:
        kw2 = _extract_kw(old_t)
        if not kw2:
            continue
        overlap = len(kw1 & kw2) / float(min(len(kw1), len(kw2)))
        if overlap >= 0.58:
            return True
    return False


def _tr_lower(text: str) -> str:
    """Türkçe karakterleri güvenli şekilde küçük harfe dönüştürür (İ/I uyuşmazlığını çözer)."""
    if not text:
        return ""
    return text.replace("İ", "i").replace("I", "ı").replace("i̇", "i").lower()


def _decode_job_url(raw_link: str) -> str:
    """Google News veya yönlendirmeli linkleri gerçek ilan sayfasına dönüştürür."""
    if not raw_link:
        return ""
    if "news.google.com" in raw_link:
        try:
            from googlenewsdecoder import gnewsdecoder
            res = gnewsdecoder(raw_link, interval=0.1)
            if res.get("status") or res.get("success"):
                dec = res.get("decoded_url") or ""
                if dec.startswith("http"):
                    return dec
        except Exception:
            pass
    return raw_link


def is_vague_clickbait(title: str) -> bool:
    """Kurum veya somut pozisyon adı içermeyen genel tık tuzağı, soru kalıbı ve özet haber başlıklarını eler."""
    t = _tr_lower(title)
    # Soru işareti içeren veya soru kalıbı taşıyan clickbait blog yazılarını KESİNLİKLE ele!
    if "?" in title or "?" in t:
        return True
    if any(q in t for q in ("ne zaman", "şartı var mı", "şartları neler", "nasıl başvurulur", "nereden yapılır", "başladı mı", "açıklandı mı", "kaç puan", "alımı var mı", "ne kadar olacak")):
        return True
    # Belirli bir kurum veya somut pozisyon adı içermeyen jenerik 'kamuya 11 bin...', 'personel alımı ilanları' başlıklarını ele
    institutions = [
        "bakanlığ", "belediye", "üniversite", "hastane", "müdürlüğ", "valili", "adli tıp",
        "işkur", "polis", "jandarma", "itfaiye", "nvi", "nüfus", "defterdarlık", "dsi",
        "ogm", "tigem", "sgk", "vakıfbank", "ziraat", "halkbank", "denizbank", "rekabet kurumu",
        "türk akreditasyon", "kalkınma ajansı", "tübitak", "afad", "öğretmen", "doktor",
        "hemşire", "güvenlik", "zabıt", "kızılay", "uzman erbaş", "uzman yardımcısı"
    ]
    if not any(inst in t for inst in institutions):
        return True
    if re.search(r"^\d{1,2}\s+[a-zçğıöşü]+\s+kamu\s+personel\s+alımı", t):
        return True
    if "kamu personel alımı ilanları yayımlandı" in t or "personel alımı ilanları yayımlandı" in t or "iş ilanları yayımlandı" in t:
        return True
    if re.search(r"işte\s+(başvuru\s+detayları|o\s+liste|o\s+şartlar|o\s+kadrolar|başvuru\s+şartları$)", t):
        return True
    return False


def _detect_job_tag_and_badge(title: str, desc: str) -> Tuple[str, str]:
    comb = _tr_lower(f"{title} {desc}")
    if "bilişim" in comb or "yazılım" in comb or "bilgisayar" in comb:
        tag = "BİLİŞİM & YAZILIM"
    elif "uzman yardımcısı" in comb or "müfettiş" in comb:
        tag = "A GRUBU KARİYER"
    elif "öğretim elemanı" in comb or "öğretim üyesi" in comb or "araştırma görevlisi" in comb:
        tag = "AKADEMİK KADRO"
    elif "kpss şartsız" in comb or "kpss'siz" in comb or "sınavsız" in comb:
        tag = "KPSS ŞARTSIZ ALIM"
    elif "kpss" in comb:
        m = re.search(r"kpss\s*(\d{2})\s*puan", comb)
        tag = f"KPSS {m.group(1)}+ PUAN" if m else "KPSS İLE ALIM"
    elif "işkur" in comb:
        tag = "İŞKUR İŞ İLANI"
    elif "belediye" in comb:
        tag = "BELEDİYE ALIMI"
    elif "hastane" in comb or "sağlık" in comb or "hemşire" in comb or "doktor" in comb or "laborant" in comb:
        tag = "SAĞLIK PERSONELİ"
    elif "polis" in comb or "jandarma" in comb or "uzman erbaş" in comb:
        tag = "EMNİYET & ASKERİ"
    elif "üniversite" in comb:
        tag = "ÜNİVERSİTE KADROSU"
    elif "emekli" in comb or "promosyon" in comb:
        tag = "EMEKLİ & PROMOSYON"
    elif "maaş" in comb or "zam" in comb or "asgari ücret" in comb:
        tag = "MAAŞ & ZAM REHBERİ"
    else:
        tag = "KAMU PERSONEL ALIMI"

    if "alacak" in comb or "başladı" in comb or "başvuru" in comb or "alım" in comb:
        badge = "BAŞVURU AKTİF"
    elif "açıklandı" in comb or "belli oldu" in comb:
        badge = "YENİ DUYURU"
    else:
        badge = "GÜNCEL"
    return tag, badge


def _clean_clickbait_summary(text: str) -> str:
    """
    Haber sitelerinin özet sonuna eklediği 'Detaylar burada.', 'İşte detaylar...',
    'Detaylar haberimizde.' gibi tıklama tuzağı cümlelerini ve özel site isimlerini temizler.
    """
    if not text:
        return ""
    cleaned = text
    # Özel haber sitesi isimlerini ve uzantılarını temizle
    cleaned = re.sub(r"\b(isinolsa\.com|memurlar\.net|kamupersoneli\.net|işin olsa|kamu personeli)\b", "", cleaned, flags=re.IGNORECASE)
    # Son cümledeki 'Detaylar burada', 'İşte detaylar', 'Haberimizde' kalıplarını sil
    tail_patterns = [
        r"[^\.!\?]*\b(detaylar|ayrıntılar)\s+(burada|haberimizde|yazımızda|sayfamızda|aşağıda)[^\.!\?]*[\.!\?…]*",
        r"[^\.!\?]*\bişte\s+(detaylar|başvuru\s+ekranı|şartlar|kadro\s+dağılımı)[^\.!\?]*[\.!\?…]*",
        r"[^\.!\?]*\b(haberin\s+devamı|tıklayınız|başvuru\s+linki\s+haberimizde)[^\.!\?]*[\.!\?…]*",
    ]
    for pat in tail_patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _resolve_official_gov_link(title: str, summary: str) -> Tuple[str, str]:
    """
    İlanın kurumuna ve türüne göre varsayılan resmi portal adını ve genel URL'sini belirler.
    Tüm gerçek ilanlarda asıl derin bağlantı (_decode_job_url ile çözümlenen ilan.gov.tr/ilan/...) korunur.
    """
    comb = _tr_lower(f"{title} {summary}")

    # 1. Kariyer Kapısı
    if any(k in comb for k in ("kariyer kapısı", "kariyerkapisi", "isealimkariyerkapisi")):
        return ("Kariyer Kapısı İlan Kılavuzu & Şartlar", "https://kariyerkapisi.gov.tr/isealim")

    # 2. İŞKUR & Belediye İşçi Alımları
    if any(k in comb for k in ("işkur", "iskur", "sürekli işçi", "belediye işçi", "kurum dışı kamu", "typ alımı")):
        return ("İŞKUR Resmi e-Şube Başvuru Ekranı", "https://esube.iskur.gov.tr")

    # 3. Polis & Askeri Temin
    if any(k in comb for k in ("polis", "pomem", "pmyo", "bekçi alımı")):
        return ("Polis Akademisi Başkanlığı", "https://www.pa.edu.tr")
    if any(k in comb for k in ("jandarma", "sahil güvenlik", "jsga", "uzman erbaş", "sözleşmeli er")):
        return ("Jandarma ve Sahil Güvenlik Personel Temin", "https://vatandas.jandarma.gov.tr")
    if any(k in comb for k in ("milli savunma", "msb", "subay alımı", "astsubay alımı")):
        return ("MSB Personel Temin Dairesi", "https://personeltemin.msb.gov.tr")

    # 4. Üniversiteler, Bakanlıklar ve Kamu Kurumları (Asıl kaynak Basın İlan Kurumu'dur)
    return ("Resmi İlan Metni (ilan.gov.tr)", "https://www.ilan.gov.tr")


def fetch_live_job_announcements(limit: int = 8) -> List[Dict]:
    """
    ilan.gov.tr (Basın İlan Kurumu), Kariyer Kapısı ve doğrulanmış resmi kaynaklardan
    canlı personel alımı, sözleşmeli personel, akademik ve kamu alım duyurularını çeker.
    Tüm ilanlar doğrudan ilan.gov.tr/ilan/... derin bağlantısıyla açılır.
    """
    feeds = [
        (
            "İlan.gov.tr Personel Alımları",
            "https://news.google.com/rss/search?q=site:ilan.gov.tr+(%22personel+al%C4%B1m%C4%B1%22+OR+%22memur+al%C4%B1m%C4%B1%22+OR+%22s%C3%B6zle%C5%9Fmeli+personel%22+OR+%22i%C5%9F%C3%A7i+al%C4%B1m%C4%B1%22)+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        ),
        (
            "İlan.gov.tr Akademik & Kariyer",
            "https://news.google.com/rss/search?q=site:ilan.gov.tr+(%22%C3%B6%C4%9Fretim+eleman%C4%B1%22+OR+%22uzman+erba%C5%9F%22+OR+%22uzman+yard%C4%B1mc%C4%B1s%C4%B1%22+OR+%22akademik+personel%22)+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        ),
        (
            "Kariyer Kapısı Resmi",
            "https://news.google.com/rss/search?q=site:kariyerkapisi.gov.tr+when:14d&hl=tr&gl=TR&ceid=TR:tr",
        ),
    ]

    reject_pats = [
        r"sandero|corsa|otomobil|araba|suv",
        r"burç|astroloji|magazin|dizi|fragman",
        r"futbol|maç|transfer|galatasaray|fenerbahçe|beşiktaş",
        r"sayısal loto|şans topu|piyango",
        r"hava durumu|deprem",
        r"ihale|ihalesi|mal alım|hizmet alım|doğrudan temin|yapım işi|onarım işi|ihale duyuru|iptal ilanı|düzeltme ilanı|konkordato|icra|satış ilanı|kiraya ver|taşınmaz sat|arsa sat|araç sat|sütur",
    ]
    positive_kws = [
        "personel", "memur", "işçi", "alım", "alacak", "kpss", "işkur",
        "kadrolu", "sözleşmeli", "başvuru", "ilan", "atama", "maaş",
        "promosyon", "emekli", "zam", "ikramiye", "bekçi", "güvenlik",
        "sekreter", "hemşire", "mühendis", "öğretmen", "bakanlığı", "belediye",
        "üniversite", "tigem", "ptt", "dsi", "ogm", "jandarma", "polis",
    ]

    now_utc = datetime.now(timezone.utc)
    items_out: List[Dict] = []
    seen_titles: List[str] = []

    for src_name, url in feeds:
        try:
            import xml.etree.ElementTree as ET
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for it in root.findall(".//item")[:20]:
                pub_str = (it.findtext("pubDate") or "").strip()
                if pub_str:
                    try:
                        p_dt = parsedate_to_datetime(pub_str).astimezone(timezone.utc)
                        if (now_utc - p_dt).total_seconds() / 3600.0 > 168.0:
                            continue
                    except Exception:
                        pass

                raw_t = it.findtext("title") or ""
                raw_d = it.findtext("description") or ""
                raw_link = (it.findtext("link") or "").strip()

                t = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_t)).strip()
                t = re.sub(r"\s+-\s+[A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\s]{2,30}$", "", t).strip()
                t = re.sub(r"\s+", " ", t)

                d = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_d)).strip()
                d = re.sub(r"\s+", " ", d)
                if d.lower().startswith(t[:28].lower()):
                    d = ""

                if len(t) < 22 or len(t) > 125:
                    continue

                if is_vague_clickbait(t):
                    continue

                low_all = _tr_lower(f"{t} {d}")
                if any(re.search(p, low_all) for p in reject_pats):
                    continue

                hits = sum(1 for k in positive_kws if k in low_all)
                if hits < 1:
                    continue

                if _is_dup_headline(t, seen_titles):
                    continue

                tag, badge = _detect_job_tag_and_badge(t, d)
                score = hits * 10
                if any(k in t.lower() for k in ("personel", "memur", "işçi", "alım", "alacak", "işkur", "kpss")):
                    score += 35
                if "site:ilan.gov.tr" in url or "ilan.gov.tr" in raw_link:
                    score += 75
                if len(d) >= 50:
                    score += 12

                cleaned_d = _clean_clickbait_summary(d)
                gov_name, gov_url = _resolve_official_gov_link(t, cleaned_d)
                clean_summary = (
                    cleaned_d
                    if len(cleaned_d) >= 40
                    else f"{t}. İlgili personel alımına dair başvuru şartları, kadro dağılımı ve takvim resmi ilan kılavuzunda yayımlanmıştır."
                )
                if len(clean_summary) > 260:
                    clean_summary = clean_summary[:257].rsplit(" ", 1)[0] + "..."

                seen_titles.append(t)
                items_out.append({
                    "title": t,
                    "summary": clean_summary,
                    "tag": tag,
                    "badge": badge,
                    "source": gov_name,
                    "gov_name": gov_name,
                    "gov_url": gov_url,
                    "raw_link": raw_link,
                    "direct_url": gov_url,
                    "score": score,
                })
        except Exception:
            continue

    items_out.sort(key=lambda x: x["score"], reverse=True)
    valid_items: List[Dict] = []
    for item in items_out:
        r_link = item.get("raw_link", "")
        if r_link:
            dec_url = _decode_job_url(r_link)
            if dec_url and dec_url.startswith("http"):
                # İhale, mal/hizmet alım ihaleleri, icra veya satış ilanlarını kesinlikle ele
                if any(bad in dec_url for bad in ("ihale-duyurulari", "ihale", "mal-alim", "hizmet-alim", "/emlak/", "/vasita/", "/iflas-", "/icra-", "satisi")):
                    continue
                if "/ilan/" in dec_url or "ilan.gov.tr" in dec_url:
                    item["direct_url"] = dec_url
                    item["gov_name"] = "Resmi İlan Metni (ilan.gov.tr)"
                    item["gov_url"] = dec_url
                elif any(dom in dec_url for dom in ("resmigazete.gov.tr", "kariyerkapisi", ".gov.tr", ".edu.tr", "iskur.gov.tr", "pa.edu.tr", "jandarma.gov.tr")):
                    item["direct_url"] = dec_url
                    item["gov_url"] = dec_url
                else:
                    # Üçüncü taraf haber/blog sitesiyse gov_url'i bozma; direct_url olarak resmi gov_url'i kullan
                    item["direct_url"] = item.get("gov_url", "https://www.ilan.gov.tr")
        valid_items.append(item)
        if len(valid_items) >= limit:
            break

    return valid_items


def get_salary_and_promo_reference() -> List[Dict]:
    """Güncel Emekli Banka Promosyonları ve Temel Kamu/Çalışma Hayatı Maaş Göstergeleri."""
    return [
        {"title": "VakıfBank Emekli Promosyonu", "sub": "12.000 TL Nakit + Troy Kart Ek Nakit Fırsatı", "val": "24.000 TL'ye Varan", "badge": "LİDER"},
        {"title": "ING Türkiye Emekli Promosyonu", "sub": "Koşulsuz Nakit + Otomatik Fatura Talimatı", "val": "20.000 TL'ye Varan", "badge": "YÜKSEK"},
        {"title": "Yapı Kredi Emekli Paketi", "sub": "Nakit Promosyon + Fatura & Ek Ödül", "val": "18.000 TL'ye Varan", "badge": "POPÜLER"},
        {"title": "Akbank Emekli Promosyonu", "sub": "15.000 TL Nakit + 2.500 TL Chip-Para", "val": "17.500 TL'ye Varan", "badge": "GÜNCEL"},
        {"title": "Garanti BBVA & QNB Emekli", "sub": "Maaş Tutarına Göre Koşulsuz Nakit Promosyon", "val": "15.000 TL - 16.250 TL", "badge": "GÜNCEL"},
        {"title": "Ziraat Bankası & Halkbank", "sub": "Kamu Bankaları Standart Nakit Promosyon + 40.000 TL %0 Kredi", "val": "12.000 TL + %0 Kredi", "badge": "KAMU"},
    ]


def render_daily_jobs_table_image(
    jobs: List[Dict],
    output_path: str = "D:/faiz-radari/latest_ilan_table.png",
) -> str:
    """
    1080x1080 'GÜNÜN KAMU, İŞKUR VE PERSONEL ALIM İLANLARI' İnfografik Tablosu.
    Sıfır tofu emoji; temiz, kurumsal ve okunaklı.
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color=(8, 13, 25))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        r = int(8 + (16 - 8) * (y / H))
        g = int(13 + (24 - 13) * (y / H))
        b = int(25 + (45 - 25) * (y / H))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw.rectangle([(0, 0), (W, 8)], fill=(245, 158, 11))

    f_top = _load_font(17, bold=True)
    f_h1 = _load_font(32, bold=True)
    f_sub = _load_font(17, bold=False)
    f_row_title = _load_font(20, bold=True)
    f_row_tag = _load_font(14, bold=True)
    f_badge = _load_font(14, bold=True)
    f_foot = _load_font(13, bold=False)

    today_str = datetime.now().strftime("%d.%m.%Y")

    # Üst Bar
    draw.rounded_rectangle([(40, 24), (W - 40, 74)], radius=10, fill=(15, 23, 42), outline=(245, 158, 11), width=2)
    draw.ellipse([(58, 41), (74, 57)], fill=(16, 185, 129))
    draw.text((86, 37), "İLAN RADARI  |  KAMU, İŞKUR VE PERSONEL ALIM MONİTÖRÜ", font=f_top, fill=(255, 255, 255))
    t_bb = draw.textbbox((0, 0), today_str, font=f_top)
    draw.text((W - 60 - (t_bb[2] - t_bb[0]), 37), today_str, font=f_top, fill=(251, 191, 36))

    # Ana Başlık
    draw.text((42, 92), "GÜNÜN ÖNE ÇIKAN PERSONEL & İŞ İLANLARI", font=f_h1, fill=(255, 255, 255))
    draw.text((42, 134), "Resmi Gazete, Kariyer Kapısı, İŞKUR ve kamu kurumlarının güncel alım duyuruları:", font=f_sub, fill=(148, 163, 184))

    ry = 176
    rh = 114
    for idx, j in enumerate(jobs[:6]):
        is_top = idx < 2
        bg_c = (18, 36, 32) if is_top else (15, 23, 42)
        bd_c = (16, 185, 129) if is_top else (51, 65, 85)
        draw.rounded_rectangle([(40, ry), (W - 40, ry + rh)], radius=14, fill=bg_c, outline=bd_c, width=2 if is_top else 1)

        # Numara kutusu
        rk_bg = (245, 158, 11) if is_top else (30, 41, 59)
        rk_fg = (15, 23, 42) if is_top else (226, 232, 240)
        draw.rounded_rectangle([(58, ry + 24), (118, ry + 88)], radius=12, fill=rk_bg)
        rk_txt = f"{idx + 1}"
        rk_bb = draw.textbbox((0, 0), rk_txt, font=_load_font(24, bold=True))
        draw.text((88 - (rk_bb[2] - rk_bb[0]) // 2, ry + 41), rk_txt, font=_load_font(24, bold=True), fill=rk_fg)

        # İlan Başlığı (satır kaydırma veya kısaltma)
        t_str = j["title"]
        if len(t_str) > 64:
            t_str = t_str[:61].rsplit(" ", 1)[0] + "..."
        draw.text((138, ry + 22), t_str, font=f_row_title, fill=(255, 255, 255))

        # Alt Kategori & Resmi Kurum
        sub_str = f"{j['tag']}  •  {j.get('gov_name', 'Resmi İlan Metni (ilan.gov.tr)')}"
        draw.text((138, ry + 64), sub_str, font=f_row_tag, fill=(52, 211, 153) if is_top else (56, 189, 248))

        # Sağ Durum Rozeti
        b_txt = j["badge"]
        b_bb = draw.textbbox((0, 0), b_txt, font=f_badge)
        bw = (b_bb[2] - b_bb[0]) + 32
        bx1 = W - 62 - bw
        b_bg = (16, 185, 129) if is_top else (30, 41, 59)
        b_fg = (10, 20, 15) if is_top else (251, 191, 36)
        draw.rounded_rectangle([(bx1, ry + 36), (W - 62, ry + 78)], radius=8, fill=b_bg)
        draw.text((bx1 + 16, ry + 48), b_txt, font=f_badge, fill=b_fg)

        ry += rh + 12

    # Alt Başvuru Rehberi Kutusu
    draw.rounded_rectangle([(40, 938), (W - 40, 988)], radius=10, fill=(30, 27, 75), outline=(129, 140, 248), width=1)
    draw.text(
        (60, 953),
        "BAŞVURU ADRESLERİ:  ilan.gov.tr  •  kariyerkapisi.gov.tr/isealim  •  esube.iskur.gov.tr",
        font=_load_font(16, bold=True),
        fill=(224, 231, 255),
    )

    # Footer
    draw.line([(40, 1004), (W - 40, 1004)], fill=(30, 41, 59), width=1)
    draw.text((40, 1016), "Resmi kurum duyurularından derlenmiştir. Bilgilendirme amaçlıdır.", font=f_foot, fill=(148, 163, 184))
    draw.text((40, 1038), "Günlük Kamu, İŞKUR ve Özel Sektör İş İlanları Takibi: @ilanradari", font=_load_font(13, bold=True), fill=(251, 191, 36))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _get_application_steps(job: Dict) -> List[str]:
    """
    İlanın kurumuna ve türüne göre (Akademik, İŞKUR/İşçi, Askeri/Polis, Kariyer Kapısı, Genel)
    görselde gösterilecek %100 doğru başvuru adımlarını belirler.
    """
    title = job.get("title", "")
    summary = job.get("summary", "")
    tag = job.get("tag", "")
    comb = _tr_lower(f"{title} {summary} {tag}")

    # 1. Üniversite Akademik Kadroları (Öğretim Elemanı, Öğretim Üyesi, Araştırma/Öğretim Görevlisi)
    if any(k in comb for k in ("öğretim elemanı", "öğretim üyesi", "araştırma görevlisi", "öğretim görevlisi", "doçent", "profesör")) or tag == "AKADEMİK":
        return [
            "1. İlandaki fakülte, ALES taban puanı, dil ve özel şartları inceleyin.",
            "2. Başvuru formu, onaylı mezuniyet ve yayın dosyanızı eksiksiz hazırlayın.",
            "3. İlanda belirtilen usule göre (şahsen veya posta ile) Rektörlüğe teslim edin.",
        ]

    # 2. İŞKUR / Belediye Sürekli İşçi Alımları
    if any(k in comb for k in ("işkur", "iskur", "sürekli işçi", "belediye işçi", "temizlik görevlisi")) or tag == "İŞÇİ ALIMI":
        return [
            "1. esube.iskur.gov.tr portalına e-Devlet veya İŞKUR şifrenizle giriş yapın.",
            "2. İlan numarasını aratarak öğrenim ve ikamet şartlarını kontrol edin.",
            "3. Belirtilen son başvuru tarihine kadar sistemden başvurunuzu onaylayın.",
        ]

    # 3. Polis, Bekçi, Askeri ve Güvenlik Alımları
    if any(k in comb for k in ("polis", "pomem", "pmyo", "bekçi", "jandarma", "uzman erbaş", "subay", "astsubay", "msb")):
        return [
            "1. Resmi temin ekranına (pa.edu.tr / personeltemin.msb.gov.tr) giriş yapın.",
            "2. KPSS taban puanı, yaş, boy/kilo ve sağlık şartlarını kontrol edin.",
            "3. e-Devlet ile ön başvuruyu tamamlayıp sınav/mülakat takvimini takip edin.",
        ]

    # 4. Bakanlıklar & Kariyer Kapısı Sözleşmeli Personel Alımları
    if any(k in comb for k in ("kariyer kapısı", "kariyerkapisi", "bakanlığı", "başkanlığı", "uzman yardımcısı", "müfettiş", "sözleşmeli personel")):
        return [
            "1. kariyerkapisi.gov.tr/isealim adresine e-Devlet şifrenizle giriş yapın.",
            "2. Kurumun ilan kılavuzundaki öğrenim, KPSS ve özel şartları inceleyin.",
            "3. Formu doldurup istenen belgeleri yükleyerek başvurunuzu tamamlayın.",
        ]

    # 5. Genel Kamu Fallback (ilan.gov.tr resmi kılavuzu)
    return [
        "1. Resmi ilan kılavuzundaki (ilan.gov.tr) genel ve özel şartları inceleyin.",
        "2. Kurumun başvuru yöntemini (Kariyer Kapısı, İŞKUR veya Şahsen) teyit edin.",
        "3. İstenen evrakları eksiksiz hazırlayarak son başvuru gününe kadar iletin.",
    ]


def render_job_spotlight_image(
    job: Dict,
    output_path: str = "D:/faiz-radari/latest_ilan_spotlight.png",
) -> str:
    """Tek bir önemli personel alımı / iş ilanını detaylarıyla gösteren 1080x1080 Flaş İlan Kartı."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color=(8, 13, 25))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        r = int(12 + (8 - 12) * (y / H))
        g = int(20 + (14 - 20) * (y / H))
        b = int(34 + (26 - 34) * (y / H))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw.rectangle([(0, 0), (W, 10)], fill=(16, 185, 129))

    f_top = _load_font(18, bold=True)
    f_cat = _load_font(16, bold=True)
    f_h1 = _load_font(36, bold=True)
    f_sec = _load_font(18, bold=True)
    f_body = _load_font(21, bold=False)
    f_foot = _load_font(14, bold=False)

    today_str = datetime.now().strftime("%d.%m.%Y")

    # Üst Bar
    draw.rounded_rectangle([(40, 32), (W - 40, 88)], radius=10, fill=(18, 48, 38), outline=(16, 185, 129), width=2)
    draw.ellipse([(58, 52), (74, 68)], fill=(52, 211, 153))
    draw.text((86, 48), "YENİ İŞ & PERSONEL ALIMI  |  İLAN RADARI", font=f_top, fill=(255, 255, 255))
    t_bb = draw.textbbox((0, 0), today_str, font=f_cat)
    draw.text((W - 60 - (t_bb[2] - t_bb[0]), 50), today_str, font=f_cat, fill=(167, 243, 208))

    # Kategori Rozeti
    tag_lbl = f"{job['tag']}  •  {job['badge']}"
    tg_bb = draw.textbbox((0, 0), tag_lbl, font=f_cat)
    draw.rounded_rectangle([(40, 110), (76 + (tg_bb[2] - tg_bb[0]), 150)], radius=8, fill=(30, 41, 59), outline=(245, 158, 11), width=1)
    draw.text((58, 120), tag_lbl, font=f_cat, fill=(251, 191, 36))

    def _wrap(text: str, font, max_w: int) -> List[str]:
        words = text.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            bb = draw.textbbox((0, 0), test, font=font)
            if (bb[2] - bb[0]) <= max_w:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines

    # İlan Manşeti
    h_lines = _wrap(job["title"], f_h1, W - 90)[:3]
    hy = 176
    for hl in h_lines:
        draw.text((44, hy), hl, font=f_h1, fill=(255, 255, 255))
        hy += 48

    # İlan Detay Kutusu
    c1_y = max(hy + 20, 330)
    d_lines = _wrap(job["summary"], f_body, W - 140)[:5]
    c1_h = max(210, 84 + len(d_lines) * 34 + 20)
    draw.rounded_rectangle([(40, c1_y), (W - 40, c1_y + c1_h)], radius=16, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
    draw.rounded_rectangle([(40, c1_y + 14), (48, c1_y + c1_h - 14)], radius=4, fill=(245, 158, 11))
    draw.text((68, c1_y + 22), "İLAN DETAYLARI & BAŞVURU ÖZETİ", font=f_sec, fill=(251, 191, 36))
    draw.line([(68, c1_y + 54), (W - 68, c1_y + 54)], fill=(30, 41, 59), width=1)

    dy = c1_y + 72
    for dl in d_lines:
        draw.text((68, dy), dl, font=f_body, fill=(241, 245, 249))
        dy += 34

    # Başvuru Adımları Kutusu
    c2_y = c1_y + c1_h + 24
    c2_h = 225
    draw.rounded_rectangle([(40, c2_y), (W - 40, c2_y + c2_h)], radius=16, fill=(18, 36, 32), outline=(16, 185, 129), width=2)
    draw.text((68, c2_y + 22), "NASIL BAŞVURU YAPILIR? (3 ADIMDA REHBER)", font=f_sec, fill=(52, 211, 153))
    draw.line([(68, c2_y + 54), (W - 68, c2_y + 54)], fill=(30, 58, 47), width=1)
    steps = _get_application_steps(job)
    sy = c2_y + 72
    for st in steps:
        draw.text((68, sy), st, font=_load_font(18, bold=False), fill=(236, 253, 245))
        sy += 44

    # Alt Bilgi
    draw.line([(40, 968), (W - 40, 968)], fill=(30, 41, 59), width=1)
    draw.text((40, 984), "İş arayan arkadaşlarınızla ve aile gruplarınızla paylaşmayı unutmayın.", font=_load_font(15, bold=True), fill=(251, 191, 36))
    draw.text((40, 1012), "Günlük İş İlanları, Personel Alımı & Maaş Rehberi: @ilanradari", font=f_foot, fill=(148, 163, 184))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _ilan_reply_markup(official_url: str = "", official_name: str = "") -> str:
    import urllib.parse
    share_txt = urllib.parse.quote(
        "📋 Güncel kamu personel alımları, İŞKUR iş ilanları ve maaş/promosyon tabloları @ilanradari kanalında!\n👉 https://t.me/ilanradari"
    )
    rows = []
    if official_url:
        if "IlanDetay" in official_url or "kariyerkapisi" in official_url:
            btn_lbl = "🏛️ İlan Kılavuzu & Başvuru Şartları ↗"
        elif "ilan.gov.tr" in official_url:
            btn_lbl = "🏛️ Resmi İlan Sayfası (ilan.gov.tr) ↗"
        elif official_name:
            btn_lbl = f"🏛️ Resmi Başvuru ({official_name[:24]}) ↗"
        else:
            btn_lbl = "🏛️ Resmi İlan Sayfası & Başvuru ↗"
        rows.append([{"text": btn_lbl, "url": official_url}])
    rows.append([
        {"text": "📲 İş Arayan Arkadaşına Gönder", "url": f"https://t.me/share/url?url=https://t.me/ilanradari&text={share_txt}"},
        {"text": "🟢 WhatsApp Kanalımız", "url": ILAN_WHATSAPP_INVITE_URL},
    ])
    return json.dumps({"inline_keyboard": rows})


def send_welcome_and_pin(target_chat_id: str = ILAN_CHANNEL_ID) -> dict:
    """@ilanradari kanalına resmi açılış & karşılama mesajını gönderir ve en üste sabitler (Pin)."""
    welcome_text = (
        "🎯 <b>İLAN RADARI'NA HOŞ GELDİNİZ!</b>\n"
        "<i>Türkiye'nin Güncel İş İlanları, Kamu Personel Alımı ve Maaş Rehberi</i>\n\n"
        "Bu kanalda tıklama tuzağı başlıklar veya karmaşık linkler olmadan, her gün <b>tek bakışlık net tablolarla</b> şunları bulacaksınız:\n\n"
        "📋 <b>1. Kamu & İŞKUR Personel Alımları:</b> Bakanlık, belediye, şehir hastanesi, üniversite ve kamu kurumlarının KPSS'li ve KPSS şartsız güncel iş ilanları.\n"
        "💰 <b>2. Emekli Maaş Promosyonu Ligi:</b> Bankaların emeklilere sunduğu en yüksek nakit promosyon ve faizsiz kredi karşılaştırmaları.\n"
        "📊 <b>3. Meslek Meslek Maaş & Zam Hesapları:</b> Memur, kamu işçisi, emekli ve asgari ücret zam tabloları, kıdem tazminatı ve sosyal destek rehberleri.\n\n"
        "🔔 <b>Önemli İlanları Kaçırmamak İçin:</b>\n"
        "• Sağ üstten kanal bildirimlerini (🔔) açmayı,\n"
        "• İş arayan yakınlarınızı ve arkadaşlarınızı aşağıdaki butonla davet etmeyi unutmayın!"
    )
    logo_path = Path(__file__).parent / "ilan_radari_logo.jpg"
    with open(logo_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": welcome_text,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup(),
            },
            files={"photo": f},
            timeout=25,
        ).json()

    if res.get("ok"):
        msg_id = res["result"]["message_id"]
        requests.post(
            f"{API_BASE}/pinChatMessage",
            json={"chat_id": target_chat_id, "message_id": msg_id, "disable_notification": False},
            timeout=10,
        )
        print(f"[BAŞARILI] Karşılama mesajı {target_chat_id} kanalına gönderildi ve sabitlendi (Pin ID: {msg_id})!")
    return res


def send_daily_jobs_report(target_chat_id: str = ILAN_CHANNEL_ID) -> dict:
    """Günün öne çıkan 6 kamu ve İŞKUR iş ilanını tek tabloda @ilanradari kanalında paylaşır (Akşam Özeti)."""
    jobs = fetch_live_job_announcements(limit=6)
    if not jobs:
        print("[UYARI] Güncel iş ilanı bulunamadı.")
        return {"ok": False}

    img_path = render_daily_jobs_table_image(jobs, str(Path(__file__).parent / "latest_ilan_table.png"))
    now_str = datetime.now().strftime("%d.%m.%Y")

    top_hook = jobs[0]["title"]
    extra_cnt = max(0, len(jobs[:6]) - 1)
    hook_line = f"🔥 <b>{top_hook}</b> (+{extra_cnt} Yeni Kamu & İŞKUR İlanı!)" if extra_cnt > 0 else f"🔥 <b>{top_hook}</b>"

    bullet_lines = []
    for i, j in enumerate(jobs[:6]):
        t_clean = j["title"][:72].rstrip()
        direct_url = j.get("direct_url") or j.get("gov_url", "https://www.ilan.gov.tr")
        bullet_lines.append(
            f"{i + 1}️⃣ <b>{t_clean}</b>\n"
            f"   🏷️ <i>{j['tag']} • {j.get('badge', 'GÜNCEL')}</i>\n"
            f"   👉 <a href=\"{direct_url}\">İlan Detayı ve Başvuru İçin Tıklayın ↗</a>"
        )
    bullets = "\n\n".join(bullet_lines)

    caption = (
        f"{hook_line}\n"
        "📋 <b>GÜNÜN KAMU & İŞKUR İLANLARI AKŞAM ÖZETİ:</b>\n\n"
        f"{bullets}\n\n"
        "🏛️ <b>Resmi Başvuru & İlan Portalları:</b>\n"
        "• <a href=\"https://www.ilan.gov.tr\">Basın İlan Kurumu (ilan.gov.tr)</a>  |  "
        "<a href=\"https://esube.iskur.gov.tr\">İŞKUR e-Şube</a>  |  "
        "<a href=\"https://kariyerkapisi.gov.tr/isealim\">Kariyer Kapısı</a>\n\n"
        "📲 <i>İş arayan ve kamuya atanmak isteyen sevdiklerinizle aşağıdaki butonla paylaşabilirsiniz.</i>\n\n"
        f"📅 <i>{now_str} • @ilanradari</i>"
    )

    with open(img_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup("https://www.ilan.gov.tr", "Resmi İlan Portalı (ilan.gov.tr)"),
            },
            files={"photo": f},
            timeout=30,
        ).json()
    print(f"[İLAN TABLOSU] {target_chat_id} -> {res.get('ok')}")
    if target_chat_id == ILAN_CHANNEL_ID:
        post_ilan_to_whatsapp(img_path, caption)
    return res


def send_spotlight_job_report(target_chat_id: str = ILAN_CHANNEL_ID, force: bool = False, job_override: Optional[Dict] = None) -> dict:
    """Henüz paylaşılmamış en yüksek puanlı yeni personel alımı ilanını tekil detay kartıyla paylaşır."""
    cache = load_ilan_cache()
    history = cache.get("dispatched_headlines", [])
    
    if job_override:
        chosen = job_override
    else:
        jobs = fetch_live_job_announcements(limit=10)
        chosen = None
        for j in jobs:
            if force or not _is_dup_headline(j["title"], history):
                chosen = j
                break

    if not chosen:
        print("[BİLGİ] Paylaşılacak yeni tekil flaş ilan bulunamadı (tümü daha önce paylaşıldı).")
        return {"ok": False, "reason": "no_new_job"}

    img_path = render_job_spotlight_image(chosen, str(Path(__file__).parent / "latest_ilan_spotlight.png"))
    now_str = datetime.now().strftime("%d.%m.%Y")
    gov_name = chosen.get("gov_name", "Resmi İlan Metni (ilan.gov.tr)")
    direct_url = chosen.get("direct_url") or chosen.get("gov_url", "https://www.ilan.gov.tr")

    details_part = f"{chosen['details']}\n\n" if chosen.get("details") else ""
    caption = (
        f"📢 <b>{chosen['title']}</b>\n\n"
        f"{chosen['summary']}\n\n"
        f"{details_part}"
        f"🏛️ <b>Resmi İlan & Başvuru Detayı:</b>\n"
        f"👉 <a href=\"{direct_url}\">İlan Detayı ve Başvuru İçin Tıklayın ↗</a>\n\n"
        "📲 <i>İş arayan ve kamuya atanmak isteyen sevdiklerinizle paylaşabilirsiniz.</i>\n\n"
        f"📅 <i>{now_str} • @ilanradari</i>"
    )

    with open(img_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup(direct_url, gov_name),
            },
            files={"photo": f},
            timeout=30,
        ).json()

    if res.get("ok") and target_chat_id == ILAN_CHANNEL_ID:
        history.append(chosen["title"])
        cache["dispatched_headlines"] = history[-60:]
        save_ilan_cache(cache)
        post_ilan_to_whatsapp(img_path, caption)

    print(f"[FLAŞ İLAN KARTI] {target_chat_id} ({chosen['title'][:45]}...) -> {res.get('ok')}")
    return res


def get_daily_fallback_guide(day_idx: int = None) -> Dict:
    """
    O saat diliminde yeni bir iş ilanı çıkmamışsa kanalın canlı kalması için
    haftanın 7 gününe özel 7 farklı 'Maaş, Promosyon & Kariyer Rehberi Tablosu' üretir.
    """
    if day_idx is None:
        day_idx = datetime.now(timezone(timedelta(hours=3))).weekday()

    guides = [
        # 0 - Pazartesi: Bankaların Güncel Emekli Maaş Promosyonu Ligi
        {
            "hook": "💰 Emekliye 24.000 TL'ye Varan Nakit Promosyon! Banka Banka Güncel Liste",
            "header_badge": "EMEKLİ MAAŞ PROMOSYONU LİGİ",
            "title": "EN YÜKSEK EMEKLİ PROMOSYONU VEREN 6 BANKA",
            "subtitle": "SGK (SSK, Bağ-Kur ve Emekli Sandığı) emeklilerine sunulan güncel nakit promosyonlar:",
            "gov_name": "Sosyal Güvenlik Kurumu (SGK)",
            "gov_url": "https://www.sgk.gov.tr",
            "footer_note": "Maaş taşıma başvuruları e-Devlet (turkiye.gov.tr) veya ilgili bankaların mobil şubelerinden yapılır.",
            "rows": [
                {"title": "VakıfBank Emekli Paketi", "sub": "12.000 TL Nakit Promosyon + Troy Emekli Kart Ek Nakit Avantajı", "badge": "24.000 TL'YE VARAN"},
                {"title": "ING Türkiye Emekli Promosyonu", "sub": "Koşulsuz Nakit Promosyon + Otomatik Fatura Talimatı Ödülü", "badge": "20.000 TL'YE VARAN"},
                {"title": "Yapı Kredi Emekli Paketi", "sub": "Maaş Tutarına Göre Nakit + Fatura & Kredi Kartı Ek Ödülü", "badge": "18.000 TL'YE VARAN"},
                {"title": "Akbank Emekli Promosyonu", "sub": "15.000 TL Nakit Promosyon + 2.500 TL Chip-Para Fırsatı", "badge": "17.500 TL'YE VARAN"},
                {"title": "Garanti BBVA & QNB", "sub": "Maaş Dilimine Göre Koşulsuz Nakit + Ek Fatura Bonusu", "badge": "15.000 - 16.250 TL"},
                {"title": "Ziraat Bankası & Halkbank", "sub": "12.000 TL Kamu Promosyonu + Emekliye Özel Faizsiz Nakit", "badge": "12.000 TL + DESTEK"},
            ],
        },
        # 1 - Salı: Meslek Meslek Güncel Kamu & Sözleşmeli Personel Maaşları
        {
            "hook": "📊 Kamu ve Sözleşmeli Personel Maaşları Ne Kadar? Meslek Meslek Net Tablo",
            "header_badge": "KAMU & MEMUR MAAŞ REHBERİ",
            "title": "MESLEK MESLEK GÜNCEL KAMU PERSONEL MAAŞLARI",
            "subtitle": "Yeni başlayan ve derece/kademeye göre kamu personeli ortalama net maaş göstergeleri:",
            "gov_name": "Kariyer Kapısı İşe Alım Platformu",
            "gov_url": "https://kariyerkapisi.gov.tr/isealim",
            "footer_note": "Maaş tutarları aile yardımı, döner sermaye, ek ders ve bölge tazminatına göre değişiklik gösterebilir.",
            "rows": [
                {"title": "Kamu Mühendisi & Teknik Kadro", "sub": "Bakanlıklar, DSİ, Karayolları, TİGEM Sözleşmeli/Kadrolu", "badge": "68.000 - 74.000 TL"},
                {"title": "Polis Memuru & Jandarma Personeli", "sub": "Emniyet Genel Müdürlüğü & Jandarma Görev Tazminatı Dahil", "badge": "64.000 - 71.000 TL"},
                {"title": "Hemşire & Sağlık Teknikeri (4/B)", "sub": "Sağlık Bakanlığı, Şehir Hastaneleri ve Üniversite Hastaneleri", "badge": "56.000 - 65.000 TL"},
                {"title": "Öğretmen (MEB Kadrolu / Sözleşmeli)", "sub": "Temel Maaş (Ek Ders ve Uzman Öğretmenlik Tazminatı Hariç)", "badge": "54.000 - 62.000 TL"},
                {"title": "Büro Personeli, VHKİ & zabıt Katibi", "sub": "Bakanlıklar, Adliyeler, Üniversiteler ve İl Müdürlükleri", "badge": "51.000 - 67.000 TL"},
                {"title": "Koruma ve Güvenlik Görevlisi & Destek", "sub": "Kamu Kurumları 4/B Sözleşmeli ve 4/D Sürekli İşçi Kadroları", "badge": "49.000 - 69.000 TL"},
            ],
        },
        # 2 - Çarşamba: KPSS 50 - 60 - 70 Puanla Alım Yapan Kamu Kurumları
        {
            "hook": "🎓 KPSS 50, 60 ve 70 Puanla Hangi Kamu Kurumlarına Girilir? Başvuru Rehberi",
            "header_badge": "KPSS PUAN & KURUM REHBERİ",
            "title": "KPSS 50 - 60 - 70 PUANLA ALIM YAPAN KURUMLAR",
            "subtitle": "Yüksek KPSS puanı olmadan açıktan ve sözleşmeli (4/B) personel alan başlıca kurumlar:",
            "gov_name": "Kariyer Kapısı İşe Alım Platformu",
            "gov_url": "https://kariyerkapisi.gov.tr/isealim",
            "footer_note": "Tüm açıktan atama ve sözleşmeli personel ilanları e-Devlet Kariyer Kapısı üzerinden yayınlanır.",
            "rows": [
                {"title": "Üniversiteler & Üniversite Hastaneleri", "sub": "Büro personeli, destek personeli, tekniker, hemşire (Mülakatsız puan sırasıyla)", "badge": "KPSS 50 - 65 PUAN"},
                {"title": "Adalet Bakanlığı & CTE Personel Alımı", "sub": "Zabıt katibi, mübaşir, infaz koruma memuru (İKM), güvenlik görevlisi", "badge": "KPSS 70 TABAN PUAN"},
                {"title": "İçişleri Bakanlığı, AFAD & Göç İdaresi", "sub": "Büro personeli, çağrı karşılama (112), teknisyen ve koruma güvenlik", "badge": "KPSS 60 - 65 PUAN"},
                {"title": "Belediyeler (Zabıta & İtfaiye Eri)", "sub": "Belediyelerin kendi bünyesinde yaptığı memur, zabıta ve itfaiye alımları", "badge": "KPSS 60 - 70 PUAN"},
                {"title": "Polis Akademisi (POMEM & Bekçi)", "sub": "Ön lisans KPSS 65, Lisans KPSS 60 taban puan ile polis memuru alımı", "badge": "KPSS 60 - 65 PUAN"},
                {"title": "Gençlik ve Spor Bakanlığı (GSB & KYK)", "sub": "Yurt yönetim memuru, antrenör, gençlik çalışanı ve destek personeli", "badge": "KPSS 60 TABAN PUAN"},
            ],
        },
        # 3 - Perşembe: Kıdem Tazminatı, İhbar Tazminatı & İşsizlik Maaşı Hakları
        {
            "hook": "📑 İstifa Eden Kıdem Tazminatı Alabilir mi? Çalışanların Bilmesi Gereken 6 Hak",
            "header_badge": "ÇALIŞAN HAKLARI & TAZMİNAT REHBERİ",
            "title": "KIDEM TAZMİNATI VE İŞSİZLİK MAAŞI REHBERİ",
            "subtitle": "Özel sektör ve kamu işçilerinin tazminat ve İŞKUR işsizlik ödeneği şartları:",
            "gov_name": "Çalışma Bakanlığı & İŞKUR e-Şube",
            "gov_url": "https://esube.iskur.gov.tr",
            "footer_note": "İşsizlik maaşı başvuruları işten ayrıldıktan sonraki 30 gün içinde e-Devlet veya İŞKUR üzerinden yapılır.",
            "rows": [
                {"title": "Her Yıl İçin 30 Günlük Brüt Maaş", "sub": "Aynı işyerinde en az 1 yıl çalışan işçi, her tam yıl için 1 brüt maaş kıdem alır", "badge": "KIDEM HAKKI"},
                {"title": "SGK Emeklilik & Prim Günüyle İstifa", "sub": "Yaş hariç emeklilik prim gününü dolduran çalışan kendi istifa etse de tazminat alır", "badge": "İSTİFADA TAZMİNAT"},
                {"title": "Askerlik ve Evlilik Nedeniyle Ayrılış", "sub": "Erkek çalışan askerlik, kadın çalışan evlilikten sonraki 1 yıl içinde tazminatlı ayrılabilir", "badge": "YASAL HAK"},
                {"title": "Maaşın Eksik/Geç Yatması (Haklı Fesih)", "sub": "Ücreti zamanında ödenmeyen veya SGK primi eksik yatan işçi haklı fesihle tazminat alır", "badge": "İŞ KANUNU 24/II"},
                {"title": "İŞKUR İşsizlik Maaşı (6 - 10 Ay)", "sub": "Son 3 yılda en az 600 gün primi olan ve kendi kusuru dışında ayrılanlara her ay ödenir", "badge": "İŞSİZLİK ÖDENEĞİ"},
                {"title": "İhbar Süresi ve İhbar Tazminatı", "sub": "Kıdeme göre 2 ila 8 hafta önceden bildirim yapılmazsa peşin ihbar tazminatı ödenir", "badge": "2 - 8 HAFTA ÜCRET"},
            ],
        },
        # 4 - Cuma: İŞKUR & Kurum Dışı KPSS Şartsız Kamu İşçisi Başvuru Rehberi
        {
            "hook": "🏛️ KPSS Şartsız Kamu İşçisi Alımlarına Nasıl Başvurulur? İŞKUR 6 Adım Rehberi",
            "header_badge": "KPSS ŞARTSIZ İŞKUR REHBERİ",
            "title": "KPSS ŞARTSIZ KAMU İŞÇİSİ ALIMI REHBERİ",
            "subtitle": "Sınavsız / noter kurasıyla sürekli işçi alan kamu kurumları ve başvuru kanalları:",
            "gov_name": "İŞKUR Resmi e-Şube Başvuru Portalı",
            "gov_url": "https://esube.iskur.gov.tr",
            "footer_note": "Başvurular tamamen ücretsizdir; İŞKUR e-Şube veya ALO 170 hattı üzerinden elektronik ortamda yapılır.",
            "rows": [
                {"title": "Sağlık Bakanlığı Sürekli İşçi Alımı", "sub": "Temizlik görevlisi, güvenlik görevlisi, klinik destek, şoför (Noter kurası ile)", "badge": "KPSS ŞARTSIZ"},
                {"title": "İŞKUR 'Kurum Dışı Kamu İşçi' Ekranı", "sub": "Belediye şirketleri (BELTAŞ, İSPER, ANFA vb.) büro, şoför ve saha personeli", "badge": "SINAVSIZ ALIM"},
                {"title": "Milli Eğitim Bakanlığı (MEB & İUP)", "sub": "Okullara temizlik, güvenlik ve bakım onarım personeli (İŞKUR üzerinden)", "badge": "KPSS ŞARTSIZ"},
                {"title": "DSİ, Karayolları (KGM) & Orman (OGM)", "sub": "Operatör, şoför, usta, bekçi ve orman işçisi kadroları", "badge": "NOTER KURASI"},
                {"title": "Üniversite ve Şehir Hastaneleri (4/D)", "sub": "En az ilkokul ve lise mezunu kadrolu sürekli işçi alımları", "badge": "4/D KADROLU İŞÇİ"},
                {"title": "Toplum Yararına Programlar (TYP)", "sub": "Kamu kurumlarında geçici süreli sigortalı ve maaşlı çalışma programları", "badge": "e-DEVLET / İŞKUR"},
            ],
        },
        # 5 - Cumartesi: Banka Personel Alımları & Sınavsız Başvuru Kanalları
        {
            "hook": "🏦 Bankalarda Gişe, Çağrı Merkezi ve Uzman Yardımcısı Alımları! Nasıl Başvurulur?",
            "header_badge": "BANKA KARİYER & ALIM REHBERİ",
            "title": "BANKA PERSONEL ALIMI VE BAŞVURU REHBERİ",
            "subtitle": "KPSS şartı olmadan kendi sınav/mülakatıyla personel alan kamu ve özel bankalar:",
            "gov_name": "İŞKUR & Resmi Banka Kariyer Portalları",
            "gov_url": "https://esube.iskur.gov.tr",
            "footer_note": "Özel bankalar yıl boyunca kendi kariyer sitelerinden, kamu bankaları ise yılda 1-2 kez toplu sınavla alım yapar.",
            "rows": [
                {"title": "Ziraat Bankası, VakıfBank & Halkbank", "sub": "Servis görevlisi (gişe), uzman yardımcısı ve müfettiş yardımcısı toplu sınavları", "badge": "KAMU BANKALARI"},
                {"title": "İş Bankası, Garanti BBVA & Yapı Kredi", "sub": "Memur, gişe yetkilisi, ticari/bireysel satış ve genel müdürlük kadroları", "badge": "KPSS ŞARTSIZ"},
                {"title": "Akbank, QNB & DenizBank Kariyer", "sub": "En az lise/ön lisans mezunu çağrı merkezi ve lisans mezunu şube kadroları", "badge": "YIL BOYU AÇIK"},
                {"title": "Banka Çağrı Merkezi (Home Office)", "sub": "Deneyimsiz yeni mezunlara açık, uzaktan veya hibrit çalışma imkanı", "badge": "YENİ MEZUN"},
                {"title": "Kuveyt Türk, Albaraka & Vakıf Katılım", "sub": "Katılım bankacılığı şube gişe ve müşteri ilişkileri yetkilisi alımları", "badge": "KATILIM BANKASI"},
                {"title": "Merkez Bankası (TCMB) & BDDK / SPK", "sub": "Uzman yardımcısı, memur, güvenlik ve teknisyen kadroları", "badge": "ÜST KURUL MAAŞI"},
            ],
        },
        # 6 - Pazar: Haftanın En Çok Aranan 6 Resmi Başvuru Kapısı
        {
            "hook": "🏛️ İş Arayanların Her Gün Kontrol Etmesi Gereken 6 Resmi Devlet Başvuru Kapısı!",
            "header_badge": "RESMİ BAŞVURU KAPILARI REHBERİ",
            "title": "TÜRKİYE'NİN 6 RESMİ İŞ & İLAN BAŞVURU KAPISI",
            "subtitle": "Aracı sitelere gerek kalmadan doğrudan başvuru yapabileceğiniz resmi devlet portalları:",
            "gov_name": "Kariyer Kapısı İşe Alım Platformu",
            "gov_url": "https://kariyerkapisi.gov.tr/isealim",
            "footer_note": "Tüm resmi başvurular e-Devlet şifresiyle ücretsiz yapılır; hiçbir kamu kurumu başvuru için ücret talep etmez.",
            "rows": [
                {"title": "1. Kariyer Kapısı İşe Alım", "sub": "kariyerkapisi.gov.tr/isealim • Tüm bakanlık ve kamu sözleşmeli alımları", "badge": "e-DEVLET GİRİŞLİ"},
                {"title": "2. İŞKUR Resmi e-Şube Portalı", "sub": "esube.iskur.gov.tr • Kamu sürekli işçi ve özel sektör açık iş ilanları", "badge": "KPSS ŞARTSIZ"},
                {"title": "3. İŞKUR Kurum Dışı Kamu İşçi İlanları", "sub": "iskur.gov.tr/baglantilar/kurum-disi-kamu-isci-alimi-ilani • Belediye alımları", "badge": "BELEDİYE KADROSU"},
                {"title": "4. Basın İlan Kurumu (ilan.gov.tr)", "sub": "ilan.gov.tr • Kamu, akademik ve askeri tüm resmi personel alım ilanları", "badge": "RESMİ İLAN"},
                {"title": "5. Resmi Gazete Çeşitli İlanlar Bölümü", "sub": "resmigazete.gov.tr • Her gece 00:00'da yayınlanan üniversite ve kurum ilanları", "badge": "RESMİ GAZETE"},
                {"title": "6. Polis Akademisi & JSGA & MSB PERTEM", "sub": "pa.edu.tr • jandarma.gov.tr • personeltemin.msb.gov.tr (Polis, Bekçi, Uzman)", "badge": "EMNİYET & TSK"},
            ],
        },
    ]
    return guides[day_idx % len(guides)]


def send_fallback_guide_report(target_chat_id: str = ILAN_CHANNEL_ID) -> dict:
    """Yeni iş ilanı olmadığında günün Maaş / Promosyon / Kariyer Rehberi tablosunu üretir ve paylaşır."""
    g = get_daily_fallback_guide()
    jobs_like = [
        {
            "title": r["title"],
            "tag": r["sub"],
            "badge": r["badge"],
            "source": g["gov_name"],
            "gov_name": r["sub"],
            "gov_url": g["gov_url"],
        }
        for r in g["rows"]
    ]

    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color=(8, 13, 25))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        r_c = int(8 + (16 - 8) * (y / H))
        g_c = int(13 + (24 - 13) * (y / H))
        b_c = int(25 + (45 - 25) * (y / H))
        draw.line([(0, y), (W, y)], fill=(r_c, g_c, b_c))

    draw.rectangle([(0, 0), (W, 8)], fill=(16, 185, 129))
    f_top = _load_font(17, bold=True)
    f_h1 = _load_font(31, bold=True)
    f_sub = _load_font(17, bold=False)
    f_row_title = _load_font(20, bold=True)
    f_row_sub = _load_font(15, bold=False)
    f_badge = _load_font(14, bold=True)
    f_foot = _load_font(13, bold=False)

    today_str = datetime.now().strftime("%d.%m.%Y")
    draw.rounded_rectangle([(40, 24), (W - 40, 74)], radius=10, fill=(15, 23, 42), outline=(16, 185, 129), width=2)
    draw.ellipse([(58, 41), (74, 57)], fill=(52, 211, 153))
    draw.text((86, 37), f"İLAN RADARI  |  {g['header_badge']}", font=f_top, fill=(255, 255, 255))
    t_bb = draw.textbbox((0, 0), today_str, font=f_top)
    draw.text((W - 60 - (t_bb[2] - t_bb[0]), 37), today_str, font=f_top, fill=(52, 211, 153))

    draw.text((42, 92), g["title"], font=f_h1, fill=(255, 255, 255))
    draw.text((42, 134), g["subtitle"], font=f_sub, fill=(148, 163, 184))

    ry = 176
    rh = 114
    for idx, row in enumerate(g["rows"][:6]):
        is_top = idx < 2
        bg_c = (18, 36, 32) if is_top else (15, 23, 42)
        bd_c = (16, 185, 129) if is_top else (51, 65, 85)
        draw.rounded_rectangle([(40, ry), (W - 40, ry + rh)], radius=14, fill=bg_c, outline=bd_c, width=2 if is_top else 1)

        rk_bg = (245, 158, 11) if is_top else (30, 41, 59)
        rk_fg = (15, 23, 42) if is_top else (226, 232, 240)
        draw.rounded_rectangle([(58, ry + 24), (118, ry + 88)], radius=12, fill=rk_bg)
        rk_txt = f"{idx + 1}"
        rk_bb = draw.textbbox((0, 0), rk_txt, font=_load_font(24, bold=True))
        draw.text((88 - (rk_bb[2] - rk_bb[0]) // 2, ry + 41), rk_txt, font=_load_font(24, bold=True), fill=rk_fg)

        draw.text((138, ry + 22), row["title"], font=f_row_title, fill=(255, 255, 255))
        draw.text((138, ry + 62), row["sub"][:68], font=f_row_sub, fill=(148, 163, 184))

        b_txt = row["badge"]
        b_bb = draw.textbbox((0, 0), b_txt, font=f_badge)
        bw = (b_bb[2] - b_bb[0]) + 32
        bx1 = W - 62 - bw
        b_bg = (16, 185, 129) if is_top else (30, 41, 59)
        b_fg = (10, 20, 15) if is_top else (251, 191, 36)
        draw.rounded_rectangle([(bx1, ry + 36), (W - 62, ry + 78)], radius=8, fill=b_bg)
        draw.text((bx1 + 16, ry + 48), b_txt, font=f_badge, fill=b_fg)
        ry += rh + 12

    draw.rounded_rectangle([(40, 938), (W - 40, 988)], radius=10, fill=(30, 27, 75), outline=(129, 140, 248), width=1)
    draw.text((60, 953), g["footer_note"][:95], font=_load_font(15, bold=True), fill=(224, 231, 255))
    draw.line([(40, 1004), (W - 40, 1004)], fill=(30, 41, 59), width=1)
    draw.text((40, 1016), "Resmi kurum verilerinden derlenmiştir. Bilgilendirme amaçlıdır.", font=f_foot, fill=(148, 163, 184))
    draw.text((40, 1038), "Günlük İş İlanları, Personel Alımı & Maaş Rehberi: @ilanradari", font=_load_font(13, bold=True), fill=(251, 191, 36))

    out_path = str(Path(__file__).parent / "latest_ilan_guide.png")
    img.save(out_path, format="PNG", optimize=True)

    bullets = "\n".join([f"• <b>{r['title']}:</b> <i>{r['badge']}</i>" for r in g["rows"][:6]])
    caption = (
        f"<b>{g['hook']}</b>\n"
        f"📌 <i>{g['subtitle']}</i>\n\n"
        f"{bullets}\n\n"
        f"🏛️ <b>Resmi İşlem & Başvuru Adresi:</b>\n"
        f"👉 <a href=\"{g['gov_url']}\">Resmi Sayfaya Git ↗</a>\n\n"
        "📲 <i>Bu rehberi faydalı olabilecek arkadaşlarınızla aşağıdaki butonla paylaşabilirsiniz.</i>"
    )
    with open(out_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup(g["gov_url"], g["gov_name"]),
            },
            files={"photo": f},
            timeout=30,
        ).json()
    print(f"[YEDEK REHBER TABLOSU] {target_chat_id} ({g['header_badge']}) -> {res.get('ok')}")
    if target_chat_id == ILAN_CHANNEL_ID:
        post_ilan_to_whatsapp(out_path, caption)
    return res


def run_ilan_auto_slot() -> None:
    """
    GitHub Actions her çalıştığında @ilanradari kanalı için:
    - Gece 21:00 - 08:30 arası sessiz saat kuralına uyar.
    - GÜN BOYUNCA (08:30 - 18:30): Yeni açılan sıcak kamu/İŞKUR ilanlarını sırasıyla
      tekil 'Flaş İlan Kartı' (Spotlight) olarak paylaşır. Yeni ilan yoksa haftanın rehberini sunar.
    - AKŞAM (19:00 - 20:30): Günün tüm alımlarını toparlayan 'Günün Özet Tablosu' infografiğini
      ve doğrudan linkli listesini akşam bülteni olarak paylaşır.
    """
    now_tr = datetime.now(timezone(timedelta(hours=3)))
    h = now_tr.hour
    if h >= 21 or h < 8:
        return

    today_str = now_tr.strftime("%Y-%m-%d")
    cache = load_ilan_cache()
    daily = cache.get("daily_dispatched", {})
    today_list = daily.get(today_str, [])

    # 1. AKŞAM ÖZET TABLOSU (19:00 - 20:59 arası günde 1 kez)
    if h in (19, 20) and "daily_table" not in today_list:
        res = send_daily_jobs_report(ILAN_CHANNEL_ID)
        if res.get("ok"):
            today_list.append("daily_table")
            daily[today_str] = today_list
            cache["daily_dispatched"] = daily
            save_ilan_cache(cache)

    # 2. GÜN İÇİ YENİ AÇILAN TEKİL İLANLAR (08:30 - 18:59 arası)
    elif h in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18) and f"spotlight_{h // 2}" not in today_list:
        res = send_spotlight_job_report(ILAN_CHANNEL_ID)
        if res.get("ok"):
            today_list.append(f"spotlight_{h // 2}")
            daily[today_str] = today_list
            cache["daily_dispatched"] = daily
            save_ilan_cache(cache)
        elif "fallback_guide" not in today_list:
            # Yeni ilan yoksa günde 1 kez haftanın gününe özel Maaş/Promosyon/Kariyer Rehberi paylaş
            res_fb = send_fallback_guide_report(ILAN_CHANNEL_ID)
            if res_fb.get("ok"):
                today_list.append("fallback_guide")
                today_list.append(f"spotlight_{h // 2}")
                daily[today_str] = today_list
                cache["daily_dispatched"] = daily
                save_ilan_cache(cache)


if __name__ == "__main__":
    if "--init" in sys.argv:
        send_welcome_and_pin(ILAN_CHANNEL_ID)
        send_daily_jobs_report(ILAN_CHANNEL_ID)
        send_spotlight_job_report(ILAN_CHANNEL_ID, force=True)
    elif "--sync-whatsapp" in sys.argv:
        import time
        welcome_cap = (
            "🎯 <b>İLAN RADARI WHATSAPP KANALINA HOŞ GELDİNİZ!</b>\n"
            "<i>Türkiye'nin Güncel İş İlanları, Kamu Personel Alımı ve Maaş Rehberi</i>\n\n"
            "Bu kanalda her gün tek bakışlık net tablolarla şunları bulacaksınız:\n"
            "📋 <b>1. Kamu & İŞKUR Personel Alımları:</b> Bakanlık, belediye, şehir hastanesi ve üniversite iş ilanları\n"
            "💰 <b>2. Emekli Maaş Promosyonu Ligi:</b> Bankaların en yüksek nakit promosyon karşılaştırmaları\n"
            "📊 <b>3. Meslek Meslek Maaş & Zam Hesapları:</b> Memur, işçi, emekli ve asgari ücret zam tabloları"
        )
        post_ilan_to_whatsapp(str(Path(__file__).parent / "ilan_radari_logo.jpg"), welcome_cap)
        time.sleep(2)

        jobs = fetch_live_job_announcements(limit=6)
        if jobs:
            img_table = render_daily_jobs_table_image(jobs, str(Path(__file__).parent / "latest_ilan_table.png"))
            now_str = datetime.now().strftime("%d.%m.%Y")
            top_hook = jobs[0]["title"]
            bullets = "\n".join([f"{i + 1}️⃣ <b>{j['title'][:78]}</b> (<i>{j['tag']}</i>)" for i, j in enumerate(jobs[:6])])
            table_cap = (
                f"🔥 <b>{top_hook} (+{len(jobs[:6])-1} Yeni Kamu & İŞKUR İlanı!)</b>\n"
                f"📋 <i>Günün Öne Çıkan Personel Alımları ({now_str}):</i>\n\n"
                f"{bullets}\n\n"
                "🏛️ <b>Resmi Başvuru Portalları:</b>\n"
                "• https://www.ilan.gov.tr (Resmi İlan Portalı)\n"
                "• https://kariyerkapisi.gov.tr/isealim (Kariyer Kapısı İşe Alım)\n"
                "• https://esube.iskur.gov.tr (İŞKUR e-Şube)"
            )
            post_ilan_to_whatsapp(img_table, table_cap)
            time.sleep(2)

            for j_spot in jobs[:2]:
                img_sp = render_job_spotlight_image(j_spot, str(Path(__file__).parent / "latest_ilan_spotlight.png"))
                g_name = j_spot.get("gov_name", "Resmi İlan Metni (ilan.gov.tr)")
                g_url = j_spot.get("direct_url") or j_spot.get("gov_url", "https://www.ilan.gov.tr")
                cap_sp = (
                    f"🚨 <b>{j_spot['title']}</b>\n"
                    f"🏷️ <i>{j_spot['tag']} • {j_spot['badge']} ({now_str})</i>\n\n"
                    f"📝 <b>İlan Özeti:</b>\n{j_spot['summary']}\n\n"
                    f"🏛️ <b>Resmi Başvuru & Kurum Sayfası:</b>\n👉 {g_name} ({g_url})"
                )
                post_ilan_to_whatsapp(img_sp, cap_sp)
                time.sleep(2)

        for mid in (5, 6, 7, 9, 10, 12):
            requests.post(
                f"{API_BASE}/editMessageReplyMarkup",
                json={"chat_id": ILAN_CHANNEL_ID, "message_id": mid, "reply_markup": _ilan_reply_markup("https://www.ilan.gov.tr", "Resmi İlan Portalı (ilan.gov.tr)")},
                timeout=10,
            )
    elif "--announce-on-faizradari" in sys.argv:
        import time
        import base64
        import shutil
        import subprocess
        from bot import WHATSAPP_CHANNEL_ID, post_to_x, post_to_buffer_instagram

        card_path = str(Path(__file__).parent / "ilan_radari_magfi_1080x1080.png")
        vid_path = str(Path(__file__).parent / "ilan_radari_magfi_video_15sn.mp4")

        # 1. TELEGRAM (@faizradari)
        tg_caption = (
            "📢 <b>BİLGİLENDİRME: YENİ 'İLAN RADARI' SAYFAMIZ AÇILDI!</b> 🎯\n\n"
            "Değerli takipçilerimiz; Türkiye genelindeki güncel <b>kamu personel alımlarını, İŞKUR iş ilanlarını, banka personel alımlarını</b> ve <b>meslek meslek maaş / emekli promosyon tablolarını</b> artık yeni <b>İlan Radarı</b> kanallarımızda paylaşıyoruz.\n\n"
            "📋 <b>İlan Radarı'nda Her Gün Neler Paylaşılıyor?</b>\n"
            "1️⃣ <b>Bakanlık, Hastane & Üniversite Alımları:</b> KPSS'li sözleşmeli personel ve memur ilanları\n"
            "2️⃣ <b>İŞKUR & Belediye İlanları:</b> KPSS şartsız sürekli işçi ve kurum dışı personel alımları\n"
            "3️⃣ <b>Banka Kariyer İlanları:</b> Gişe yetkilisi, çağrı merkezi ve uzman yardımcısı alımları\n"
            "4️⃣ <b>Maaş & Haklar Rehberi:</b> Kamu maaş zamları, emekli promosyon ligi ve kıdem tazminatı tabloları\n\n"
            "👇 <b>Aşağıdaki bağlantılardan Telegram ve WhatsApp kanallarımıza ücretsiz katılabilirsiniz:</b>\n"
            "🔹 <b>Telegram Kanalımız:</b> https://t.me/ilanradari (@ilanradari)\n"
            f"🟢 <b>WhatsApp Kanalımız:</b> {ILAN_WHATSAPP_INVITE_URL}"
        )
        tg_markup = json.dumps({
            "inline_keyboard": [
                [{"text": "📢 İlan Radarı Telegram Kanalı (@ilanradari)", "url": "https://t.me/ilanradari"}],
                [{"text": "🟢 İlan Radarı WhatsApp Kanalı", "url": ILAN_WHATSAPP_INVITE_URL}],
            ]
        })
        with open(card_path, "rb") as f:
            r_tg = requests.post(
                f"{API_BASE}/sendPhoto",
                data={"chat_id": FAIZ_CHANNEL_ID, "caption": tg_caption, "parse_mode": "HTML", "reply_markup": tg_markup},
                files={"photo": f},
                timeout=30,
            ).json()
        print("1_TG_FAIZRADARI_OK:", r_tg.get("ok"), "MSG_ID:", r_tg.get("result", {}).get("message_id"))

        # 2. WHATSAPP (Faiz Radarı WhatsApp Kanalı)
        wa_caption = (
            "📢 *BİLGİLENDİRME: YENİ 'İLAN RADARI' SAYFAMIZ AÇILDI!* 🎯\n\n"
            "Değerli takipçilerimiz; Türkiye genelindeki güncel *kamu personel alımlarını, İŞKUR iş ilanlarını, banka personel alımlarını* ve *meslek meslek maaş / emekli promosyon tablolarını* artık yeni *İlan Radarı* kanallarımızda paylaşıyoruz.\n\n"
            "📋 *İlan Radarı'nda Her Gün Neler Paylaşılıyor?*\n"
            "1️⃣ *Bakanlık, Hastane & Üniversite Alımları:* KPSS'li sözleşmeli personel ve memur ilanları\n"
            "2️⃣ *İŞKUR & Belediye İlanları:* KPSS şartsız sürekli işçi ve kurum dışı personel alımları\n"
            "3️⃣ *Banka Kariyer İlanları:* Gişe yetkilisi, çağrı merkezi ve uzman yardımcısı alımları\n"
            "4️⃣ *Maaş & Haklar Rehberi:* Kamu maaş zamları, emekli promosyon ligi ve kıdem tazminatı tabloları\n\n"
            "👇 *Aşağıdaki linklerden ücretsiz katılabilirsiniz:*\n"
            "🔹 *Telegram Kanalımız:* https://t.me/ilanradari\n"
            f"🟢 *WhatsApp Kanalımız:* {ILAN_WHATSAPP_INVITE_URL}"
        )
        with open(card_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        headers_wa = {"Authorization": f"Bearer {WHAPI_TOKEN}", "Content-Type": "application/json", "User-Agent": "FaizRadari-Bot/1.0"}
        r_wa = requests.post(
            "https://gate.whapi.cloud/messages/image",
            json={"to": WHATSAPP_CHANNEL_ID, "media": f"data:image/png;base64,{img_b64}", "caption": wa_caption},
            headers=headers_wa,
            timeout=35,
        )
        print("2_WA_FAIZRADARI_STATUS:", r_wa.status_code)

        # 3. X (@faizradari)
        x_text = (
            "📢 Bilgilendirme: Yeni 'İlan Radarı' Sayfamız Açıldı!\n\n"
            "Güncel kamu personel alımlarını, İŞKUR iş ilanlarını, KPSS şartsız memur/işçi alımlarını, banka iş ilanlarını ve maaş/promosyon tablolarını artık İlan Radarı sayfamızda paylaşıyoruz:\n\n"
            "• Bakanlık, Belediye & Hastane Alımları\n"
            "• İŞKUR & Banka İş İlanları\n"
            "• Maaş & Emekli Promosyon Tabloları\n\n"
            "👉 Telegram arama kısmına @ilanradari yazarak ücretsiz katılabilirsiniz!"
        )
        post_to_x(card_path, x_text)

        # 4. INSTAGRAM (@faizradari via Buffer)
        repo_dir = str(Path(__file__).parent)
        shutil.copyfile(vid_path, str(Path(__file__).parent / "latest_story_video.mp4"))
        subprocess.run(["git", "add", "-f", "latest_story_video.mp4", "ilan_radari.py"], cwd=repo_dir, check=False)
        subprocess.run(["git", "commit", "-m", "chore: publish @ilanradari informative announcement across Faiz Radarı channels"], cwd=repo_dir, check=False)
        subprocess.run(["git", "pull", "--rebase", "-X", "theirs"], cwd=repo_dir, check=False)
        subprocess.run(["git", "push"], cwd=repo_dir, check=False)
        sha_p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=False)
        ref = sha_p.stdout.strip() if (sha_p.returncode == 0 and sha_p.stdout.strip()) else "main"
        time.sleep(2)

        ig_url = f"https://raw.githubusercontent.com/mbakan44-web/faizradari/{ref}/latest_story_video.mp4?v={int(time.time())}"
        ig_caption = (
            "📢 Bilgilendirme: Yeni 'İlan Radarı' Sayfamız Açıldı! 🎯\n\n"
            "Türkiye genelindeki güncel kamu personel alımlarını, İŞKUR iş ilanlarını, banka personel alımlarını ve meslek meslek maaş/promosyon tablolarını artık yeni İlan Radarı kanalımızda tek tabloda paylaşıyoruz:\n\n"
            "1️⃣ Bakanlık, Belediye, Şehir Hastanesi ve Üniversite personel alımları\n"
            "2️⃣ İŞKUR KPSS'li ve KPSS şartsız güncel memur & işçi ilanları\n"
            "3️⃣ Banka personel alımları, maaş zamları ve emekli promosyon ligi\n\n"
            "👉 Katılmak için Telegram arama kısmına  @ilanradari  yazarak ücretsiz kanalımıza hemen katılabilirsiniz!\n\n"
            "İş arayan arkadaşlarınızla paylaşmayı unutmayın 👇\n\n"
            "#işilanları #personelalımı #kpss #işkur #kariyer"
        )
        ok_ig = post_to_buffer_instagram(ig_url, ig_caption, is_video=True)
        print("4_IG_FAIZRADARI_OK:", ok_ig)
    elif "--auto-slot" in sys.argv:
        run_ilan_auto_slot()
    else:
        send_daily_jobs_report(ILAN_CHANNEL_ID)
