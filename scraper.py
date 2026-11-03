import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import requests
from bs4 import BeautifulSoup
from calculator import LoanOffer, DepositOffer, SpreadOffer, RateDropAlert

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
        (r"^odeabank.*", "Odeabank"),
        (r"^anadolubank.*", "Anadolubank"),
        (r"^albaraka.*", "Albaraka Türk"),
        (r"^türkiye\s+finans.*", "Türkiye Finans"),
        (r"^şekerbank.*", "Şekerbank"),
        (r"^hsbc.*", "HSBC"),
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
        "QNB": 2.84,
        "Kuveyt Türk": 2.87,
        "Ziraat Bankası": 2.89,
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
        "ON Dijital": 51.0,
        "CEPTETEB": 50.0,
        "ING": 50.0,
        "Alternatif Bank": 49.0,
        "Fibabanka": 48.5,
        "Akbank": 48.0,
        "Garanti BBVA": 47.0,
        "Enpara": 46.5,
        "Türkiye İş Bankası": 44.0,
        "Yapı Kredi": 43.5,
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
    önceki önbellekle karşılaştırıp faiz indirimi yapan banka varsa `RateDropAlert`
    listesiyle birlikte döndürür.
    """
    cache = _load_full_cache()
    cache_key = f"{loan_type}_kredisi"

    # 1. Taban oranlar
    base_rates = clean_and_deduplicate_rates(DEFAULT_RATES.get(loan_type, {}), mode="min")

    # 2. Önbellekteki güncel oranlar (Eski önbellek taban orandaki indirimleri engellemesin diye min alınır)
    cached_rates = clean_and_deduplicate_rates(cache.get(cache_key, {}), mode="min")
    old_rates: Dict[str, float] = {}
    all_banks = set(base_rates.keys()) | set(cached_rates.keys())
    for b in all_banks:
        if b in base_rates and b in cached_rates:
            old_rates[b] = min(base_rates[b], cached_rates[b])
        elif b in base_rates:
            old_rates[b] = base_rates[b]
        else:
            old_rates[b] = cached_rates[b]

    # 3. Canlı tarama
    scraped = _scrape_loan_rates_by_type(loan_type, principal, months)
    alerts: List[RateDropAlert] = []
    current_rates = dict(old_rates)

    for bank_name, new_rate in scraped:
        norm_name = normalize_bank_name(bank_name)
        prev_rate = old_rates.get(norm_name)
        if prev_rate is not None and new_rate <= prev_rate - 0.05:
            alerts.append(
                RateDropAlert(
                    bank_name=norm_name,
                    loan_type=loan_type,
                    old_rate=float(prev_rate),
                    new_rate=float(new_rate),
                    principal=principal,
                    months=months,
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


def get_consumer_loan_offers(principal: float = 100_000, months: int = 12) -> List[LoanOffer]:
    offers, _ = get_loan_offers("ihtiyac", principal, months)
    return offers


def get_deposit_offers(principal: float = 500_000, days: int = 32) -> Tuple[List[DepositOffer], List[Dict]]:
    """500.000 TL 32 Gün Vadeli Mevduat net getiri tekliflerini ve %0 faizli nakit fırsatlarını döndürür."""
    cache = _load_full_cache()
    base_rates = clean_and_deduplicate_rates(DEFAULT_RATES["mevduat"], mode="max")
    cached_rates = clean_and_deduplicate_rates(cache.get("mevduat_oranlari", {}), mode="max")
    rates = dict(base_rates)
    rates.update(cached_rates)
    rates = clean_and_deduplicate_rates(rates, mode="max")

    cache["mevduat_oranlari"] = rates
    _save_full_cache(cache)

    offers = [
        DepositOffer(bank_name=bank, annual_rate=float(rate), principal=principal, days=days)
        for bank, rate in rates.items()
    ]
    offers.sort(key=lambda x: x.annual_rate, reverse=True)
    return offers[:8], ZERO_INTEREST_OFFERS


def get_bank_spread_offers() -> Tuple[List[SpreadOffer], List[SpreadOffer]]:
    """
    Bankaların canlı Dolar (USD/TRY) ve Gram Altın (TL) Alış, Satış ve Makas verilerini çeker.
    Tüm banka isimleri tekilleştirilmiş kanonik formatta sunulur.
    """
    usd_map: Dict[str, SpreadOffer] = {}
    gold_map: Dict[str, SpreadOffer] = {}

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
                    if 35.0 < buy_v < sell_v < 80.0:
                        usd_map[name] = SpreadOffer(
                            bank_name=name,
                            asset="USD",
                            buy_price=buy_v,
                            sell_price=sell_v,
                        )
    except Exception:
        pass

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
                    if "USD ($)" in label and 35.0 < buy_v < sell_v < 80.0:
                        usd_map["Enpara"] = SpreadOffer("Enpara", "USD", buy_v, sell_v)
                    elif "Altın (gram)" in label and "/USD" not in label and 5500.0 < buy_v < sell_v < 9000.0:
                        gold_map["Enpara"] = SpreadOffer("Enpara", "ALTIN", buy_v, sell_v)
    except Exception:
        pass

    try:
        r_gold = requests.get("https://altin.in/banka/altin", headers=HEADERS, timeout=8)
        if r_gold.status_code == 200:
            soup_g = BeautifulSoup(r_gold.text, "html.parser")
            for ul in soup_g.find_all("ul"):
                parts = [p.strip() for p in ul.get_text("|", strip=True).split("|") if p.strip()]
                if len(parts) >= 5 and "Gram Altın" in parts:
                    raw_bank = parts[0]
                    norm_bank = normalize_bank_name(raw_bank)
                    if norm_bank == "Enpara" and "Enpara" in gold_map:
                        continue
                    idx_g = parts.index("Gram Altın")
                    if len(parts) >= idx_g + 3:
                        buy_v = _parse_tr_float(parts[idx_g + 1])
                        sell_v = _parse_tr_float(parts[idx_g + 2])
                        if 5500.0 < buy_v < sell_v < 9000.0:
                            gold_map[norm_bank] = SpreadOffer(norm_bank, "ALTIN", buy_v, sell_v)
    except Exception:
        pass

    usd_list = sorted(usd_map.values(), key=lambda x: x.spread_pct)[:7]
    gold_list = sorted(gold_map.values(), key=lambda x: x.spread_pct)[:7]
    return usd_list, gold_list
