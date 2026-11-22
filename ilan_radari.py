import os
import re
import sys
import json
import html as html_lib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Dict, Tuple
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


def _detect_job_tag_and_badge(title: str, desc: str) -> Tuple[str, str]:
    comb = f"{title} {desc}".lower()
    if "kpss şartsız" in comb or "kpss'siz" in comb or "sınavsız" in comb:
        tag = "KPSS ŞARTSIZ ALIM"
    elif "kpss" in comb:
        m = re.search(r"kpss\s*(\d{2})\s*puan", comb)
        tag = f"KPSS {m.group(1)}+ PUAN" if m else "KPSS İLE ALIM"
    elif "işkur" in comb:
        tag = "İŞKUR İŞ İLANI"
    elif "belediye" in comb:
        tag = "BELEDİYE ALIMI"
    elif "üniversite" in comb or "hastane" in comb or "sağlık" in comb:
        tag = "KAMU / SAĞLIK"
    elif "emekli" in comb or "promosyon" in comb:
        tag = "EMEKLİ & PROMOSYON"
    elif "maaş" in comb or "zam" in comb or "asgari ücret" in comb:
        tag = "MAAŞ & ZAM REHBERİ"
    else:
        tag = "KAMU & ÖZEL İLAN"

    if "alacak" in comb or "başladı" in comb or "başvuru" in comb or "alım" in comb:
        badge = "BAŞVURU AKTİF"
    elif "açıklandı" in comb or "belli oldu" in comb:
        badge = "YENİ DUYURU"
    else:
        badge = "GÜNCEL"
    return tag, badge


def fetch_live_job_announcements(limit: int = 8) -> List[Dict]:
    """
    İşin Olsa, KamuPersoneli, Google News Kamu İlanları ve Memurlar.net üzerinden
    canlı personel alımı, İŞKUR, belediye, bakanlık ve maaş/promosyon duyurularını çeker.
    """
    feeds = [
        ("İşin Olsa", "https://www.isinolsa.com/rss"),
        ("KamuPersoneli", "https://www.kamupersoneli.net/rss"),
        (
            "Kamu İlan Masası",
            "https://news.google.com/rss/search?q=(%22personel+al%C4%B1m%C4%B1%22+OR+%22memur+al%C4%B1m%C4%B1%22+OR+%22i%C5%9F%C3%A7i+al%C4%B1m%C4%B1%22+OR+%22%C4%B0%C5%9EKUR%22+OR+%22KPSS%22+OR+%22bek%C3%A7i+al%C4%B1m%C4%B1%22)+when:2d&hl=tr&gl=TR&ceid=TR:tr",
        ),
        (
            "Maaş & Promosyon Masası",
            "https://news.google.com/rss/search?q=(%22emekli+promosyon%22+OR+%22memur+maa%C5%9F%C4%B1%22+OR+%22personel+alacak%22+OR+%22Kariyer+Kap%C4%B1s%C4%B1%22)+when:2d&hl=tr&gl=TR&ceid=TR:tr",
        ),
    ]

    reject_pats = [
        r"sandero|corsa|otomobil|araba|suv",
        r"burç|astroloji|magazin|dizi|fragman",
        r"futbol|maç|transfer|galatasaray|fenerbahçe|beşiktaş",
        r"sayısal loto|şans topu|piyango",
        r"hava durumu|deprem",
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
                        if (now_utc - p_dt).total_seconds() / 3600.0 > 48.0:
                            continue
                    except Exception:
                        pass

                raw_t = it.findtext("title") or ""
                raw_d = it.findtext("description") or ""

                t = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_t)).strip()
                t = re.sub(r"\s+-\s+[A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\s]{2,30}$", "", t).strip()
                t = re.sub(r"\s+", " ", t)

                d = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_d)).strip()
                d = re.sub(r"\s+", " ", d)
                if d.lower().startswith(t[:28].lower()):
                    d = ""

                if len(t) < 22 or len(t) > 125:
                    continue

                low_all = f"{t} {d}".lower()
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
                if len(d) >= 50:
                    score += 12

                clean_summary = d if len(d) >= 40 else f"{t}. Başvuru şartları, kadro dağılımı ve son başvuru tarihi e-Devlet Kariyer Kapısı ve İŞKUR üzerinden takip edilebilir."
                if len(clean_summary) > 260:
                    clean_summary = clean_summary[:257].rsplit(" ", 1)[0] + "..."

                seen_titles.append(t)
                items_out.append({
                    "title": t,
                    "summary": clean_summary,
                    "tag": tag,
                    "badge": badge,
                    "source": src_name,
                    "score": score,
                })
        except Exception:
            continue

    items_out.sort(key=lambda x: x["score"], reverse=True)
    return items_out[:limit]


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

        # Alt Kategori & Kaynak
        sub_str = f"{j['tag']}  •  Kaynak: {j['source']}"
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
        "BAŞVURU ADRESLERİ:  e-Devlet Kariyer Kapısı (cbiko.gov.tr)  •  esube.iskur.gov.tr  •  Resmi Gazete",
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

    today_str = datetime.now().strftime("%d.%m.%Y • %H:%M")

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
    steps = [
        "1. e-Devlet Kariyer Kapısı (isealimkariyerkapisi.cbiko.gov.tr) veya İŞKUR e-Şube'ye giriş yapın.",
        "2. İlgili kurumun ilan kılavuzundaki öğrenim ve KPSS/özel şartlarını kontrol edin.",
        "3. Başvurunuzu son başvuru tarihine kadar elektronik ortamda tamamlayın.",
    ]
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


def _ilan_reply_markup() -> str:
    import urllib.parse
    share_txt = urllib.parse.quote(
        "📋 Güncel kamu personel alımları, İŞKUR iş ilanları ve maaş/promosyon tabloları @ilanradari kanalında!\n👉 https://t.me/ilanradari"
    )
    markup = {
        "inline_keyboard": [
            [
                {"text": "📢 İlan Radarı Kanalımız (@ilanradari)", "url": "https://t.me/ilanradari"},
                {"text": "📲 İş Arayan Arkadaşına Gönder", "url": f"https://t.me/share/url?url=https://t.me/ilanradari&text={share_txt}"},
            ]
        ]
    }
    return json.dumps(markup)


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
        "• İş arayan yakınlarınızı ve arkadaşlarınızı kanalımıza davet etmeyi unutmayın!\n\n"
        "👉 <b>Resmi Kanalımız:</b> @ilanradari"
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
    """Günün öne çıkan 6 kamu ve İŞKUR iş ilanını tek tabloda @ilanradari kanalında paylaşır."""
    jobs = fetch_live_job_announcements(limit=6)
    if not jobs:
        print("[UYARI] Güncel iş ilanı bulunamadı.")
        return {"ok": False}

    img_path = render_daily_jobs_table_image(jobs, str(Path(__file__).parent / "latest_ilan_table.png"))
    now_str = datetime.now().strftime("%d.%m.%Y")

    bullets = "\n".join([f"{i + 1}️⃣ <b>{j['title']}</b> (<i>{j['tag']}</i>)" for i, j in enumerate(jobs[:6])])
    caption = (
        f"📋 <b>İLAN RADARI | GÜNÜN PERSONEL & İŞ İLANLARI</b> ({now_str})\n\n"
        f"{bullets}\n\n"
        "📌 <b>Başvuru Kanalları:</b> e-Devlet Kariyer Kapısı, İŞKUR e-Şube ve ilgili kurumların resmi duyuru sayfaları.\n\n"
        "📲 <i>İş arayan arkadaşlarınızla ve aile gruplarınızla paylaşmayı unutmayın!</i>\n"
        "🔔 <b>Takip:</b> @ilanradari"
    )

    with open(img_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup(),
            },
            files={"photo": f},
            timeout=30,
        ).json()
    print(f"[İLAN TABLOSU] {target_chat_id} -> {res.get('ok')}")
    return res


def send_spotlight_job_report(target_chat_id: str = ILAN_CHANNEL_ID, force: bool = False) -> dict:
    """Henüz paylaşılmamış en yüksek puanlı yeni personel alımı ilanını tekil detay kartıyla paylaşır."""
    cache = load_ilan_cache()
    history = cache.get("dispatched_headlines", [])
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
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")

    caption = (
        f"🚨 <b>YENİ PERSONEL & İŞ İLANI DUYURUSU</b> ({now_str})\n\n"
        f"📌 <b>{chosen['title']}</b>\n"
        f"🏷️ <b>Kategori:</b> {chosen['tag']} ({chosen['badge']})\n\n"
        f"📝 <b>İlan Özeti:</b>\n{chosen['summary']}\n\n"
        "📲 <i>Bu ilanı değerlendirebilecek arkadaşlaranıza aşağıdaki butonla hemen iletebilirsiniz.</i>\n"
        "🔔 <b>Güncel İlan Takibi:</b> @ilanradari"
    )

    with open(img_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/sendPhoto",
            data={
                "chat_id": target_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": _ilan_reply_markup(),
            },
            files={"photo": f},
            timeout=30,
        ).json()

    if res.get("ok") and target_chat_id == ILAN_CHANNEL_ID:
        history.append(chosen["title"])
        cache["dispatched_headlines"] = history[-60:]
        save_ilan_cache(cache)

    print(f"[FLAŞ İLAN KARTI] {target_chat_id} ({chosen['title'][:45]}...) -> {res.get('ok')}")
    return res


def run_ilan_auto_slot() -> None:
    """
    GitHub Actions her çalıştığında @ilanradari kanalı için:
    - Gece 20:00 - 08:30 arası sessiz saat kuralına uyar.
    - Sabah (09:00-11:59): Günün 6'lı Kamu & İŞKUR Personel Alım İlanları Tablosunu paylaşır (günde 1 kez).
    - Öğleden sonra / Akşam (12:00-19:59): Yeni çıkan önemli bir personel alımı / maaş duyurusu varsa Flaş İlan Kartı paylaşır.
    """
    now_tr = datetime.now(timezone(timedelta(hours=3)))
    h = now_tr.hour
    if h >= 20 or h < 8:
        return

    today_str = now_tr.strftime("%Y-%m-%d")
    cache = load_ilan_cache()
    daily = cache.get("daily_dispatched", {})
    today_list = daily.get(today_str, [])

    if h in (8, 9, 10, 11) and "daily_table" not in today_list:
        res = send_daily_jobs_report(ILAN_CHANNEL_ID)
        if res.get("ok"):
            today_list.append("daily_table")
            daily[today_str] = today_list
            cache["daily_dispatched"] = daily
            save_ilan_cache(cache)
    elif h in (12, 13, 14, 15, 16, 17, 18, 19) and f"spotlight_{h // 4}" not in today_list:
        res = send_spotlight_job_report(ILAN_CHANNEL_ID)
        if res.get("ok"):
            today_list.append(f"spotlight_{h // 4}")
            daily[today_str] = today_list
            cache["daily_dispatched"] = daily
            save_ilan_cache(cache)


if __name__ == "__main__":
    if "--init" in sys.argv:
        send_welcome_and_pin(ILAN_CHANNEL_ID)
        send_daily_jobs_report(ILAN_CHANNEL_ID)
        send_spotlight_job_report(ILAN_CHANNEL_ID, force=True)
    elif "--auto-slot" in sys.argv:
        run_ilan_auto_slot()
    else:
        send_daily_jobs_report(ILAN_CHANNEL_ID)
