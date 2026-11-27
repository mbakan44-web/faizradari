import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import requests
from bs4 import BeautifulSoup
from calculator import LoanOffer, DepositOffer, SpreadOffer, RateDropAlert, format_tl

CACHE_FILE = Path(__file__).parent / "rates_cache.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

def normalize_bank_name(name: str) -> str:
    """
    Tüm banka isimlerini resmi ve tekil kanonik isimlerine dönüştürür.
    Kesinlikle '.com' veya mükerrer isimlerin oluşmasına izin vermez.
    """
    n = name.strip()
    n = re.sub(r"\.com(\.tr)?", "", n, flags=re.IGNORECASE).strip()

    rules = [
        (r"^enpara.*", "Enpara"),
        (r"^on(\s+dijital)?.*|^burgan.*", "ON Dijital"),
        (r"^cepteteb.*|^teb.*", "CEPTETEB"),
        (r"^(türkiye\s+)?iş(\s+bankası)?$|^işbank.*", "Türkiye İş Bankası"),
        (r"^ziraat\s+dinamik.*", "Ziraat Dinamik"),
        (r"^ziraat(\s+bankası)?$", "Ziraat Bankası"),
        (r"^vakıf(\s*bank)?$", "VakıfBank"),
        (r"^halk(\s*bank)?$", "Halkbank"),
        (r"^garanti(\s+bbva)?.*", "Garanti BBVA"),
        (r"^yapı\s*kredi.*", "Yapı Kredi"),
        (r"^qnb(\s+finansbank)?.*|^finansbank.*", "QNB"),
        (r"^akbank.*", "Akbank"),
        (r"^deniz(\s*bank)?.*", "DenizBank"),
        (r"^ing.*", "ING"),
        (r"^alternatif(\s+bank)?.*", "Alternatif Bank"),
        (r"^fibabanka.*", "Fibabanka"),
        (r"^kuveyt\s+türk.*", "Kuveyt Türk"),
        (r"^n\s*kolay.*", "N Kolay"),
        (r"^getirfinans.*", "getirfinans"),
        (r"^odea.*", "Odeabank"),
        (r"^anadolubank.*", "Anadolubank"),
        (r"^albaraka.*", "Albaraka Türk"),
        (r"^türkiye\s+finans.*", "Türkiye Finans"),
        (r"^şekerbank.*", "Şekerbank"),
        (r"^hsbc.*", "HSBC"),
        (r"^tom\s*bank.*", "TOM Bank"),
        (r"^hayat\s*finans.*", "Hayat Finans"),
        (r"^türk\s+ticaret.*", "Türk Ticaret Bankası"),
    ]
    for pat, canonical in rules:
        if re.search(pat, n, re.IGNORECASE):
            return canonical
    return n


def clean_and_deduplicate_rates(rates: Dict[str, float], mode: str = "min") -> Dict[str, float]:
    """
    Verilen faiz/oran sözlüğündeki mükerrer banka varyasyonlarını kanonik isme bağlayıp tekilleştirir.
    Kredi faizinde mode='min' (en düşük oran), mevduatta mode='max' (en yüksek getiri) esas alınır.
    """
    cleaned: Dict[str, float] = {}
    for raw_name, rate in rates.items():
        norm = normalize_bank_name(str(raw_name))
        try:
            val = float(rate)
        except (ValueError, TypeError):
            continue
        if not norm or val <= 0:
            continue
        if norm not in cleaned:
            cleaned[norm] = val
        else:
            if mode == "min":
                cleaned[norm] = min(cleaned[norm], val)
            else:
                cleaned[norm] = max(cleaned[norm], val)
    return cleaned


DEFAULT_RATES = {
    "ihtiyac": {
        "Enpara": 2.79,
        "QNB": 2.84,
        "DenizBank": 2.89,
        "getirfinans": 2.89,
        "ON Dijital": 2.99,
        "Alternatif Bank": 2.99,
        "Odeabank": 2.99,
        "Anadolubank": 3.09,
        "CEPTETEB": 3.39,
        "Akbank": 3.39,
        "Türkiye İş Bankası": 3.68,
        "Ziraat Bankası": 3.69,
        "Garanti BBVA": 3.89,
        "N Kolay": 3.99,
        "Yapı Kredi": 4.29,
    },
    "konut": {
        "VakıfBank": 2.84,
        "Kuveyt Türk": 2.87,
        "Ziraat Bankası": 2.89,
        "QNB": 2.99,
        "Halkbank": 2.99,
        "Türkiye İş Bankası": 3.05,
        "Yapı Kredi": 3.09,
        "Garanti BBVA": 3.13,
        "Akbank": 3.15,
        "ING": 3.19,
        "CEPTETEB": 3.20,
    },
    "tasit": {
        "Akbank": 3.18,
        "Garanti BBVA": 3.25,
        "Kuveyt Türk": 3.27,
        "Türkiye İş Bankası": 3.29,
        "Ziraat Bankası": 3.29,
        "VakıfBank": 3.39,
        "CEPTETEB": 3.39,
        "Yapı Kredi": 3.49,
        "QNB": 3.59,
        "Halkbank": 3.65,
    },
    "mevduat": {
        "Ziraat Dinamik": 45.0,
        "Alternatif Bank": 43.0,
        "Anadolubank": 43.0,
        "Odeabank": 43.0,
        "Fibabanka": 42.0,
        "ING": 42.0,
        "ON Dijital": 41.5,
        "DenizBank": 41.0,
        "CEPTETEB": 40.5,
        "QNB": 40.5,
        "Yapı Kredi": 39.75,
        "Akbank": 37.75,
        "Enpara": 36.5,
    },
}

ZERO_INTEREST_OFFERS = [
    {"bank": "Garanti BBVA", "amount": "50.000 TL", "term": "3-6 Ay", "detail": "25.000 TL Kredi + 25.000 TL Taksitli Avans (%0 Faiz)"},
    {"bank": "Enpara", "amount": "50.000 TL", "term": "6 Ay", "detail": "Yeni müşterilere özel 50.000 TL'ye varan %0 faizli kredi"},
    {"bank": "Akbank", "amount": "45.000 TL", "term": "6 Ay", "detail": "20.000 TL Kredi + 25.000 TL Taksitli Avans (%0 Faiz)"},
    {"bank": "QNB", "amount": "45.000 TL", "term": "3-6 Ay", "detail": "20.000 TL Kredi + 25.000 TL Nakit Avans (%0 Faiz)"},
    {"bank": "ON Dijital", "amount": "35.000 TL", "term": "6 Ay", "detail": "Yeni müşterilere özel %0 faiz fırsatı"},
]


def _parse_tr_float(val_str: str) -> float:
    s = re.sub(r"[^\d,\.]", "", val_str.strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def fetch_market_tickers() -> Dict[str, str]:
    """Canlı Dolar, Euro ve Gram Altın kurlarını çeker."""
    tickers = {"USD": "—", "EUR": "—", "ALTIN": "—", "BIST100": "—"}
    try:
        resp = requests.get("https://finans.truncgil.com/v4/today.json", headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if "USD" in data and "Selling" in data["USD"]:
                tickers["USD"] = f"{float(data['USD']['Selling']):.2f} ₺"
            if "EUR" in data and "Selling" in data["EUR"]:
                tickers["EUR"] = f"{float(data['EUR']['Selling']):.2f} ₺"
            if "GRA" in data and "Selling" in data["GRA"]:
                tickers["ALTIN"] = f"{float(data['GRA']['Selling']):,.0f} ₺".replace(",", ".")
    except Exception:
        pass

    if tickers["USD"] == "—":
        try:
            r_usd = requests.get("https://open.er-api.com/v6/latest/USD", timeout=6).json()
            usd_try = r_usd["rates"]["TRY"]
            r_eur = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=6).json()
            eur_try = r_eur["rates"]["TRY"]
            tickers["USD"] = f"{usd_try:.2f} ₺"
            tickers["EUR"] = f"{eur_try:.2f} ₺"
        except Exception:
            pass

    if tickers["ALTIN"] == "—":
        try:
            r_g = requests.get("https://altin.in/banka/altin", headers=HEADERS, timeout=6)
            m = re.search(r"Gram Altın Fiyatları[\s\S]{1,120}?([5678]\d{3}\.\d+)", r_g.text)
            if m:
                tickers["ALTIN"] = f"{float(m.group(1)):,.0f} ₺".replace(",", ".")
        except Exception:
            pass
    return tickers


def _scrape_loan_rates_by_type(loan_type: str, principal: float, months: int) -> List[Tuple[str, float]]:
    """
    Çok kaynaklı canlı kredi faizi tarayıcısı (TeklifimGelsin JSON + HangiKredi HTML regex).
    Tüm veriler normalize_bank_name ile tekilleştirilir.
    """
    slug_map = {
        "ihtiyac": ("ihtiyac-kredisi", 2.0, 6.0),
        "konut": ("konut-kredisi", 2.2, 5.5),
        "tasit": ("tasit-kredisi", 2.4, 6.0),
    }
    slug, min_r, max_r = slug_map.get(loan_type, ("ihtiyac-kredisi", 2.0, 6.0))
    scraped_rates: Dict[str, float] = {}

    # Kaynak 1: TeklifimGelsin (Geniş banka JSON veri tabanı)
    try:
        url_tg = f"https://teklifimgelsin.com/kredi/{slug}"
        resp_tg = requests.get(url_tg, headers=HEADERS, timeout=8)
        if resp_tg.status_code == 200:
            matches = re.findall(r'"bank":\s*"([^"]+)"[\s\S]{1,150}?"interest_rate":\s*([0-9\.]+)', resp_tg.text)
            for raw_b, rate in matches:
                norm_b = normalize_bank_name(raw_b)
                r_val = float(rate)
                if min_r <= r_val <= max_r:
                    if norm_b not in scraped_rates or r_val < scraped_rates[norm_b]:
                        scraped_rates[norm_b] = r_val
    except Exception:
        pass

    # Kaynak 2: HangiKredi (Piyasa doğrulama)
    try:
        url_hk = f"https://www.hangikredi.com/kredi/{slug}?amount={int(principal)}&maturity={months}"
        resp_hk = requests.get(url_hk, headers=HEADERS, timeout=8)
        if resp_hk.status_code == 200:
            known_banks = [
                "QNB", "Enpara", "Akbank", "Garanti BBVA", "İş Bankası", "Yapı Kredi",
                "CEPTETEB", "DenizBank", "ING", "ON Dijital", "Alternatif Bank",
                "N Kolay", "Fibabanka", "Ziraat", "VakıfBank", "Halkbank", "Kuveyt Türk",
                "getirfinans", "Odeabank", "Anadolubank"
            ]
            for bank in known_banks:
                m = re.search(rf"{re.escape(bank)}[\s\S]{{1,350}}?%?\s*([1-6][,\.][0-9]{{2}})", resp_hk.text, re.IGNORECASE)
                if m:
                    r_val = float(m.group(1).replace(",", "."))
                    norm_b = normalize_bank_name(bank)
                    if min_r <= r_val <= max_r:
                        if norm_b not in scraped_rates or r_val < scraped_rates[norm_b]:
                            scraped_rates[norm_b] = r_val
    except Exception:
        pass

    return [(b, r) for b, r in scraped_rates.items()]


def _load_full_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            # Otomatik temizlik: Cache'teki tüm kategorileri tekilleştir
            for k in ["ihtiyac_kredisi", "konut_kredisi", "tasit_kredisi"]:
                if k in raw and isinstance(raw[k], dict):
                    raw[k] = clean_and_deduplicate_rates(raw[k], mode="min")
            if "mevduat_oranlari" in raw and isinstance(raw["mevduat_oranlari"], dict):
                raw["mevduat_oranlari"] = clean_and_deduplicate_rates(raw["mevduat_oranlari"], mode="max")
            if "sifir_faiz_firsatlari" in raw and isinstance(raw["sifir_faiz_firsatlari"], list):
                for item in raw["sifir_faiz_firsatlari"]:
                    if "bank" in item:
                        item["bank"] = normalize_bank_name(item["bank"])
            return raw
        except Exception:
            pass
    return {}


def _save_full_cache(data: dict) -> None:
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    data["sifir_faiz_firsatlari"] = ZERO_INTEREST_OFFERS
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_loan_offers(
    loan_type: str = "ihtiyac",
    principal: float = 100_000,
    months: int = 12,
) -> Tuple[List[LoanOffer], List[RateDropAlert]]:
    """
    İhtiyaç, Konut veya Taşıt kredisi oranlarını çeker, tekilleştirir,
    önceki önbellekle karşılaştırıp faiz indirimi veya faiz artışı yapan banka varsa `RateDropAlert`
    listesiyle birlikte döndürür.
    """
    cache = _load_full_cache()
    cache_key = f"{loan_type}_kredisi"

    # 1. Taban ve Önbellek oranları
    base_rates = clean_and_deduplicate_rates(DEFAULT_RATES.get(loan_type, {}), mode="min")
    cached_rates = clean_and_deduplicate_rates(cache.get(cache_key, {}), mode="min")
    
    # Karşılaştırma için temel: Önceki önbellekteki bilinen oranlar
    old_rates: Dict[str, float] = dict(cached_rates) if cached_rates else dict(base_rates)

    # 2. Canlı tarama
    scraped = _scrape_loan_rates_by_type(loan_type, principal, months)
    alerts: List[RateDropAlert] = []
    current_rates = dict(old_rates)

    for bank_name, new_rate in scraped:
        norm_name = normalize_bank_name(bank_name)
        prev_rate = old_rates.get(norm_name)
        if prev_rate is not None:
            diff = round(new_rate - prev_rate, 2)
            # Yalnızca faiz indirimi (oran düşüşü) tespit edilirse alarm üret (faiz artışları paylaşılmaz)
            if diff <= -0.04:
                alerts.append(
                    RateDropAlert(
                        bank_name=norm_name,
                        loan_type=loan_type,
                        old_rate=float(prev_rate),
                        new_rate=float(new_rate),
                        principal=principal,
                        months=months,
                        change_type="drop",
                    )
                )
        current_rates[norm_name] = new_rate

    # Kesin tekilleştirme ve temizlik
    current_rates = clean_and_deduplicate_rates(current_rates, mode="min")

    cache[cache_key] = current_rates
    if "mevduat_oranlari" not in cache:
        cache["mevduat_oranlari"] = clean_and_deduplicate_rates(DEFAULT_RATES["mevduat"], mode="max")
    _save_full_cache(cache)

    offers = [
        LoanOffer(bank_name=bank, monthly_rate=float(rate), principal=principal, months=months, loan_type=loan_type)
        for bank, rate in current_rates.items()
    ]
    offers.sort(key=lambda x: x.monthly_rate)
    return offers[:8], alerts


def check_all_loan_rates_for_changes() -> List[RateDropAlert]:
    """Tüm kredi türlerini (İhtiyaç, Taşıt, Konut) tarayıp faiz indirimi veya artışı yapan bankaları tespit eder."""
    all_alerts: List[RateDropAlert] = []
    specs = [
        ("ihtiyac", 100_000, 12),
        ("tasit", 400_000, 36),
        ("konut", 2_000_000, 120),
    ]
    for l_type, p, m in specs:
        try:
            _, alerts = get_loan_offers(loan_type=l_type, principal=p, months=m)
            all_alerts.extend(alerts)
        except Exception as e:
            print(f"[UYARI] {l_type} faiz değişim tarama hatası: {e}")
    return all_alerts


def get_consumer_loan_offers(principal: float = 100_000, months: int = 12) -> List[LoanOffer]:
    offers, _ = get_loan_offers("ihtiyac", principal, months)
    return offers


def _scrape_deposit_rates() -> Dict[str, float]:
    """HangiKredi ve TeklifimGelsin üzerinden güncel TL vadeli mevduat faiz oranlarını canlı çeker."""
    scraped: Dict[str, float] = {}

    # Kaynak 1: HangiKredi mevduat tablosu
    try:
        r = requests.get("https://www.hangikredi.com/yatirim-araclari/mevduat-faiz-oranlari", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for tr in soup.find_all("tr"):
                parts = [p.strip() for p in tr.get_text("|", strip=True).split("|") if p.strip()]
                if len(parts) >= 2 and "%" in parts[1]:
                    raw_bank = parts[0]
                    low_b = raw_bank.lower()
                    if any(skip in low_b for skip in ("aya kadar", "yıl", "vade", "banka", "fenerpara", "gspara")):
                        continue
                    nums = re.findall(r"%\s*([0-9]{2}(?:[,\.][0-9]{1,2})?)", parts[1])
                    vals = [float(n.replace(",", ".")) for n in nums]
                    valid_vals = [v for v in vals if 25.0 <= v <= 58.0]
                    if valid_vals:
                        max_rate = max(valid_vals)
                        norm_b = normalize_bank_name(raw_bank)
                        if norm_b not in scraped or max_rate > scraped[norm_b]:
                            scraped[norm_b] = max_rate
    except Exception:
        pass

    # Kaynak 2: TeklifimGelsin mevduat doğrulama
    try:
        r2 = requests.get("https://teklifimgelsin.com/mevduat", headers=HEADERS, timeout=8)
        if r2.status_code == 200:
            matches = re.findall(r'"bank":\s*"([^"]+)"[\s\S]{1,180}?"interest_rate":\s*([0-9\.]+)', r2.text)
            for raw_b, rate in matches:
                r_val = float(rate)
                if 25.0 <= r_val <= 58.0:
                    norm_b = normalize_bank_name(raw_b)
                    if norm_b not in scraped or r_val > scraped[norm_b]:
                        scraped[norm_b] = r_val
    except Exception:
        pass

    return clean_and_deduplicate_rates(scraped, mode="max")


def get_deposit_offers(principal: float = 500_000, days: int = 32) -> Tuple[List[DepositOffer], List[Dict]]:
    """500.000 TL 32 Gün Vadeli Mevduat net getiri tekliflerini ve %0 faizli nakit fırsatlarını döndürür."""
    cache = _load_full_cache()
    live_rates = _scrape_deposit_rates()

    if len(live_rates) >= 5:
        rates = live_rates
    else:
        base_rates = clean_and_deduplicate_rates(DEFAULT_RATES["mevduat"], mode="max")
        cached_rates = clean_and_deduplicate_rates(cache.get("mevduat_oranlari", {}), mode="max")
        rates = dict(cached_rates) if cached_rates else dict(base_rates)
        rates.update(live_rates)
        rates = clean_and_deduplicate_rates(rates, mode="max")

    cache["mevduat_oranlari"] = rates
    _save_full_cache(cache)

    offers = [
        DepositOffer(bank_name=bank, annual_rate=float(rate), principal=principal, days=days)
        for bank, rate in rates.items()
    ]
    offers.sort(key=lambda x: x.annual_rate, reverse=True)
    return offers[:8], ZERO_INTEREST_OFFERS


def compute_rate_fingerprint(offers) -> List[List]:
    """İlk 8 banka ve faiz oranlarından benzersiz parmak izi (fingerprint) üretir."""
    fp = []
    for o in offers[:8]:
        rate = getattr(o, "monthly_rate", None)
        if rate is None:
            rate = getattr(o, "annual_rate", 0.0)
        fp.append([o.bank_name, round(float(rate), 2)])
    return fp


def has_rates_changed_since_last_publish(topic: str, offers) -> Tuple[bool, List[str]]:
    """
    Bu kategori en son paylaşıldığından beri herhangi bir bankanın oranında değişiklik oldu mu?
    - Değişiklik yoksa: (False, []) döner -> Mükerrer tablo paylaşımı engellenir!
    - İlk kez paylaşılıyorsa veya en az 1 bankada oran değiştiyse: (True, [değişen bankalar]) döner.
    """
    cache = _load_full_cache()
    pub_map = cache.get("last_published_fingerprints", {})
    prev_entry = pub_map.get(topic)
    new_fp = compute_rate_fingerprint(offers)

    if not prev_entry or not prev_entry.get("fingerprint"):
        return True, []

    old_fp = prev_entry["fingerprint"]
    if old_fp == new_fp:
        return False, []

    old_dict = {b: r for b, r in old_fp}
    new_dict = {b: r for b, r in new_fp}
    changed_banks = []
    for b, r in new_dict.items():
        if b not in old_dict or abs(old_dict[b] - r) >= 0.01:
            changed_banks.append(b)
    return True, changed_banks


def mark_rates_published(topic: str, offers) -> None:
    """Paylaşılan tablonun oran parmak izini önbelleğe kaydeder."""
    cache = _load_full_cache()
    pub_map = cache.get("last_published_fingerprints", {})
    pub_map[topic] = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "fingerprint": compute_rate_fingerprint(offers),
    }
    cache["last_published_fingerprints"] = pub_map
    _save_full_cache(cache)


def get_bank_spread_offers() -> Tuple[List[SpreadOffer], List[SpreadOffer]]:
    """
    Bankaların canlı Dolar (USD/TRY) ve Gram Altın (TL) Alış, Satış ve Makas verilerini çeker.
    Tüm banka isimleri tekilleştirilmiş kanonik formatta sunulur.
    Öncelikli olarak kur.doviz.com ve altin.doviz.com canlı tablolarını kullanır.
    """
    usd_map: Dict[str, SpreadOffer] = {}
    gold_map: Dict[str, SpreadOffer] = {}

    # 1. doviz.com üzerinden Canlı Banka Dolar Kurları
    try:
        r_usd = requests.get("https://kur.doviz.com/serbest-piyasa/amerikan-dolari", headers=HEADERS, timeout=8)
        if r_usd.status_code == 200:
            soup_u = BeautifulSoup(r_usd.text, "html.parser")
            tbl_u = soup_u.find("table")
            if tbl_u:
                for tr in tbl_u.find_all("tr")[1:]:
                    cols = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                    if len(cols) >= 3:
                        raw = cols[0]
                        if any(x in raw.lower() for x in ("kapalıçarşı", "altınkaynak", "harem", "odacı", "venüs", "merkez bankası", "tcmb", "kaynak", "serbest")):
                            continue
                        name = normalize_bank_name(raw)
                        buy_v = _parse_tr_float(cols[1])
                        sell_v = _parse_tr_float(cols[2])
                        if 30.0 < buy_v < sell_v < 100.0 and (sell_v - buy_v) >= 0.05:
                            usd_map[name] = SpreadOffer(
                                bank_name=name,
                                asset="USD",
                                buy_price=buy_v,
                                sell_price=sell_v,
                            )
    except Exception:
        pass

    # 2. doviz.com üzerinden Canlı Banka Gram Altın Kurları
    try:
        r_gold = requests.get("https://altin.doviz.com/gram-altin", headers=HEADERS, timeout=8)
        if r_gold.status_code == 200:
            soup_g = BeautifulSoup(r_gold.text, "html.parser")
            tbl_g = soup_g.find("table")
            if tbl_g:
                for tr in tbl_g.find_all("tr")[1:]:
                    cols = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                    if len(cols) >= 3:
                        raw = cols[0]
                        if any(x in raw.lower() for x in ("kapalıçarşı", "altınkaynak", "harem", "odacı", "venüs", "merkez bankası", "tcmb", "kaynak", "serbest")):
                            continue
                        name = normalize_bank_name(raw)
                        buy_v = _parse_tr_float(cols[1])
                        sell_v = _parse_tr_float(cols[2])
                        # Makas en az 15 TL olmalıdır (hatalı/donmuş 6 TL gibi sahte verileri engelle)
                        if 3500.0 < buy_v < sell_v < 15000.0 and (sell_v - buy_v) >= 15.0:
                            gold_map[name] = SpreadOffer(
                                bank_name=name,
                                asset="ALTIN",
                                buy_price=buy_v,
                                sell_price=sell_v,
                            )
    except Exception:
        pass

    # 3. Enpara resmi sayfasından teyit/tamamlama
    if "Enpara" not in usd_map or "Enpara" not in gold_map:
        try:
            r_enp = requests.get("https://www.enpara.com/hesaplar/doviz-ve-altin-kurlari", headers=HEADERS, timeout=8)
            if r_enp.status_code == 200:
                soup_enp = BeautifulSoup(r_enp.text, "html.parser")
                for item in soup_enp.select(".enpara-gold-exchange-rates__table-item"):
                    parts = [p.strip() for p in item.get_text("|", strip=True).split("|") if p.strip()]
                    if len(parts) >= 3:
                        label = parts[0]
                        buy_v = _parse_tr_float(parts[1])
                        sell_v = _parse_tr_float(parts[2])
                        if "USD ($)" in label and 30.0 < buy_v < sell_v < 100.0 and "Enpara" not in usd_map:
                            usd_map["Enpara"] = SpreadOffer("Enpara", "USD", buy_v, sell_v)
                        elif "Altın (gram)" in label and "/USD" not in label and 3500.0 < buy_v < sell_v < 15000.0 and "Enpara" not in gold_map:
                            gold_map["Enpara"] = SpreadOffer("Enpara", "ALTIN", buy_v, sell_v)
        except Exception:
            pass

    # 4. Yedek Kaynak (Eğer doviz.com geçici olarak yanıt vermezse tlkur.com)
    if len(usd_map) < 3:
        try:
            resp = requests.get("https://tlkur.com/dolar", headers=HEADERS, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tr in soup.find_all("tr"):
                    cols = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                    if len(cols) >= 3:
                        raw_name = re.sub(r"\d{2}:\d{2}(:\d{2})?", "", cols[0]).strip()
                        if not raw_name or raw_name in ("Kaynak", "Serbest Piyasa", "TCMB", "Altınkaynak", "Kapalıçarşı"):
                            continue
                        name = normalize_bank_name(raw_name)
                        buy_v = _parse_tr_float(cols[1])
                        sell_v = _parse_tr_float(cols[2])
                        if 30.0 < buy_v < sell_v < 100.0 and (sell_v - buy_v) >= 0.05:
                            usd_map[name] = SpreadOffer(
                                bank_name=name,
                                asset="USD",
                                buy_price=buy_v,
                                sell_price=sell_v,
                            )
        except Exception:
            pass

    usd_list = sorted(usd_map.values(), key=lambda x: x.spread_pct)[:7]
    gold_list = sorted(gold_map.values(), key=lambda x: x.spread_pct)[:7]
    return usd_list, gold_list


def _extract_news_keywords(text: str) -> set:
    stop_words = {
        "ve", "ile", "için", "bir", "bu", "da", "de", "mi", "mu", "ne", "en",
        "göre", "sonra", "önce", "olan", "olarak", "daha", "çok", "kadar", "gibi",
    }
    words = re.findall(r"[a-zçğıöşü0-9]{3,}", text.lower())
    return {w for w in words if w not in stop_words}


def _is_duplicate_news(headline: str, history: List[Dict]) -> bool:
    kw_new = _extract_news_keywords(headline)
    if not kw_new:
        return False
    for h in history:
        old_title = h.get("headline", "")
        kw_old = _extract_news_keywords(old_title)
        if not kw_old:
            continue
        overlap = len(kw_new & kw_old) / float(min(len(kw_new), len(kw_old)))
        if overlap >= 0.45:
            return True
    return False


def fetch_breaking_economy_news(ignore_daily_limit: bool = False) -> Dict:
    """
    %100 Ücretsiz (0 TL) Otonom Son Dakika Ekonomi & TCMB Haber Avcısı:
    - TRT Ekonomi, Habertürk Ekonomi, NTV Ekonomi, CNN Türk Ekonomi ve Google News Finans RSS akışlarını tarar.
    - Vatandaşın cebini ilgilendirmeyen protokol, ödül, tıklama tuzağı (?) ve magazin haberlerini eler.
    - Yalnızca yüksek puanlı makro/cep etkisi olan (TCMB, Faiz, Enflasyon, BDDK, Kredi, Mevduat, Altın/Dolar, Maaş/Vergi)
      gelişmeleri yakalar ve canlı piyasa verileriyle zenginleştirir.
    - Günde en fazla 1 otomatik flaş haber üretir; paylaşılan haberi bir daha asla tekrarlamaz.
    """
    import html as html_lib
    import xml.etree.ElementTree as ET

    cache = _load_full_cache()
    today_str = datetime.now().strftime("%Y-%m-%d")
    history: List[Dict] = cache.get("dispatched_news_history", [])

    if not ignore_daily_limit:
        today_count = sum(1 for h in history if h.get("date") == today_str)
        if today_count >= 1:
            return {}

    feeds = [
        ("Bloomberg HT", "https://www.bloomberght.com/rss"),
        ("TRT Haber Ekonomi", "https://www.trthaber.com/ekonomi_articles.rss"),
        ("Habertürk Ekonomi", "https://www.haberturk.com/rss/ekonomi.xml"),
        ("CNN Türk Ekonomi", "https://www.cnnturk.com/feed/rss/ekonomi/news"),
        (
            "Finans Haber Masası",
            "https://news.google.com/rss/search?q=(TCMB+OR+%22Merkez+Bankas%C4%B1%22+OR+%22faiz+karar%C4%B1%22+OR+enflasyon+OR+BDDK+OR+mevduat+OR+%22konut+kredisi%22)+when:1d&hl=tr&gl=TR&ceid=TR:tr",
        ),
    ]

    reject_patterns = [
        r"\?$",
        r"nasıl başladı",
        r"ne kadar oldu\?",
        r"belli oldu mu",
        r"ne zaman yatacak",
        r"ödülü",
        r"bir araya geldi",
        r"ziyaret etti",
        r"taziye",
        r"futbol|transfer|maç|süper lig",
        r"burç|astroloji|magazin",
        r"iski|aski|su kesintisi|elektrik kesintisi",
        r"bitcoin|altcoin|shiba|dogecoin",
        r"sayısal loto|şans topu|süper loto|on numara|milli piyango",
    ]

    category_rules = [
        (
            "MERKEZ BANKASI & FAİZ",
            42,
            [
                "merkez bankası", "tcmb", "faiz kararı", "politika faizi",
                "para politikası", "ppk", "faiz indirimi", "faiz artışı",
                "fed tutanakları", "fed faiz",
            ],
        ),
        (
            "ENFLASYON & TÜİK VERİSİ",
            38,
            ["enflasyon", "tüfe", "tüik", "tüketici fiyatları", "alım gücü", "enflasyon raporu"],
        ),
        (
            "BANKACILIK & KREDİ KARARI",
            36,
            [
                "bddk", "mevduat faizi", "stopaj", "konut kredisi", "ihtiyaç kredisi",
                "kredi kartı", "nakit avans", "kredi notu", "moody's", "fitch", "s&p",
                "faiz yarışı",
            ],
        ),
        (
            "ALTIN & DÖVİZ PİYASASI",
            30,
            ["gram altın", "ons altın", "dolar/tl", "rekor kırdı", "merkez bankası rezerv", "dış borç"],
        ),
        (
            "MAAŞ, VERGİ & EKONOMİ",
            28,
            ["asgari ücret", "emekli", "memur zammı", "vergi", "hazine ve maliye", "중", "orta vadeli program"],
        ),
    ]

    candidates: List[Dict] = []

    from email.utils import parsedate_to_datetime
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)

    for src_name, url in feeds:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            for it in items[:15]:
                pub_str = (it.findtext("pubDate") or "").strip()
                if pub_str:
                    try:
                        pub_dt = parsedate_to_datetime(pub_str).astimezone(timezone.utc)
                        age_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                        if age_hours > 24.0:
                            continue
                    except Exception:
                        pass

                raw_t = it.findtext("title") or ""
                raw_d = it.findtext("description") or ""

                t = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_t)).strip()
                t = re.sub(r"\s+-\s+[A-ZÇĞİÖŞÜa-zçğıöşü0-9\.\s]{2,28}$", "", t).strip()
                t = re.sub(r"\s+", " ", t)

                d = html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_d)).strip()
                d = re.sub(r"\s+", " ", d)
                # Google News açıklamasında başlığın aynısı varsa temizle
                if d.lower().startswith(t[:30].lower()):
                    d = ""

                if len(t) < 22 or len(t) > 135:
                    continue

                low_t = t.lower()
                if any(re.search(pat, low_t) for pat in reject_patterns):
                    continue

                if _is_duplicate_news(t, history):
                    continue

                best_cat = ""
                score = 0
                combined = f"{low_t} {d.lower()}"
                for cat_name, base_pts, kw_list in category_rules:
                    hits = sum(1 for kw in kw_list if kw in combined)
                    if hits > 0:
                        cat_score = base_pts + (hits - 1) * 8
                        if cat_score > score:
                            score = cat_score
                            best_cat = cat_name

                if score < 28:
                    continue

                # Zengin özet açıklaması olan resmi kaynaklara (+10 puan) öncelik ver
                if len(d) >= 55:
                    score += 10

                candidates.append({
                    "source": src_name,
                    "category": best_cat,
                    "headline": t,
                    "raw_summary": d,
                    "score": score,
                })
        except Exception:
            continue

    if not candidates:
        return {}

    # Çoklu kaynakta benzer haber varsa puanını artır (doğrulama bonusu)
    for i, c1 in enumerate(candidates):
        kw1 = _extract_news_keywords(c1["headline"])
        confirmations = 0
        for j, c2 in enumerate(candidates):
            if i != j and c1["source"] != c2["source"]:
                kw2 = _extract_news_keywords(c2["headline"])
                if kw1 and kw2 and (len(kw1 & kw2) / float(min(len(kw1), len(kw2)))) >= 0.4:
                    confirmations += 1
                    # Eğer c1'in özeti boşsa ve c2'nin özeti doluysa ödünç al
                    if not c1["raw_summary"] and c2["raw_summary"]:
                        c1["raw_summary"] = c2["raw_summary"]
        c1["score"] += confirmations * 12

    candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = candidates[0]

    # Canlı piyasa verileriyle "Faiz Radarı Cep & Piyasa Etkisi" notu oluştur
    tickers = fetch_market_tickers()
    deps, _ = get_deposit_offers(500_000, 32)
    ihts, _ = get_loan_offers("ihtiyac", 100_000, 12)
    best_dep = deps[0] if deps else None
    best_iht = ihts[0] if ihts else None

    summary = winner["raw_summary"]
    if not summary or len(summary) < 45:
        summary = f"{winner['headline']}. Ekonomi ve finans piyasalarında yakından takip edilen gelişmenin detayları netleşti."
    elif len(summary) > 320:
        cut = summary[:318]
        if ". " in cut[120:]:
            summary = cut[:120 + cut[120:].rfind(". ") + 1]
        else:
            summary = cut.rsplit(" ", 1)[0] + "..."

    cat = winner["category"]
    dep_str = f"%{best_dep.annual_rate:.1f} ({best_dep.bank_name})" if best_dep else "%45,0"
    iht_str = f"%{best_iht.monthly_rate:.2f} ({best_iht.bank_name})" if best_iht else "%2,89"

    if "FAİZ" in cat or "BANKACILIK" in cat:
        impact_note = (
            f"Yurt içi bankalarda güncel en yüksek vadeli mevduat faizi {dep_str}, "
            f"en uygun ihtiyaç kredisi oranı ise aylık {iht_str} seviyesinde uygulanıyor."
        )
        question = "Sizce bu gelişme önümüzdeki günlerde banka faiz oranlarını nasıl etkiler?"
    elif "ALTIN" in cat:
        impact_note = (
            f"Serbest piyasada şu an Dolar/TL {tickers.get('USD', '—')}, Euro/TL {tickers.get('EUR', '—')} "
            f"ve Gram Altın {tickers.get('ALTIN', '—')} seviyesinden işlem görüyor."
        )
        question = "Altın ve dövizdeki bu seyir hakkında sizin beklentiniz nedir?"
    else:
        impact_note = (
            f"Piyasa Göstergeleri: Dolar/TL {tickers.get('USD', '—')} | Gram Altın {tickers.get('ALTIN', '—')} | "
            f"En Yüksek Mevduat {dep_str}."
        )
        question = "Bu ekonomi gelişmesinin piyasalara ve bütçenize etkisini nasıl değerlendiriyorsunuz?"

    voice_script = (
        f"Son dakika ekonomi gelişmesi! {winner['headline']}. "
        f"{impact_note} "
        f"Peki sizce bu gelişme piyasaları nasıl etkiler? Yorumlarda buluşalım!"
    )

    reel_rows = [
        {"rank": "!", "title": "SON DAKİKA GELİŞMESİ", "sub": winner["category"], "value": "CANLI", "highlight": True},
        {"rank": "1", "title": "Dolar & Euro Kuru", "sub": f"Euro/TL: {tickers.get('EUR', '—')}", "value": tickers.get("USD", "—"), "highlight": False},
        {"rank": "2", "title": "Serbest Piyasa Altın", "sub": "Kapalıçarşı & Banka Referans", "value": tickers.get("ALTIN", "—"), "highlight": False},
        {"rank": "3", "title": "En Yüksek Mevduat", "sub": f"500.000 TL 32 gün net: +{format_tl(best_dep.net_return)}" if best_dep else "32 günlük vadeli", "value": f"%{best_dep.annual_rate:.1f}".replace(".", ",") if best_dep else "%45,0", "highlight": False},
        {"rank": "4", "title": "En Uygun İhtiyaç Kredisi", "sub": f"{best_iht.bank_name} • 100.000 TL 12 ay" if best_iht else "100.000 TL 12 ay", "value": f"%{best_iht.monthly_rate:.2f}".replace(".", ",") if best_iht else "%2,89", "highlight": False},
    ]

    return {
        "source": winner["source"],
        "category": cat,
        "headline": winner["headline"],
        "summary": summary,
        "impact_note": impact_note,
        "details": f"{summary}\n\n{impact_note}",
        "question": question,
        "voice_script": voice_script,
        "tickers": tickers,
        "dep_leader": dep_str,
        "loan_leader": iht_str,
        "reel_rows": reel_rows,
        "score": winner["score"],
    }


def mark_news_dispatched(news_item: Dict) -> None:
    """Paylaşılan son dakika haberini önbelleğe kaydederek tekrar paylaşılmasını engeller."""
    if not news_item or not news_item.get("headline"):
        return
    cache = _load_full_cache()
    history: List[Dict] = cache.get("dispatched_news_history", [])
    history.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "headline": news_item["headline"],
        "category": news_item.get("category", ""),
    })
    cache["dispatched_news_history"] = history[-40:]
    _save_full_cache(cache)


def fetch_30d_investment_race(principal: float = 100_000) -> Dict:
    """
    Son 30 günde 100.000 TL'sini Vadeli Mevduat, Gram Altın, Dolar, Euro ve Borsa'ya (BIST 100)
    yatıran birinin bugün elindeki gerçek net TL tutarını ve sıralamasını hesaplar (0 TL maliyet, Yahoo Finance + Canlı Mevduat).
    """
    deps, _ = get_deposit_offers(principal, 32)
    best_dep = deps[0] if deps else DepositOffer("Ziraat Dinamik", 45.0, principal, 32)
    dep_net = best_dep.net_return
    dep_pct = (dep_net / principal) * 100.0

    # Yahoo Finance 1 aylık değişim oranları
    changes = {
        "USD": 1.90,
        "EUR": 0.15,
        "ONS": -8.50,
        "BIST100": 0.25,
    }
    prices = {
        "USD": (49.50, 50.46),
        "EUR": (55.55, 55.63),
        "ONS": (4100.0, 3750.0),
        "BIST100": (11420.0, 11442.0),
    }
    sym_map = {"USD": "TRY=X", "EUR": "EURTRY=X", "ONS": "GC=F", "BIST100": "XU100.IS"}
    for key, sym in sym_map.items():
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d",
                headers=HEADERS,
                timeout=8,
            ).json()
            res = r["chart"]["result"][0]
            closes = [float(c) for c in res["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) >= 5:
                p0, p1 = closes[0], closes[-1]
                prices[key] = (p0, p1)
                changes[key] = ((p1 - p0) / p0) * 100.0
        except Exception:
            pass

    # Gram Altın (TL) 30 günlük değişimi: (ONS_1 * USD_1) / (ONS_0 * USD_0)
    g0 = (prices["ONS"][0] * prices["USD"][0]) / 31.1035
    g1 = (prices["ONS"][1] * prices["USD"][1]) / 31.1035
    gold_pct = ((g1 - g0) / g0) * 100.0

    tickers = fetch_market_tickers()

    vehicles = [
        {
            "name": f"TL Vadeli Mevduat (%{best_dep.annual_rate:.1f})",
            "short_name": "TL Vadeli Mevduat",
            "detail": f"{best_dep.bank_name} • %17,5 stopaj sonrası 32 gün net",
            "pct": dep_pct,
            "net_diff": dep_net,
            "final_tl": principal + dep_net,
        },
        {
            "name": "Amerikan Doları (USD/TRY)",
            "short_name": "Dolar (USD/TRY)",
            "detail": f"30 gün önce: {prices['USD'][0]:.2f} TL  ->  Bugün: {prices['USD'][1]:.2f} TL",
            "pct": changes["USD"],
            "net_diff": principal * (changes["USD"] / 100.0),
            "final_tl": principal * (1.0 + changes["USD"] / 100.0),
        },
        {
            "name": "Gram Altın (24 Ayar)",
            "short_name": "Gram Altın",
            "detail": f"30 gün önce: {g0:,.0f} TL  ->  Bugün: {g1:,.0f} TL".replace(",", "."),
            "pct": gold_pct,
            "net_diff": principal * (gold_pct / 100.0),
            "final_tl": principal * (1.0 + gold_pct / 100.0),
        },
        {
            "name": "Euro (EUR/TRY)",
            "short_name": "Euro (EUR/TRY)",
            "detail": f"30 gün önce: {prices['EUR'][0]:.2f} TL  ->  Bugün: {prices['EUR'][1]:.2f} TL",
            "pct": changes["EUR"],
            "net_diff": principal * (changes["EUR"] / 100.0),
            "final_tl": principal * (1.0 + changes["EUR"] / 100.0),
        },
        {
            "name": "Borsa İstanbul (BIST 100)",
            "short_name": "Borsa (BIST 100)",
            "detail": f"30 gün önce: {prices['BIST100'][0]:,.0f}  ->  Bugün: {prices['BIST100'][1]:,.0f} puan".replace(",", "."),
            "pct": changes["BIST100"],
            "net_diff": principal * (changes["BIST100"] / 100.0),
            "final_tl": principal * (1.0 + changes["BIST100"] / 100.0),
        },
    ]

    vehicles.sort(key=lambda x: x["final_tl"], reverse=True)
    winner = vehicles[0]
    loser = vehicles[-1]
    spread_gap = winner["final_tl"] - loser["final_tl"]

    return {
        "principal": principal,
        "vehicles": vehicles,
        "winner": winner,
        "loser": loser,
        "spread_gap": spread_gap,
        "tickers": tickers,
    }


def get_weekly_bank_vs_duel(pair_idx: int = None) -> Dict:
    """
    Haftalık '2 Dev Banka Kafa Kafaya (VS) Düellosu' verilerini canlı oranlardan üretir.
    4 Raunt:
      1. 500.000 TL 32 Gün Vadeli Mevduat Net Getirisi
      2. 100.000 TL 12 Ay İhtiyaç Kredisi Aylık Taksiti
      3. 2.000.000 TL 120 Ay Konut Kredisi Aylık Taksiti
      4. 400.000 TL 36 Ay Taşıt Kredisi Aylık Taksiti
    """
    get_loan_offers("ihtiyac", 100_000, 12)
    get_loan_offers("konut", 2_000_000, 120)
    get_loan_offers("tasit", 400_000, 36)
    get_deposit_offers(500_000, 32)

    cache = _load_full_cache()
    dep_map = cache.get("mevduat_oranlari", DEFAULT_RATES["mevduat"])
    iht_map = cache.get("ihtiyac_kredisi", DEFAULT_RATES["ihtiyac"])
    kon_map = cache.get("konut_kredisi", DEFAULT_RATES["konut"])
    tas_map = cache.get("tasit_kredisi", DEFAULT_RATES["tasit"])

    pairs = [
        ("Akbank", "Garanti BBVA", "ÖZEL BANKACILIK DEVLERİ DÜELLOSU"),
        ("Ziraat Bankası", "VakıfBank", "KAMU BANKALARI DEV DÜELLOSU"),
        ("Yapı Kredi", "Türkiye İş Bankası", "KÖKLÜ BANKALAR KREDİ & MEVDUAT DÜELLOSU"),
        ("DenizBank", "QNB", "YÜKSEK FAİZ & UYGUN KREDİ DÜELLOSU"),
        ("ING", "CEPTETEB", "DİJİTAL & AVANTAJLI BANKACILIK DÜELLOSU"),
    ]
    if pair_idx is None:
        week_no = datetime.now().isocalendar()[1]
        pair_idx = week_no % len(pairs)
    b1, b2, subtitle = pairs[pair_idx % len(pairs)]

    # 1. Mevduat (Yüksek olan kazanır)
    r_dep1 = float(dep_map.get(b1, DEFAULT_RATES["mevduat"].get(b1, 38.0)))
    r_dep2 = float(dep_map.get(b2, DEFAULT_RATES["mevduat"].get(b2, 38.0)))
    d1 = DepositOffer(b1, r_dep1, 500_000, 32)
    d2 = DepositOffer(b2, r_dep2, 500_000, 32)

    # 2. İhtiyaç Kredisi (Düşük olan kazanır)
    r_iht1 = float(iht_map.get(b1, DEFAULT_RATES["ihtiyac"].get(b1, 3.59)))
    r_iht2 = float(iht_map.get(b2, DEFAULT_RATES["ihtiyac"].get(b2, 3.59)))
    l_iht1 = LoanOffer(b1, r_iht1, 100_000, 12, "ihtiyac")
    l_iht2 = LoanOffer(b2, r_iht2, 100_000, 12, "ihtiyac")

    # 3. Konut Kredisi (Düşük olan kazanır)
    r_kon1 = float(kon_map.get(b1, DEFAULT_RATES["konut"].get(b1, 3.09)))
    r_kon2 = float(kon_map.get(b2, DEFAULT_RATES["konut"].get(b2, 3.09)))
    l_kon1 = LoanOffer(b1, r_kon1, 2_000_000, 120, "konut")
    l_kon2 = LoanOffer(b2, r_kon2, 2_000_000, 120, "konut")

    # 4. Taşıt Kredisi (Düşük olan kazanır)
    r_tas1 = float(tas_map.get(b1, DEFAULT_RATES["tasit"].get(b1, 3.39)))
    r_tas2 = float(tas_map.get(b2, DEFAULT_RATES["tasit"].get(b2, 3.39)))
    l_tas1 = LoanOffer(b1, r_tas1, 400_000, 36, "tasit")
    l_tas2 = LoanOffer(b2, r_tas2, 400_000, 36, "tasit")

    rounds = [
        {
            "title": "500.000 TL Mevduat (32 Gün Net)",
            "b1_val": f"+{format_tl(d1.net_return)}",
            "b1_sub": f"Yıllık %{d1.annual_rate:.1f}",
            "b2_val": f"+{format_tl(d2.net_return)}",
            "b2_sub": f"Yıllık %{d2.annual_rate:.1f}",
            "winner": 1 if d1.net_return > d2.net_return else (2 if d2.net_return > d1.net_return else 0),
        },
        {
            "title": "100.000 TL İhtiyaç Kredisi (12 Ay)",
            "b1_val": f"{format_tl(l_iht1.monthly_installment)}/ay",
            "b1_sub": f"Aylık %{l_iht1.monthly_rate:.2f}",
            "b2_val": f"{format_tl(l_iht2.monthly_installment)}/ay",
            "b2_sub": f"Aylık %{l_iht2.monthly_rate:.2f}",
            "winner": 1 if l_iht1.monthly_rate < l_iht2.monthly_rate else (2 if l_iht2.monthly_rate < l_iht1.monthly_rate else 0),
        },
        {
            "title": "2.000.000 TL Konut Kredisi (120 Ay)",
            "b1_val": f"{format_tl(l_kon1.monthly_installment)}/ay",
            "b1_sub": f"Aylık %{l_kon1.monthly_rate:.2f}",
            "b2_val": f"{format_tl(l_kon2.monthly_installment)}/ay",
            "b2_sub": f"Aylık %{l_kon2.monthly_rate:.2f}",
            "winner": 1 if l_kon1.monthly_rate < l_kon2.monthly_rate else (2 if l_kon2.monthly_rate < l_kon1.monthly_rate else 0),
        },
        {
            "title": "400.000 TL Taşıt Kredisi (36 Ay)",
            "b1_val": f"{format_tl(l_tas1.monthly_installment)}/ay",
            "b1_sub": f"Aylık %{l_tas1.monthly_rate:.2f}",
            "b2_val": f"{format_tl(l_tas2.monthly_installment)}/ay",
            "b2_sub": f"Aylık %{l_tas2.monthly_rate:.2f}",
            "winner": 1 if l_tas1.monthly_rate < l_tas2.monthly_rate else (2 if l_tas2.monthly_rate < l_tas1.monthly_rate else 0),
        },
    ]

    score1 = sum(1 for r in rounds if r["winner"] in (1, 0))
    score2 = sum(1 for r in rounds if r["winner"] in (2, 0))
    overall_winner = b1 if score1 > score2 else (b2 if score2 > score1 else "BERABERE")

    return {
        "bank1": b1,
        "bank2": b2,
        "subtitle": subtitle,
        "rounds": rounds,
        "score1": score1,
        "score2": score2,
        "overall_winner": overall_winner,
    }
