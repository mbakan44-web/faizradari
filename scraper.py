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

DEFAULT_RATES = {
    "ihtiyac": {
        "Alternatif Bank": 2.49,
        "DenizBank": 2.89,
        "ON Dijital": 2.99,
        "Enpara.com": 3.14,
        "CEPTETEB": 3.39,
        "Akbank": 3.49,
        "Türkiye İş Bankası": 3.68,
        "Garanti BBVA": 3.89,
    },
    "konut": {
        "Ziraat Bankası": 2.79,
        "QNB": 2.84,
        "Akbank": 2.89,
        "Garanti BBVA": 2.91,
        "VakıfBank": 2.99,
        "Türkiye İş Bankası": 3.05,
        "Yapı Kredi": 3.09,
        "Halkbank": 3.19,
    },
    "tasit": {
        "Akbank": 3.19,
        "Garanti BBVA": 3.25,
        "Türkiye İş Bankası": 3.29,
        "Kuveyt Türk (Finansman)": 3.34,
        "VakıfBank": 3.39,
        "Ziraat Bankası": 3.45,
        "Yapı Kredi": 3.49,
        "QNB": 3.59,
    },
    "mevduat": {
        "ON Dijital (ON Plus)": 51.0,
        "CEPTETEB (Marifetli Hesap)": 50.0,
        "ING (Turuncu Ekstra)": 50.0,
        "Alternatif Bank (VOV Hesap)": 49.0,
        "Fibabanka (Kiraz Hesap)": 48.5,
        "Akbank (Serbest Plus)": 48.0,
        "Garanti BBVA (E-Vadeli)": 47.0,
        "Enpara.com (Vadeli TL)": 46.5,
    },
}

ZERO_INTEREST_OFFERS = [
    {"bank": "Garanti BBVA", "amount": "50.000 TL", "term": "3-6 Ay", "detail": "25.000 TL Kredi + 25.000 TL Taksitli Avans (%0 Faiz)"},
    {"bank": "Enpara.com", "amount": "50.000 TL", "term": "6 Ay", "detail": "Yeni müşterilere özel 50.000 TL'ye varan %0 faizli kredi"},
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
    slug_map = {
        "ihtiyac": ("ihtiyac-kredisi", 2.0, 6.5),
        "konut": ("konut-kredisi", 2.2, 5.5),
        "tasit": ("tasit-kredisi", 2.4, 6.0),
    }
    slug, min_r, max_r = slug_map.get(loan_type, ("ihtiyac-kredisi", 2.0, 6.5))
    urls = [
        f"https://www.hangikredi.com/kredi/{slug}?amount={int(principal)}&maturity={months}",
        f"https://www.enuygun.com/kredi/{slug}/",
    ]
    known_banks = [
        "QNB", "Enpara", "Akbank", "Garanti BBVA", "İş Bankası", "Yapı Kredi",
        "CEPTETEB", "DenizBank", "ING", "ON Dijital", "Alternatif Bank",
        "N Kolay", "Fibabanka", "Ziraat", "VakıfBank", "Halkbank", "Kuveyt Türk"
    ]
    scraped: List[Tuple[str, float]] = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            text = resp.text
            for bank in known_banks:
                pattern = rf"{re.escape(bank)}[\s\S]{{1,350}}?%?\s*([2-6][,\.][0-9]{{2}})"
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate_val = float(match.group(1).replace(",", "."))
                    norm_name = "Enpara.com" if bank == "Enpara" else ("Türkiye İş Bankası" if bank == "İş Bankası" else ("Ziraat Bankası" if bank == "Ziraat" else bank))
                    if min_r <= rate_val <= max_r and not any(b == norm_name for b, _ in scraped):
                        scraped.append((norm_name, rate_val))
            if len(scraped) >= 5:
                break
        except Exception:
            continue
    return scraped


def _load_full_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
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
    İhtiyaç, Konut veya Taşıt kredisi oranlarını çeker, önceki önbellekle karşılaştırıp
    faiz indirimi yapan banka varsa `RateDropAlert` listesiyle birlikte döndürür.
    """
    cache = _load_full_cache()
    cache_key = f"{loan_type}_kredisi"
    old_rates: Dict[str, float] = dict(cache.get(cache_key, DEFAULT_RATES.get(loan_type, {})))
    old_rates.pop("TEB", None)

    scraped = _scrape_loan_rates_by_type(loan_type, principal, months)
    alerts: List[RateDropAlert] = []
    current_rates = dict(old_rates)

    for bank_name, new_rate in scraped:
        prev_rate = old_rates.get(bank_name)
        if prev_rate is not None and new_rate <= prev_rate - 0.05:
            alerts.append(
                RateDropAlert(
                    bank_name=bank_name,
                    loan_type=loan_type,
                    old_rate=float(prev_rate),
                    new_rate=float(new_rate),
                    principal=principal,
                    months=months,
                )
            )
        current_rates[bank_name] = new_rate

    cache[cache_key] = current_rates
    if "mevduat_oranlari" not in cache:
        cache["mevduat_oranlari"] = DEFAULT_RATES["mevduat"]
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
    rates = cache.get("mevduat_oranlari", DEFAULT_RATES["mevduat"])
    offers = [
        DepositOffer(bank_name=bank, annual_rate=float(rate), principal=principal, days=days)
        for bank, rate in rates.items()
    ]
    offers.sort(key=lambda x: x.annual_rate, reverse=True)
    return offers[:8], ZERO_INTEREST_OFFERS


def get_bank_spread_offers() -> Tuple[List[SpreadOffer], List[SpreadOffer]]:
    """
    Bankaların canlı Dolar (USD/TRY) ve Gram Altın (TL) Alış, Satış ve Makas verilerini çeker.
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
                    name = re.sub(r"\d{2}:\d{2}(:\d{2})?", "", cols[0]).strip()
                    if not name or name in ("Kaynak", "Serbest Piyasa", "TCMB", "Altınkaynak", "Kapalıçarşı"):
                        continue
                    if name == "Enpara":
                        name = "Enpara.com"
                    if name == "QNB Finansbank":
                        name = "QNB"
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
                        usd_map["Enpara.com"] = SpreadOffer("Enpara.com", "USD", buy_v, sell_v)
                    elif "Altın (gram)" in label and "/USD" not in label and 5500.0 < buy_v < sell_v < 9000.0:
                        gold_map["Enpara.com"] = SpreadOffer("Enpara.com", "ALTIN", buy_v, sell_v)
    except Exception:
        pass

    bank_name_normalize = {
        "İşbank": "Türkiye İş Bankası",
        "Akbank": "Akbank",
        "Ziraat": "Ziraat Bankası",
        "HSBC": "HSBC",
        "Garanti": "Garanti BBVA",
        "Finansbank": "QNB",
        "Halkbank": "Halkbank",
        "Vakıfbank": "VakıfBank",
        "Yapı Kredi": "Yapı Kredi",
        "Denizbank": "DenizBank",
        "Kuveyt Türk": "Kuveyt Türk",
        "Enpara": "Enpara.com",
    }
    try:
        r_gold = requests.get("https://altin.in/banka/altin", headers=HEADERS, timeout=8)
        if r_gold.status_code == 200:
            soup_g = BeautifulSoup(r_gold.text, "html.parser")
            for ul in soup_g.find_all("ul"):
                parts = [p.strip() for p in ul.get_text("|", strip=True).split("|") if p.strip()]
                if len(parts) >= 5 and "Gram Altın" in parts:
                    raw_bank = parts[0]
                    norm_bank = bank_name_normalize.get(raw_bank, raw_bank)
                    if norm_bank == "Enpara.com" and "Enpara.com" in gold_map:
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
