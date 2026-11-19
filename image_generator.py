from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont
from calculator import LoanOffer, DepositOffer, SpreadOffer, RateDropAlert, format_tl


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_candidates = (
        [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for path in font_candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_loan_table_image(
    offers: List[LoanOffer],
    tickers: Dict[str, str],
    output_path: str = "D:/faiz-radari/latest_loan_table.png",
) -> str:
    """
    İhtiyaç, Konut veya Taşıt Kredisi için kurumsal karşılaştırma tablosu (PNG) üretir.
    """
    width = 1280
    row_height = 68
    num_rows = len(offers)
    height = 380 + (num_rows * row_height) + 170

    loan_type = offers[0].loan_type if offers else "ihtiyac"
    theme_map = {
        "ihtiyac": {
            "accent": (16, 185, 129),
            "label": "İHTİYAÇ KREDİSİ",
            "sub": "Tüm bankalar için %15 KKDF, %15 BSMV vergileri ve yasal dosya masrafı (tahsis ücreti) dahil net hesaplamadır.",
            "fee_col": "DOSYA MASRAFI",
        },
        "konut": {
            "accent": (56, 189, 248),
            "label": "KONUT (EV) KREDİSİ",
            "sub": "Konut kredisinde KKDF ve BSMV %0'dır (vergiden muaf). Tahsis ücreti + ortalama ekspertiz/ipotek masrafı dahildir.",
            "fee_col": "TAHSİS+EKSPERTİZ",
        },
        "tasit": {
            "accent": (168, 85, 247),
            "label": "TAŞIT (ARAÇ) KREDİSİ",
            "sub": "Taşıt kredisinde %15 KKDF, %15 BSMV vergileri ve binde 5 tahsis ücreti dahil net geri ödeme hesaplamasıdır.",
            "fee_col": "DOSYA MASRAFI",
        },
    }
    theme = theme_map.get(loan_type, theme_map["ihtiyac"])
    accent = theme["accent"]

    img = Image.new("RGB", (width, height), color=(11, 17, 32))
    draw = ImageDraw.Draw(img)

    f_brand = _load_font(34, bold=True)
    f_sub = _load_font(20, bold=False)
    f_ticker_lbl = _load_font(17, bold=True)
    f_ticker_val = _load_font(20, bold=True)
    f_title = _load_font(26, bold=True)
    f_th = _load_font(18, bold=True)
    f_td = _load_font(21, bold=False)
    f_td_bold = _load_font(22, bold=True)
    f_badge = _load_font(14, bold=True)
    f_diff = _load_font(19, bold=True)
    f_disclaimer = _load_font(14, bold=False)

    # 1. Üst Başlık Barı
    draw.rectangle([(0, 0), (width, 110)], fill=(15, 23, 42))
    draw.rectangle([(0, 107), (width, 110)], fill=accent)

    draw.rounded_rectangle([(40, 24), (98, 82)], radius=14, fill=accent)
    draw.text((55, 30), "%", font=_load_font(36, bold=True), fill=(11, 17, 32))
    draw.text((115, 22), f"FAİZ RADARI | {theme['label']}", font=f_brand, fill=(248, 250, 252))
    draw.text((115, 62), "KREDİ, MEVDUAT & FİNANS MONİTÖRÜ  •  t.me/faizradari", font=f_sub, fill=(148, 163, 184))

    now_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
    draw.rounded_rectangle([(width - 310, 32), (width - 40, 78)], radius=10, fill=(30, 41, 59))
    draw.text((width - 290, 42), f"GÜNCEL: {now_str}", font=_load_font(18, bold=True), fill=(56, 189, 248))

    # 2. Canlı Kur Şeridi (Ticker Bar)
    draw.rounded_rectangle([(40, 128), (width - 40, 184)], radius=10, fill=(19, 28, 49), outline=(30, 41, 59), width=2)
    draw.text((60, 144), "PİYASA ÖZETİ:", font=f_ticker_lbl, fill=(245, 158, 11))

    draw.text((240, 144), "USD/TRY:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((335, 142), tickers.get("USD", "—"), font=f_ticker_val, fill=(248, 250, 252))

    draw.text((520, 144), "EUR/TRY:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((615, 142), tickers.get("EUR", "—"), font=f_ticker_val, fill=(248, 250, 252))

    draw.text((800, 144), "GRAM ALTIN:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((930, 142), tickers.get("ALTIN", "—"), font=f_ticker_val, fill=(250, 204, 21))

    # 3. Tablo Ana Başlığı
    principal_str = format_tl(offers[0].principal) if offers else "100.000 TL"
    months_val = offers[0].months if offers else 12
    draw.text(
        (40, 205),
        f"{principal_str} {theme['label']} — {months_val} AY VADE NET GERİ ÖDEME TABLOSU",
        font=f_title,
        fill=(255, 255, 255),
    )
    draw.text((40, 240), theme["sub"], font=_load_font(17, bold=False), fill=(148, 163, 184))

    # 4. Tablo Sütun Başlıkları
    table_top = 280
    draw.rounded_rectangle([(40, table_top), (width - 40, table_top + 52)], radius=8, fill=(30, 41, 59))

    col_x = {
        "bank": 65,
        "rate": 430,
        "monthly": 610,
        "fee": 835,
        "total": 1035,
    }
    draw.text((col_x["bank"], table_top + 14), "BANKA", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["rate"], table_top + 14), "FAİZ ORANI", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["monthly"], table_top + 14), "AYLIK TAKSİT", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["fee"], table_top + 14), theme["fee_col"], font=f_th, fill=(203, 213, 225))
    draw.text((col_x["total"], table_top + 14), "TOPLAM ÖDEME", font=f_th, fill=(245, 158, 11))

    # 5. Tablo Satırları
    y = table_top + 60
    for idx, offer in enumerate(offers):
        is_best = idx == 0
        if is_best:
            row_bg = (6, 58, 46)
            border_col = (16, 185, 129)
        else:
            row_bg = (17, 25, 44) if idx % 2 == 0 else (23, 33, 56)
            border_col = (30, 41, 59)

        draw.rounded_rectangle(
            [(40, y), (width - 40, y + row_height - 8)],
            radius=8,
            fill=row_bg,
            outline=border_col,
            width=2 if is_best else 1,
        )

        bank_color = (52, 211, 153) if is_best else (241, 245, 249)
        draw.text((col_x["bank"], y + 16), f"{idx + 1}. {offer.bank_name}", font=f_td_bold if is_best else f_td, fill=bank_color)

        if is_best:
            draw.rounded_rectangle([(315, y + 17), (408, y + 43)], radius=6, fill=(16, 185, 129))
            draw.text((324, y + 21), "EN UYGUN", font=f_badge, fill=(6, 25, 20))

        rate_str = f"%{offer.monthly_rate:.2f}".replace(".", ",")
        draw.text((col_x["rate"], y + 16), rate_str, font=f_td_bold, fill=(250, 204, 21) if is_best else (226, 232, 240))
        draw.text((col_x["monthly"], y + 16), format_tl(offer.monthly_installment), font=f_td, fill=(241, 245, 249))
        draw.text((col_x["fee"], y + 16), format_tl(offer.allocation_fee), font=f_td, fill=(148, 163, 184))

        total_color = (52, 211, 153) if is_best else (248, 250, 252)
        draw.text((col_x["total"], y + 16), format_tl(offer.total_repayment), font=f_td_bold, fill=total_color)

        y += row_height

    # 6. Alt Analiz & Fark Kutusu
    if len(offers) >= 2:
        diff_tl = offers[-1].total_repayment - offers[0].total_repayment
        draw.rounded_rectangle([(40, y + 8), (width - 40, y + 64)], radius=8, fill=(30, 27, 75), outline=(99, 102, 241), width=1)
        summary_txt = (
            f">> RADAR ANALİZİ: En avantajlı banka ({offers[0].bank_name}) ile listenin sonundaki banka arasında "
            f"toplam {format_tl(diff_tl)} cebinizde kalır!"
        )
        draw.text((60, y + 23), summary_txt, font=f_diff, fill=(224, 231, 255))
        y += 78

    # 7. Yasal Sorumluluk Reddi (Disclaimer)
    disclaimer_line1 = (
        "YASAL UYARI (SORUMLULUK REDDİ): Bu tablodaki faiz oranları ve maliyet hesaplamaları bankaların kamuya açık "
        "tarifelerinden derlenmiş olup yalnızca genel bilgilendirme amaçlıdır."
    )
    disclaimer_line2 = (
        "Bankalar kredi notuna, müşteri segmentine ve piyasa koşullarına göre oranları anlık değiştirebilir. "
        "Burada yer alan bilgiler hiçbir şekilde yatırım veya finansal danışmanlık tavsiyesi değildir.  •  @faizradari"
    )
    draw.text((40, y + 8), disclaimer_line1, font=f_disclaimer, fill=(100, 116, 139))
    draw.text((40, y + 30), disclaimer_line2, font=f_disclaimer, fill=(100, 116, 139))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_deposit_table_image(
    deposits: List[DepositOffer],
    zero_offers: List[Dict],
    tickers: Dict[str, str],
    output_path: str = "D:/faiz-radari/latest_deposit_table.png",
) -> str:
    """
    500.000 TL 32 Gün Vadeli Mevduat Net Getiri Tablosu + Yeni Müşteri %0 Faiz Fırsatları görseli üretir.
    """
    width = 1280
    row_height = 64
    num_rows = len(deposits)
    zero_rows = len(zero_offers[:5])
    height = 370 + (num_rows * row_height) + 90 + (zero_rows * 46) + 165

    img = Image.new("RGB", (width, height), color=(11, 17, 32))
    draw = ImageDraw.Draw(img)

    f_brand = _load_font(34, bold=True)
    f_sub = _load_font(20, bold=False)
    f_ticker_lbl = _load_font(17, bold=True)
    f_ticker_val = _load_font(20, bold=True)
    f_title = _load_font(25, bold=True)
    f_th = _load_font(17, bold=True)
    f_td = _load_font(20, bold=False)
    f_td_bold = _load_font(21, bold=True)
    f_badge = _load_font(13, bold=True)
    f_diff = _load_font(18, bold=True)
    f_disclaimer = _load_font(14, bold=False)

    # 1. Üst Başlık Barı
    draw.rectangle([(0, 0), (width, 110)], fill=(15, 23, 42))
    draw.rectangle([(0, 107), (width, 110)], fill=(234, 179, 8))

    draw.rounded_rectangle([(40, 24), (98, 82)], radius=14, fill=(234, 179, 8))
    draw.text((55, 30), "₺", font=_load_font(36, bold=True), fill=(11, 17, 32))
    draw.text((115, 22), "FAİZ RADARI | VADELİ MEVDUAT & %0 FAİZ", font=f_brand, fill=(248, 250, 252))
    draw.text((115, 62), "BANKALARIN NET MEVDUAT KAZANCI VE HOŞ GELDİN FIRSATLARI  •  t.me/faizradari", font=f_sub, fill=(148, 163, 184))

    now_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
    draw.rounded_rectangle([(width - 310, 32), (width - 40, 78)], radius=10, fill=(30, 41, 59))
    draw.text((width - 290, 42), f"GÜNCEL: {now_str}", font=_load_font(18, bold=True), fill=(250, 204, 21))

    # 2. Piyasa Özeti
    draw.rounded_rectangle([(40, 128), (width - 40, 184)], radius=10, fill=(19, 28, 49), outline=(30, 41, 59), width=2)
    draw.text((60, 144), "PİYASA ÖZETİ:", font=f_ticker_lbl, fill=(245, 158, 11))
    draw.text((240, 144), "USD/TRY:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((335, 142), tickers.get("USD", "—"), font=f_ticker_val, fill=(248, 250, 252))
    draw.text((520, 144), "EUR/TRY:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((615, 142), tickers.get("EUR", "—"), font=f_ticker_val, fill=(248, 250, 252))
    draw.text((800, 144), "GRAM ALTIN:", font=f_ticker_lbl, fill=(148, 163, 184))
    draw.text((930, 142), tickers.get("ALTIN", "—"), font=f_ticker_val, fill=(250, 204, 21))

    # 3. Tablo Başlığı
    principal_str = format_tl(deposits[0].principal) if deposits else "500.000 TL"
    days_val = deposits[0].days if deposits else 32
    draw.text(
        (40, 204),
        f"{principal_str} ANAPARA — {days_val} GÜNLÜK VADELİ MEVDUAT NET FAİZ KAZANCI TABLOSU",
        font=f_title,
        fill=(255, 255, 255),
    )
    draw.text(
        (40, 238),
        "Yıllık brüt mevduat faiz oranları üzerinden %17,5 stopaj vergisi düşülerek net ele geçecek kazanç hesaplanmıştır.",
        font=_load_font(17, bold=False),
        fill=(148, 163, 184),
    )

    # 4. Sütunlar
    table_top = 276
    draw.rounded_rectangle([(40, table_top), (width - 40, table_top + 48)], radius=8, fill=(30, 41, 59))
    col_x = {"bank": 65, "rate": 465, "gross": 640, "net": 845, "total": 1055}
    draw.text((col_x["bank"], table_top + 13), "BANKA / MEVDUAT HESABI", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["rate"], table_top + 13), "YILLIK FAİZ", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["gross"], table_top + 13), "BRÜT GETİRİ", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["net"], table_top + 13), "NET KAZANÇ", font=f_th, fill=(52, 211, 153))
    draw.text((col_x["total"], table_top + 13), "VADE SONU TOPLAM", font=f_th, fill=(250, 204, 21))

    y = table_top + 56
    for idx, dep in enumerate(deposits):
        is_best = idx == 0
        row_bg = (6, 58, 46) if is_best else ((17, 25, 44) if idx % 2 == 0 else (23, 33, 56))
        border_col = (16, 185, 129) if is_best else (30, 41, 59)
        draw.rounded_rectangle(
            [(40, y), (width - 40, y + row_height - 8)],
            radius=8,
            fill=row_bg,
            outline=border_col,
            width=2 if is_best else 1,
        )

        bank_col = (52, 211, 153) if is_best else (241, 245, 249)
        draw.text((col_x["bank"], y + 15), f"{idx + 1}. {dep.bank_name}", font=f_td_bold if is_best else f_td, fill=bank_col)
        if is_best:
            draw.rounded_rectangle([(355, y + 16), (448, y + 40)], radius=6, fill=(16, 185, 129))
            draw.text((363, y + 19), "EN YÜKSEK", font=f_badge, fill=(6, 25, 20))

        rate_s = f"%{dep.annual_rate:.1f}".replace(".", ",")
        draw.text((col_x["rate"], y + 15), rate_s, font=f_td_bold, fill=(250, 204, 21) if is_best else (226, 232, 240))
        draw.text((col_x["gross"], y + 15), format_tl(dep.gross_return), font=f_td, fill=(148, 163, 184))
        draw.text((col_x["net"], y + 15), f"+{format_tl(dep.net_return)}", font=f_td_bold, fill=(52, 211, 153))
        draw.text((col_x["total"], y + 15), format_tl(dep.total_balance), font=f_td_bold, fill=(248, 250, 252))
        y += row_height

    # 5. Yeni Müşterilere Özel %0 Faizli Nakit Kutusu
    y += 10
    box_h = 56 + (zero_rows * 44)
    draw.rounded_rectangle([(40, y), (width - 40, y + box_h)], radius=10, fill=(23, 21, 58), outline=(139, 92, 246), width=2)
    draw.text(
        (60, y + 14),
        ">> YENİ MÜŞTERİLERE ÖZEL %0 FAİZLİ KREDİ & TAKSİTLİ NAKİT AVANS FIRSATLARI",
        font=_load_font(20, bold=True),
        fill=(196, 181, 253),
    )
    zy = y + 52
    for z in zero_offers[:5]:
        draw.text((65, zy), f"• {z['bank']}:", font=_load_font(18, bold=True), fill=(250, 204, 21))
        draw.text((255, zy), f"{z['amount']} ({z['term']})  —  {z['detail']}", font=_load_font(18, bold=False), fill=(241, 245, 249))
        zy += 42

    y += box_h + 18

    # 6. Yasal Uyarı
    disclaimer_line1 = (
        "YASAL UYARI (SORUMLULUK REDDİ): Mevduat faiz oranları ve %0 faizli kampanya limitleri bankaların hoş geldin / yeni müşteri "
        "koşullarına göre değişiklik gösterebilir."
    )
    disclaimer_line2 = (
        "Tablodaki veriler açık kaynaklardan derlenmiş olup bilgilendirme amaçlıdır, yatırım veya finansal tavsiye değildir.  •  @faizradari"
    )
    draw.text((40, y), disclaimer_line1, font=f_disclaimer, fill=(100, 116, 139))
    draw.text((40, y + 22), disclaimer_line2, font=f_disclaimer, fill=(100, 116, 139))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_spread_table_image(
    usd_spreads: List[SpreadOffer],
    gold_spreads: List[SpreadOffer],
    tickers: Dict[str, str],
    output_path: str = "D:/faiz-radari/latest_spread_table.png",
) -> str:
    """
    Sol panelde Bankaların Canlı Dolar (USD) Makas Tablosu,
    Sağ panelde Bankaların Canlı Gram Altın (TL) Makas Tablosunu gösteren
    yüksek çözünürlüklü kurumsal PNG görseli üretir.
    """
    width = 1400
    max_rows = max(len(usd_spreads), len(gold_spreads), 6)
    row_h = 64
    height = 310 + (max_rows * row_h) + 175

    img = Image.new("RGB", (width, height), color=(11, 17, 32))
    draw = ImageDraw.Draw(img)

    f_brand = _load_font(34, bold=True)
    f_sub = _load_font(19, bold=False)
    f_panel_title = _load_font(22, bold=True)
    f_th = _load_font(16, bold=True)
    f_td = _load_font(19, bold=False)
    f_td_bold = _load_font(19, bold=True)
    f_diff = _load_font(18, bold=True)
    f_disclaimer = _load_font(14, bold=False)

    # 1. Üst Başlık Barı
    draw.rectangle([(0, 0), (width, 108)], fill=(15, 23, 42))
    draw.rectangle([(0, 105), (width, 108)], fill=(245, 158, 11))

    draw.rounded_rectangle([(40, 22), (98, 80)], radius=14, fill=(245, 158, 11))
    draw.text((55, 28), "₺", font=_load_font(36, bold=True), fill=(11, 17, 32))
    draw.text((115, 20), "FAİZ RADARI | DÖVİZ & ALTIN MAKAS MONİTÖRÜ", font=f_brand, fill=(248, 250, 252))
    draw.text(
        (115, 62),
        f"BANKALARIN CANLI ALIŞ - SATIŞ VE MAKAS ARALIKLARI  •  Piyasa Ref: USD {tickers.get('USD')} | Gram Altın {tickers.get('ALTIN')}",
        font=f_sub,
        fill=(148, 163, 184),
    )

    now_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
    draw.rounded_rectangle([(width - 310, 30), (width - 40, 76)], radius=10, fill=(30, 41, 59))
    draw.text((width - 290, 40), f"CANLI: {now_str}", font=_load_font(18, bold=True), fill=(250, 204, 21))

    # 2. Sol Panel (USD) ve Sağ Panel (Gram Altın) Koordinatları
    left_x1, left_x2 = 40, 685
    right_x1, right_x2 = 715, 1360
    top_y = 132

    draw.rounded_rectangle([(left_x1, top_y), (left_x2, top_y + 50)], radius=8, fill=(6, 78, 59))
    draw.text((left_x1 + 20, top_y + 12), "[$] BANKALARDA DOLAR (USD) MAKAS TABLOSU", font=f_panel_title, fill=(167, 243, 208))

    draw.rounded_rectangle([(right_x1, top_y), (right_x2, top_y + 50)], radius=8, fill=(120, 53, 15))
    draw.text((right_x1 + 20, top_y + 12), "[AU] BANKALARDA GRAM ALTIN MAKAS TABLOSU", font=f_panel_title, fill=(253, 230, 138))

    def draw_panel_table(x1: int, x2: int, offers: List[SpreadOffer], is_gold: bool):
        th_y = top_y + 62
        draw.rounded_rectangle([(x1, th_y), (x2, th_y + 44)], radius=6, fill=(30, 41, 59))
        draw.text((x1 + 16, th_y + 11), "BANKA / KURUM", font=f_th, fill=(203, 213, 225))
        draw.text((x1 + 240, th_y + 11), "ALIŞ", font=f_th, fill=(203, 213, 225))
        draw.text((x1 + 365, th_y + 11), "SATIŞ", font=f_th, fill=(203, 213, 225))
        draw.text((x1 + 495, th_y + 11), "MAKAS (TL / %)", font=f_th, fill=(250, 204, 21))

        row_y = th_y + 52
        for idx, item in enumerate(offers):
            is_best = idx == 0
            bg = (6, 58, 46) if is_best else ((17, 25, 44) if idx % 2 == 0 else (23, 33, 56))
            border = (16, 185, 129) if is_best else (30, 41, 59)
            draw.rounded_rectangle(
                [(x1, row_y), (x2, row_y + row_h - 8)],
                radius=7,
                fill=bg,
                outline=border,
                width=2 if is_best else 1,
            )

            name_col = (52, 211, 153) if is_best else (241, 245, 249)
            draw.text((x1 + 16, row_y + 16), f"{idx + 1}. {item.bank_name}", font=f_td_bold if is_best else f_td, fill=name_col)

            buy_s = f"{item.buy_price:,.0f} ₺".replace(",", ".") if is_gold else f"{item.buy_price:.2f} ₺".replace(".", ",")
            sell_s = f"{item.sell_price:,.0f} ₺".replace(",", ".") if is_gold else f"{item.sell_price:.2f} ₺".replace(".", ",")
            spread_tl_s = f"{item.spread_tl:,.0f} ₺".replace(",", ".") if is_gold else f"{item.spread_tl:.2f} ₺".replace(".", ",")
            spread_pct_s = f"%{item.spread_pct:.2f}".replace(".", ",")

            draw.text((x1 + 240, row_y + 16), buy_s, font=f_td, fill=(226, 232, 240))
            draw.text((x1 + 365, row_y + 16), sell_s, font=f_td, fill=(226, 232, 240))

            sp_col = (52, 211, 153) if is_best else (250, 204, 21)
            draw.text((x1 + 495, row_y + 16), f"{spread_tl_s} ({spread_pct_s})", font=f_td_bold, fill=sp_col)

            row_y += row_h
        return row_y

    end_y_left = draw_panel_table(left_x1, left_x2, usd_spreads, is_gold=False)
    end_y_right = draw_panel_table(right_x1, right_x2, gold_spreads, is_gold=True)
    y = max(end_y_left, end_y_right)

    # 3. Alt Radar Analiz Kutusu
    best_usd = usd_spreads[0] if usd_spreads else None
    best_gold = gold_spreads[0] if gold_spreads else None
    draw.rounded_rectangle([(40, y + 8), (width - 40, y + 62)], radius=8, fill=(30, 27, 75), outline=(99, 102, 241), width=1)
    if best_usd and best_gold:
        summary_txt = (
            f">> RADAR ANALİZİ: Şu an en düşük Dolar makası {best_usd.bank_name} (%{best_usd.spread_pct:.2f}), "
            f"en düşük Gram Altın makası ise {best_gold.bank_name} (%{best_gold.spread_pct:.2f}) tarafında uygulanmaktadır."
        )
    else:
        summary_txt = ">> RADAR ANALİZİ: Mesai saatleri dışında bankaların döviz ve altın makas aralıkları açılmaktadır."
    draw.text((60, y + 22), summary_txt, font=f_diff, fill=(224, 231, 255))
    y += 76

    # 4. Yasal Sorumluluk Reddi (Disclaimer)
    disclaimer_line1 = (
        "YASAL UYARI (SORUMLULUK REDDİ): Tablodaki döviz ve altın alış-satış kurları bankaların açık veri kaynaklarından anlık "
        "derlenmektedir ve yalnızca bilgilendirme amaçlıdır."
    )
    disclaimer_line2 = (
        "Bankalar piyasa yoğunluğuna ve mesai saatlerine göre makas aralıklarını anlık değiştirebilir. "
        "Burada yer alan veriler yatırım veya finansal danışmanlık tavsiyesi değildir.  •  @faizradari"
    )
    draw.text((40, y + 8), disclaimer_line1, font=f_disclaimer, fill=(100, 116, 139))
    draw.text((40, y + 30), disclaimer_line2, font=f_disclaimer, fill=(100, 116, 139))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_rate_drop_alert_image(
    alerts: List[RateDropAlert],
    output_path: str = "D:/faiz-radari/latest_alert.png",
) -> str:
    """
    Bir banka faiz indirdiğinde veya yükselttiğinde otomatik üretilen FLAŞ FAİZ DEĞİŞİMİ ALARMI görseli.
    """
    width = 1200
    row_h = 96
    height = 280 + (len(alerts) * row_h) + 120

    img = Image.new("RGB", (width, height), color=(15, 10, 28))
    draw = ImageDraw.Draw(img)

    header_title = "FLAŞ ALARM | BANKA FAİZ İNDİRİMİ YAKALANDI!"
    bar_fill = (6, 78, 59)

    draw.rectangle([(0, 0), (width, 110)], fill=bar_fill)
    draw.rectangle([(0, 106), (width, 110)], fill=(250, 204, 21))

    draw.text((45, 22), header_title, font=_load_font(30, bold=True), fill=(255, 255, 255))
    draw.text((45, 65), "FAİZ RADARI ANLIK ORAN DEĞİŞİM MONİTÖRÜ  •  t.me/faizradari", font=_load_font(19, bold=False), fill=(209, 250, 229))

    loan_names = {"ihtiyac": "İhtiyaç Kredisi", "tasit": "Taşıt Kredisi", "konut": "Konut Kredisi"}

    y = 140
    for alert in alerts:
        old_s = f"%{alert.old_rate:.2f}".replace(".", ",")
        new_s = f"%{alert.new_rate:.2f}".replace(".", ",")
        lname = loan_names.get(alert.loan_type, "Kredi")

        bg_color = (6, 58, 46)
        border_color = (16, 185, 129)
        action_tag = "📉 FAİZ İNDİRDİ"
        tag_color = (52, 211, 153)
        diff_desc = f"{format_tl(alert.principal)} ({alert.months} Ay) kredide toplam geri ödeme {format_tl(alert.total_savings)} AZALDI! (Yeni Taksit: {format_tl(alert.new_offer.monthly_installment)})"

        draw.rounded_rectangle([(40, y), (width - 40, y + row_h - 12)], radius=10, fill=bg_color, outline=border_color, width=2)
        line1 = f"{alert.bank_name} ({lname})  |  Eski: {old_s}  ➔  YENİ ORAN: {new_s}  [{action_tag}]"

        draw.text((65, y + 16), line1, font=_load_font(22, bold=True), fill=tag_color)
        draw.text((65, y + 50), diff_desc, font=_load_font(18, bold=False), fill=(241, 245, 249))
        y += row_h

    draw.text(
        (40, y + 20),
        "YASAL UYARI: Veriler bankaların kamuya açık ekranlarından otomatik tespit edilmiştir, yatırım tavsiyesi değildir.  •  @faizradari",
        font=_load_font(14, bold=False),
        fill=(148, 163, 184),
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_briefing_table_image(
    items: List[str],
    title: str = "GÜNÜN FİNANS RAPORU",
    output_path: str = "D:/faiz-radari/latest_briefing_table.png",
) -> str:
    """
    Faiz Radarı'nın özgün, modern kart tasarımlı 1080x1080 'GÜNÜN FİNANS RAPORU' infografiği.
    10 ayrı finans ve faiz maddesini 2 sütunlu şık gösterge paneli (dashboard) kartları halinde çizer.
    """
    width, height = 1080, 1080
    img = Image.new("RGB", (width, height), color=(8, 13, 24))
    draw = ImageDraw.Draw(img)

    # 1. Koyu lacivert / obsidyen degrade arka plan
    for y in range(height):
        r = int(7 + (13 - 7) * (y / height))
        g = int(11 + (22 - 11) * (y / height))
        b = int(22 + (38 - 22) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Üst neon çizgi (Zümrüt Yeşili -> Camgöbeği -> Mavi)
    for x in range(width):
        ratio = x / width
        cr = int(16 * (1 - ratio) + 14 * ratio)
        cg = int(185 * (1 - ratio) + 165 * ratio)
        cb = int(129 * (1 - ratio) + 233 * ratio)
        draw.line([(x, 0), (x, 3)], fill=(cr, cg, cb))

    # Alt zemin hafif dekoratif radar/piyasa çizgileri (çok hafif saydam)
    chart_pts = [
        (0, 1030), (90, 1010), (180, 1025), (270, 995), (360, 1015),
        (450, 975), (540, 1005), (630, 960), (720, 985), (810, 950),
        (900, 970), (990, 945), (1080, 930)
    ]
    for i in range(len(chart_pts) - 1):
        draw.line([chart_pts[i], chart_pts[i+1]], fill=(18, 30, 52), width=2)

    # Font tanımları
    f_brand_tag = _load_font(12, bold=True)
    f_header = _load_font(34, bold=True)
    f_date = _load_font(15, bold=True)
    f_status = _load_font(12, bold=False)
    f_card_num = _load_font(13, bold=True)
    f_card_title = _load_font(15, bold=True)
    f_card_text = _load_font(14, bold=False)
    f_footer_note = _load_font(12, bold=False)
    f_footer_social = _load_font(13, bold=True)
    f_footer_brand = _load_font(14, bold=True)

    # 2. Üst Başlık & Tarih Alanı
    # Sol Üst Marka Rozeti
    draw.rounded_rectangle([(40, 24), (320, 52)], radius=6, fill=(12, 33, 48), outline=(14, 165, 233), width=1)
    draw.text((54, 30), "📡 FAİZ RADARI  |  ORAN İSTİHBARATI", font=f_brand_tag, fill=(56, 189, 248))

    # Ana Başlık
    clean_title = title.upper()
    draw.text((40, 62), f"📊 {clean_title}", font=f_header, fill=(255, 255, 255))

    # Sağ Üst Tarih & Canlı Durum Rozeti
    today_str = datetime.now().strftime("%d %B %Y").upper()
    months_tr = {
        "JANUARY": "OCAK", "FEBRUARY": "ŞUBAT", "MARCH": "MART", "APRIL": "NİSAN",
        "MAY": "MAYIS", "JUNE": "HAZİRAN", "JULY": "TEMMUZ", "AUGUST": "AĞUSTOS",
        "SEPTEMBER": "EYLÜL", "OCTOBER": "EKİM", "NOVEMBER": "KASIM", "DECEMBER": "ARALIK"
    }
    for en_m, tr_m in months_tr.items():
        today_str = today_str.replace(en_m, tr_m)

    date_label = f"📅 {today_str} • 11:00"
    bbox_date = draw.textbbox((0, 0), date_label, font=f_date)
    dw = bbox_date[2] - bbox_date[0]
    draw.rounded_rectangle([(width - 40 - dw - 24, 28), (width - 40, 60)], radius=6, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
    draw.text((width - 40 - dw - 12, 35), date_label, font=f_date, fill=(226, 232, 240))
    draw.text((width - 195, 70), "🟢 Canlı Piyasa Analizi", font=f_status, fill=(52, 211, 153))

    # İnce Üst Ayırıcı Çizgi
    draw.line([(40, 118), (width - 40, 118)], fill=(30, 41, 59), width=1)

    # 3. Kategori Temaları (Her karta özgü kurumsal renk paleti)
    card_themes = [
        {"color": (16, 185, 129), "bg": (6, 78, 59)},    # 01 Mevduat (Zümrüt Yeşili)
        {"color": (56, 189, 248), "bg": (12, 74, 110)},  # 02 İhtiyaç (Gökyüzü Mavisi)
        {"color": (251, 146, 60), "bg": (124, 45, 18)},  # 03 Konut (Sıcak Turuncu)
        {"color": (167, 139, 250), "bg": (76, 29, 149)}, # 04 Taşıt (Asil Mor)
        {"color": (250, 204, 21), "bg": (113, 63, 18)},  # 05 %0 Faiz (Altın Sarısı)
        {"color": (45, 212, 191), "bg": (19, 78, 74)},   # 06 Döviz (Teal)
        {"color": (251, 191, 36), "bg": (120, 53, 15)},  # 07 Altın / Emtia (Kehribar)
        {"color": (96, 165, 250), "bg": (30, 58, 138)},  # 08 Döviz Makası (Mavi)
        {"color": (244, 63, 94), "bg": (136, 19, 55)},   # 09 TCMB Politika (Mercan Kırmızı)
        {"color": (129, 140, 248), "bg": (49, 46, 129)}, # 10 Kredi Kartı (İndigo)
    ]

    # Metin kaydırma yardımcısı
    def _wrap_text(text: str, font, max_w: int) -> List[str]:
        words = text.split()
        res_lines = []
        cur_words = []
        for w in words:
            test_line = " ".join(cur_words + [w])
            bb = draw.textbbox((0, 0), test_line, font=font)
            if (bb[2] - bb[0]) <= max_w:
                cur_words.append(w)
            else:
                if cur_words:
                    res_lines.append(" ".join(cur_words))
                    cur_words = [w]
                else:
                    res_lines.append(w)
        if cur_words:
            res_lines.append(" ".join(cur_words))
        return res_lines

    # 4. 10 Maddelik Gösterge Kartları (2 Sütun x 5 Satır)
    y_start = 136
    card_w = 485
    card_h = 148
    gap_y = 14

    for idx, it in enumerate(items[:10]):
        col = 0 if idx < 5 else 1
        row = idx if idx < 5 else idx - 5
        x = 40 if col == 0 else 555
        y = y_start + (row * (card_h + gap_y))

        theme = card_themes[idx % len(card_themes)]
        color_accent = theme["color"]
        bg_accent = theme["bg"]

        # Kart arka planı (Koyu camgöbeği/lacivert panel)
        draw.rounded_rectangle([(x, y), (x + card_w, y + card_h)], radius=12, fill=(13, 21, 37), outline=(30, 45, 69), width=1)

        # Kartın solundaki renkli dikey vurgu şeridi
        draw.rounded_rectangle([(x, y + 8), (x + 5, y + card_h - 8)], radius=2, fill=color_accent)

        # Başlık ve detay ayrımı
        if ": " in it:
            item_cat, item_detail = it.split(": ", 1)
        else:
            item_cat, item_detail = f"Madde {idx+1}", it

        # Numara Rozeti (örn: 01, 02)
        num_str = f"{idx+1:02d}"
        draw.rounded_rectangle([(x + 16, y + 12), (x + 48, y + 36)], radius=6, fill=bg_accent, outline=color_accent, width=1)
        draw.text((x + 23, y + 16), num_str, font=f_card_num, fill=color_accent)

        # Kart Başlığı
        draw.text((x + 56, y + 15), item_cat.upper(), font=f_card_title, fill=(255, 255, 255))

        # Kart İçerik Metni (Maksimum 425 piksele satır kaydırılır)
        lines = _wrap_text(item_detail, f_card_text, card_w - 36)
        text_y = y + 46
        for l in lines[:4]:  # En fazla 4 satır sığdır
            draw.text((x + 18, text_y), l, font=f_card_text, fill=(218, 226, 236))
            text_y += 22

    # 5. Alt Bilgi Alanı (Footer)
    footer_y = 964
    draw.line([(40, footer_y), (width - 40, footer_y)], fill=(30, 41, 59), width=1)

    draw.text(
        (40, footer_y + 12),
        "⚠️ Veriler bankaların ve kurumların kamuya açık kaynaklarından derlenmiş olup bilgilendirme amaçlıdır. Yatırım tavsiyesi içermez.",
        font=f_footer_note,
        fill=(100, 116, 139)
    )
    draw.text(
        (40, footer_y + 36),
        "🔔 Canlı Hesaplama & Takip: Telegram @faizradari  •  X: @faizradari  •  WhatsApp Kanalı",
        font=f_footer_social,
        fill=(148, 163, 184)
    )

    # Sağ Alt Kurumsal Rozet
    badge_w = 210
    badge_h = 44
    bx = width - 40 - badge_w
    by = footer_y + 18
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=8, fill=(15, 23, 42), outline=(16, 185, 129), width=1)
    draw.text((bx + 18, by + 12), "⚡ FAİZ RADARI CANLI", font=f_footer_brand, fill=(255, 255, 255))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_weekly_recap_image(
    recap_data: dict,
    output_path: str = "D:/faiz-radari/latest_weekly_recap.png",
) -> str:
    """
    Pazar akşamları saat 19:00'da yayınlanan 1080x1080 'HAFTANIN FİNANS KARNESİ' özel infografiği.
    Haftanın mevduat şampiyonunu, en uygun kredisini, altın/döviz kapanışlarını ve yeni haftanın ajandasını sunar.
    """
    width, height = 1080, 1080
    img = Image.new("RGB", (width, height), color=(8, 13, 24))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(9 + (15 - 9) * (y / height))
        g = int(14 + (24 - 14) * (y / height))
        b = int(28 + (42 - 28) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    for x in range(width):
        ratio = x / width
        cr = int(245 * (1 - ratio) + 16 * ratio)
        cg = int(158 * (1 - ratio) + 185 * ratio)
        cb = int(11 * (1 - ratio) + 129 * ratio)
        draw.line([(x, 0), (x, 4)], fill=(cr, cg, cb))

    f_tag = _load_font(13, bold=True)
    f_title = _load_font(34, bold=True)
    f_date = _load_font(16, bold=True)
    f_card_h = _load_font(18, bold=True)
    f_card_sub = _load_font(21, bold=True)
    f_body = _load_font(15, bold=False)
    f_footer = _load_font(13, bold=False)
    f_brand = _load_font(14, bold=True)

    draw.rounded_rectangle([(40, 26), (360, 56)], radius=6, fill=(45, 26, 12), outline=(245, 158, 11), width=1)
    draw.text((54, 33), "🏆 PAZAR ÖZEL  |  HAFTALIK PİYASA KARNESİ", font=f_tag, fill=(251, 191, 36))
    draw.text((40, 68), "HAFTANIN FİNANS & FAİZ KARNESİ", font=f_title, fill=(255, 255, 255))

    today_str = datetime.now().strftime("%d %B %Y").upper()
    months_tr = {
        "JANUARY": "OCAK", "FEBRUARY": "ŞUBAT", "MARCH": "MART", "APRIL": "NİSAN",
        "MAY": "MAYIS", "JUNE": "HAZİRAN", "JULY": "TEMMUZ", "AUGUST": "AĞUSTOS",
        "SEPTEMBER": "EYLÜL", "OCTOBER": "EKİM", "NOVEMBER": "KASIM", "DECEMBER": "ARALIK"
    }
    for en_m, tr_m in months_tr.items():
        today_str = today_str.replace(en_m, tr_m)

    draw.text((width - 270, 78), f"📅 {today_str}", font=f_date, fill=(148, 163, 184))
    draw.line([(40, 122), (width - 40, 122)], fill=(30, 41, 59), width=1)

    cards = [
        {
            "box": [(40, 140), (525, 520)],
            "color": (16, 185, 129),
            "bg": (6, 78, 59),
            "tag": "💰 HAFTANIN MEVDUAT LİDERİ",
            "val": recap_data.get("best_dep_bank", "ON Dijital (%51.0)"),
            "lines": [
                f"• 500.000 TL Anapara 32 Gün Getirisi: +{recap_data.get('dep_net', '20.121 TL')}",
                "• Hoş geldin faizinde rekabet tepe noktasında seyretti.",
                f"• Yeni Müşteri Fırsatı: {recap_data.get('zero_interest', '50.000 TL sıfır faizli nakit avans.')}"
            ]
        },
        {
            "box": [(555, 140), (1040, 520)],
            "color": (56, 189, 248),
            "bg": (12, 74, 110),
            "tag": "💳 HAFTANIN EN UYGUN KREDİSİ",
            "val": recap_data.get("best_loan_bank", "DenizBank (%2.89)"),
            "lines": [
                f"• 100.000 TL 12 Ay Taksit: {recap_data.get('loan_installment', '10.506 TL')}",
                f"• Toplam Geri Ödeme: {recap_data.get('loan_total', '126.641 TL')}",
                f"• Konut Kredisi Lideri: {recap_data.get('konut_best', 'VakıfBank (%2.84) ile 58.843 TL taksit.')}"
            ]
        },
        {
            "box": [(40, 540), (525, 930)],
            "color": (251, 191, 36),
            "bg": (120, 53, 15),
            "tag": "📈 PİYASA & EMTİA HAFTALIK DURUM",
            "val": f"Gram Altın: {recap_data.get('gold_price', '6.658 ₺')}",
            "lines": [
                f"• Dolar/TL Kapanış: {recap_data.get('usd_price', '50.19 ₺')} seviyesinde.",
                f"• Euro/TL Kapanış: {recap_data.get('eur_price', '56.29 ₺')} seviyesinde.",
                f"• En Dar Banka Döviz Makası: {recap_data.get('best_spread', 'Albaraka Türk (0.72 TL)')}"
            ]
        },
        {
            "box": [(555, 540), (1040, 930)],
            "color": (168, 85, 247),
            "bg": (88, 28, 135),
            "tag": "📅 YENİ HAFTADA RADARDA NE VAR?",
            "val": "TCMB & Enflasyon Dinamikleri",
            "lines": [
                "• TCMB Politika Faizi (%50,00) ve haftalık repo likiditesi.",
                "• Bankaların yeni müşteri sıfır faiz kontenjan güncellemeleri.",
                "• Piyasa açılışıyla birlikte güncel makas aralıkları takibi."
            ]
        }
    ]

    for c in cards:
        x1, y1 = c["box"][0]
        x2, y2 = c["box"][1]
        draw.rounded_rectangle([c["box"][0], c["box"][1]], radius=14, fill=(13, 21, 37), outline=(30, 45, 69), width=1)
        draw.rounded_rectangle([(x1, y1 + 10), (x1 + 6, y2 - 10)], radius=3, fill=c["color"])
        draw.text((x1 + 22, y1 + 20), c["tag"], font=f_card_h, fill=c["color"])
        draw.text((x1 + 22, y1 + 52), c["val"], font=f_card_sub, fill=(255, 255, 255))
        draw.line([(x1 + 22, y1 + 90), (x2 - 22, y1 + 90)], fill=(30, 45, 69), width=1)

        text_y = y1 + 108
        for line in c["lines"]:
            draw.text((x1 + 22, text_y), line, font=f_body, fill=(226, 232, 240))
            text_y += 34

    footer_y = 964
    draw.line([(40, footer_y), (width - 40, footer_y)], fill=(30, 41, 59), width=1)
    draw.text(
        (40, footer_y + 12),
        "⚠️ Veriler piyasa ve banka kaynaklarından derlenmiş olup bilgilendirme amaçlıdır. Yatırım tavsiyesi değildir.",
        font=f_footer,
        fill=(100, 116, 139)
    )
    draw.text(
        (40, footer_y + 36),
        "🔔 Canlı Hesaplama & Takip: Telegram @faizradari  •  X: @faizradari  •  WhatsApp Kanalı",
        font=f_tag,
        fill=(148, 163, 184)
    )

    badge_w = 230
    bx = width - 40 - badge_w
    by = footer_y + 16
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + 46)], radius=8, fill=(15, 23, 42), outline=(245, 158, 11), width=1)
    draw.text((bx + 16, by + 13), "⚡ FAİZ RADARI PAZAR", font=f_brand, fill=(251, 191, 36))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_breaking_news_image(
    headline: str,
    details: str,
    category: str = "TCMB FAİZ KARARI",
    output_path: str = "D:/faiz-radari/latest_breaking_news.png",
    impact_note: str = "",
    source: str = "",
    tickers: Dict[str, str] = None,
    question: str = "",
) -> str:
    """
    TCMB faiz kararı, enflasyon açıklaması, altın/kur hareketi veya bankacılık düzenlemeleri gibi
    kritik piyasa anlarında paylaşılan 1080x1080 'SON DAKİKA & PİYASA ETKİSİ' infografiği.
    Sıfır tofu (emoji kutucuğu yok), canlı kur şeridi ve Faiz Radarı Cep Etkisi kutusu içerir.
    """
    width, height = 1080, 1080
    img = Image.new("RGB", (width, height), color=(10, 10, 18))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(22 + (10 - 22) * (y / height))
        g = int(9 + (12 - 9) * (y / height))
        b = int(16 + (26 - 16) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Üst kırmızı alarm şeridi
    draw.rectangle([(0, 0), (width, 10)], fill=(239, 68, 68))

    f_top_alert = _load_font(18, bold=True)
    f_cat = _load_font(15, bold=True)
    f_headline = _load_font(34, bold=True)
    f_sec_title = _load_font(17, bold=True)
    f_body = _load_font(20, bold=False)
    f_impact = _load_font(20, bold=True)
    f_ticker_lbl = _load_font(13, bold=True)
    f_ticker_val = _load_font(21, bold=True)
    f_q = _load_font(17, bold=True)
    f_footer = _load_font(13, bold=False)
    f_brand = _load_font(15, bold=True)

    # Üst Son Dakika Barı
    draw.rounded_rectangle([(40, 32), (width - 40, 88)], radius=10, fill=(127, 29, 29), outline=(239, 68, 68), width=2)
    draw.ellipse([(58, 52), (74, 68)], fill=(255, 255, 255))
    draw.text((86, 48), "SON DAKİKA  |  FAİZ RADARI EKONOMİ MASASI", font=f_top_alert, fill=(255, 255, 255))

    today_str = datetime.now().strftime("%d.%m.%Y • %H:%M")
    t_bb = draw.textbbox((0, 0), today_str, font=f_cat)
    draw.text((width - 60 - (t_bb[2] - t_bb[0]), 50), today_str, font=f_cat, fill=(254, 202, 202))

    # Kategori + Kaynak Rozeti (Dinamik genişlik)
    cat_label = category.upper()
    if source:
        cat_label = f"{cat_label}  •  KAYNAK: {source.upper()}"
    cat_bb = draw.textbbox((0, 0), cat_label, font=f_cat)
    cat_w = (cat_bb[2] - cat_bb[0]) + 36
    draw.rounded_rectangle([(40, 108), (40 + cat_w, 146)], radius=8, fill=(30, 41, 59), outline=(245, 158, 11), width=1)
    draw.text((58, 117), cat_label, font=f_cat, fill=(251, 191, 36))

    def _wrap(text: str, font, max_w: int) -> List[str]:
        words = text.split()
        lines = []
        cur = []
        for w in words:
            test = " ".join(cur + [w])
            bb = draw.textbbox((0, 0), test, font=font)
            if (bb[2] - bb[0]) <= max_w:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                    cur = [w]
                else:
                    lines.append(w)
        if cur:
            lines.append(" ".join(cur))
        return lines

    # Ana Manşet
    h_lines = _wrap(headline, f_headline, width - 90)[:3]
    h_y = 164
    for hl in h_lines:
        draw.text((44, h_y), hl, font=f_headline, fill=(255, 255, 255))
        h_y += 44

    # 1. Kutu: Haberin Özeti
    c1_y = max(h_y + 16, 304)
    d_lines = _wrap(details, f_body, width - 140)[:5]
    c1_h = max(165, 76 + len(d_lines) * 30 + 18)
    draw.rounded_rectangle([(40, c1_y), (width - 40, c1_y + c1_h)], radius=14, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
    draw.rounded_rectangle([(40, c1_y + 12), (46, c1_y + c1_h - 12)], radius=3, fill=(239, 68, 68))

    draw.text((68, c1_y + 18), "HABERİN DETAYI & GELİŞME ÖZETİ", font=f_sec_title, fill=(248, 113, 113))
    draw.line([(68, c1_y + 48), (width - 68, c1_y + 48)], fill=(30, 41, 59), width=1)

    det_y = c1_y + 62
    for dl in d_lines:
        draw.text((68, det_y), dl, font=f_body, fill=(241, 245, 249))
        det_y += 30

    # 2. Kutu: Faiz Radarı Piyasa & Cep Etkisi
    cur_y = c1_y + c1_h + 18
    if impact_note:
        imp_lines = _wrap(impact_note, f_impact, width - 140)[:4]
        c2_h = max(150, 74 + len(imp_lines) * 30 + 16)
        draw.rounded_rectangle([(40, cur_y), (width - 40, cur_y + c2_h)], radius=14, fill=(20, 30, 26), outline=(16, 185, 129), width=2)
        draw.rounded_rectangle([(40, cur_y + 12), (46, cur_y + c2_h - 12)], radius=3, fill=(16, 185, 129))
        draw.text((68, cur_y + 18), "FAİZ RADARI ANALİZİ  |  CEBİNİZE & PİYASAYA ETKİSİ", font=f_sec_title, fill=(52, 211, 153))
        draw.line([(68, cur_y + 48), (width - 68, cur_y + 48)], fill=(30, 58, 47), width=1)

        iy = cur_y + 62
        for il in imp_lines:
            draw.text((68, iy), il, font=f_impact, fill=(236, 253, 245))
            iy += 30
        cur_y += c2_h + 18

    # 3. Canlı Piyasa Göstergeleri Şeridi (Dolar, Euro, Gram Altın)
    if tickers:
        strip_y = min(cur_y, 795)
        strip_h = 82
        box_w = (width - 80 - 24) // 3
        items_t = [
            ("DOLAR / TL", str(tickers.get("USD", "—")), (56, 189, 248)),
            ("EURO / TL", str(tickers.get("EUR", "—")), (167, 139, 250)),
            ("GRAM ALTIN", str(tickers.get("ALTIN", "—")), (251, 191, 36)),
        ]
        for idx, (tlbl, tval, tcol) in enumerate(items_t):
            bx = 40 + idx * (box_w + 12)
            draw.rounded_rectangle([(bx, strip_y), (bx + box_w, strip_y + strip_h)], radius=12, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
            draw.text((bx + 20, strip_y + 14), tlbl, font=f_ticker_lbl, fill=(148, 163, 184))
            draw.text((bx + 20, strip_y + 38), tval, font=f_ticker_val, fill=tcol)
        cur_y = strip_y + strip_h + 16

    # 4. Etkileşim / Soru Şeridi
    if question and cur_y <= 905:
        draw.rounded_rectangle([(40, 895), (width - 40, 948)], radius=10, fill=(30, 27, 75), outline=(99, 102, 241), width=1)
        q_short = question if len(question) <= 82 else question[:79] + "..."
        draw.text((60, 911), f"SİZCE: {q_short}", font=f_q, fill=(224, 231, 255))

    # Alt Bilgi & Marka Rozeti
    footer_y = 964
    draw.line([(40, footer_y), (width - 40, footer_y)], fill=(30, 41, 59), width=1)
    draw.text(
        (40, footer_y + 14),
        "Resmi kurum ve ekonomi basını verilerinden derlenmiştir. Yatırım tavsiyesi niteliği taşımaz.",
        font=f_footer,
        fill=(100, 116, 139),
    )
    draw.text(
        (40, footer_y + 38),
        "Anlık Bildirim & Takip: Telegram @faizradari  •  X: @faizradari  •  Instagram: @faizradari",
        font=_load_font(13, bold=True),
        fill=(148, 163, 184),
    )

    badge_w = 230
    bx = width - 40 - badge_w
    by = footer_y + 16
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + 46)], radius=8, fill=(15, 23, 42), outline=(239, 68, 68), width=1)
    draw.text((bx + 24, by + 13), "FAİZ RADARI CANLI", font=f_brand, fill=(255, 255, 255))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def render_viral_insight_image(
    tag: str,
    headline: str,
    big_metric_label: str,
    big_metric_value: str,
    rows: List[Dict],
    question: str,
    output_path: str = "D:/faiz-radari/latest_insight.png",
) -> str:
    """
    Telegram, X ve WhatsApp için yüksek etkileşimli, sade, dev tipografili
    1080x1080 'Günün Cep Hesabı / Finans Analizi' infografiği üretir.
    """
    w, h = 1080, 1080
    img = Image.new("RGB", (w, h), color=(8, 13, 26))
    draw = ImageDraw.Draw(img)

    # 1. Derin kurumsal lacivert degrade
    for y in range(h):
        r = int(8 + (15 - 8) * (y / h))
        g = int(13 + (24 - 13) * (y / h))
        b = int(26 + (46 - 26) * (y / h))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Üst neon şerit
    for x in range(w):
        ratio = x / w
        cr = int(16 * (1 - ratio) + 56 * ratio)
        cg = int(185 * (1 - ratio) + 189 * ratio)
        cb = int(129 * (1 - ratio) + 248 * ratio)
        draw.line([(x, 0), (x, 6)], fill=(cr, cg, cb))

    f_tag = _load_font(18, bold=True)
    f_date = _load_font(17, bold=True)
    f_head = _load_font(44, bold=True)
    f_metric_lbl = _load_font(20, bold=True)
    f_metric_val = _load_font(56, bold=True)
    f_row_t = _load_font(26, bold=True)
    f_row_s = _load_font(19, bold=False)
    f_row_v = _load_font(28, bold=True)
    f_q = _load_font(22, bold=True)
    f_foot = _load_font(16, bold=True)

    # Üst rozet ve tarih
    draw.rounded_rectangle([(48, 34), (440, 76)], radius=10, fill=(14, 30, 56), outline=(56, 189, 248), width=2)
    draw.text((66, 44), f"● {tag.upper()}", font=f_tag, fill=(56, 189, 248))

    today_s = datetime.now().strftime("%d.%m.%Y")
    draw.rounded_rectangle([(w - 265, 34), (w - 48, 76)], radius=10, fill=(20, 32, 54), outline=(51, 65, 85), width=1)
    date_txt = f"CANLI  •  {today_s}"
    dbb = draw.textbbox((0, 0), date_txt, font=f_date)
    draw.text(((w - 265 + w - 48) // 2 - (dbb[2] - dbb[0]) // 2, 44), date_txt, font=f_date, fill=(203, 213, 225))

    # Ana Başlık (2 satıra kadar otomatik)
    words = headline.split()
    h_lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        bb = draw.textbbox((0, 0), test, font=f_head)
        if (bb[2] - bb[0]) <= w - 96:
            cur.append(word)
        else:
            if cur:
                h_lines.append(" ".join(cur))
                cur = [word]
            else:
                h_lines.append(word)
    if cur:
        h_lines.append(" ".join(cur))

    hy = 100
    for hl in h_lines[:2]:
        draw.text((48, hy), hl, font=f_head, fill=(255, 255, 255))
        hy += 56

    # Dev Vurgu Kutusu (Büyük TL Farkı / Kazancı — otomatik genişlik uyumlu)
    box_y = max(hy + 14, 226)
    draw.rounded_rectangle([(48, box_y), (w - 48, box_y + 138)], radius=18, fill=(7, 46, 39), outline=(16, 185, 129), width=2)
    draw.text((76, box_y + 18), big_metric_label.upper(), font=f_metric_lbl, fill=(167, 243, 208))
    mv_font = f_metric_val
    for sz in (54, 48, 42, 36):
        cand = _load_font(sz, bold=True)
        bb_m = draw.textbbox((0, 0), big_metric_value, font=cand)
        if (bb_m[2] - bb_m[0]) <= w - 152:
            mv_font = cand
            break
    draw.text((76, box_y + 56), big_metric_value, font=mv_font, fill=(250, 204, 21))

    # Karşılaştırma Satırları (4 satır geniş okunaklı kartlar)
    ry = box_y + 162
    row_h = 118
    for idx, r_item in enumerate(rows[:4]):
        is_top = r_item.get("highlight", idx == 0)
        bg = (16, 34, 58) if is_top else (15, 23, 42)
        border = (56, 189, 248) if is_top else (30, 44, 70)
        draw.rounded_rectangle([(48, ry), (w - 48, ry + row_h - 14)], radius=14, fill=bg, outline=border, width=2 if is_top else 1)

        # Sol numara rozeti
        badge_bg = (16, 185, 129) if is_top else (30, 41, 59)
        badge_fg = (8, 22, 18) if is_top else (203, 213, 225)
        draw.rounded_rectangle([(68, ry + 26), (118, ry + 76)], radius=12, fill=badge_bg)
        rk = str(r_item.get("rank", idx + 1))
        rbb = draw.textbbox((0, 0), rk, font=f_row_t)
        draw.text((93 - (rbb[2] - rbb[0]) // 2, ry + 34), rk, font=f_row_t, fill=badge_fg)

        # Başlık & Alt Metin
        draw.text((138, ry + 20), str(r_item.get("title", "")), font=f_row_t, fill=(255, 255, 255))
        draw.text((138, ry + 58), str(r_item.get("sub", "")), font=f_row_s, fill=(148, 163, 184))

        # Sağ Büyük Değer
        val_s = str(r_item.get("value", ""))
        vbb = draw.textbbox((0, 0), val_s, font=f_row_v)
        vw = vbb[2] - vbb[0]
        val_col = (52, 211, 153) if is_top else (250, 204, 21)
        draw.text((w - 76 - vw, ry + 34), val_s, font=f_row_v, fill=val_col)
        ry += row_h

    # Alt Etkileşim Sorusu Kutusu
    qy = 924
    draw.rounded_rectangle([(48, qy), (w - 48, qy + 74)], radius=14, fill=(28, 25, 62), outline=(129, 140, 248), width=2)
    q_font = f_q
    for sz in (22, 20, 18):
        cand = _load_font(sz, bold=True)
        bb_q = draw.textbbox((0, 0), question, font=cand)
        if (bb_q[2] - bb_q[0]) <= w - 130:
            q_font = cand
            break
    qbb = draw.textbbox((0, 0), question, font=q_font)
    qw = qbb[2] - qbb[0]
    draw.text(((w - qw) // 2, qy + 23), question, font=q_font, fill=(248, 250, 252))

    # Footer
    draw.text((48, 1022), "Kamuya açık banka verilerinden derlenmiştir. Yatırım tavsiyesi değildir.", font=_load_font(14, bold=False), fill=(100, 116, 139))
    draw.text((w - 190, 1020), "@faizradari", font=f_foot, fill=(56, 189, 248))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _format_turkish_tts_text(text: str) -> str:
    """Finansal metni Türkçe spikerin (edge-tts) en doğal telaffuz edeceği hale getirir."""
    import re
    s = text.strip()
    # %2,89 -> yüzde 2 virgül 89 | %45,0 -> yüzde 45
    def _pct_repl(m):
        whole, frac = m.group(1), m.group(2)
        if not frac or frac in ("0", "00"):
            return f"yüzde {whole}"
        return f"yüzde {whole} virgül {frac}"
    s = re.sub(r"%\s*([0-9]+)(?:[,\.]([0-9]+))?", _pct_repl, s)
    s = s.replace("₺", " lira").replace("TL", "lira").replace("$", " dolar")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _probe_audio_duration(audio_path: str, ffmpeg_exe: str) -> float:
    import re
    import subprocess
    try:
        p = subprocess.run([ffmpeg_exe, "-i", str(audio_path)], capture_output=True, text=True)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def generate_turkish_voiceover(
    script_text: str,
    output_mp3: str = None,
    voice: str = "tr-TR-AhmetNeural",
    rate: str = "+12%",
) -> Tuple[str, float]:
    """
    Sıfır maliyetli Microsoft Neural Türkçe spiker (edge-tts) ile profesyonel
    ekonomi bülteni seslendirmesi (MP3) ve gerçek süresini (saniye) üretir.
    Hata durumunda sessizce ('', 0.0) döner; video üretimi fon müziğiyle devam eder.
    """
    if not script_text or not script_text.strip():
        return "", 0.0

    try:
        import asyncio
        import edge_tts
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

        base_dir = Path(__file__).parent
        if not output_mp3:
            output_mp3 = str(base_dir / "latest_voiceover.mp3")

        spoken_text = _format_turkish_tts_text(script_text)

        async def _synth():
            comm = edge_tts.Communicate(spoken_text, voice=voice, rate=rate, pitch="+0Hz")
            await comm.save(output_mp3)

        try:
            asyncio.run(_synth())
        except RuntimeError:
            # Eğer aktif bir event loop varsa yeni loop oluştur
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_synth())
            finally:
                loop.close()

        if Path(output_mp3).exists() and Path(output_mp3).stat().st_size > 1000:
            dur = _probe_audio_duration(output_mp3, ffmpeg_exe)
            print(f"[SESLİ SPİKER] Türkçe AI seslendirme üretildi ({voice}, {dur:.2f} sn).")
            return str(output_mp3), dur
    except Exception as e:
        print(f"[UYARI] Türkçe AI seslendirme üretilemedi, sadece fon müziğine geçiliyor: {e}")

    return "", 0.0


def render_animated_reel_video(
    tag: str,
    hook_line1: str,
    hook_line2: str,
    subtitle: str,
    rows: List[Dict],
    cta_text: str = "KAYDET — Lazım olduğunda elinin altında olsun!",
    question_text: str = "Sence hangi banka daha mantıklı? Yorumlara yaz!",
    voice_script: str = "",
    voice: str = "tr-TR-AhmetNeural",
    audio_path: str = None,
    output_video_path: str = None,
    output_cover_path: str = None,
    duration_sec: float = 8.0,
    fps: int = 15,
) -> Tuple[str, str]:
    """
    Instagram Reels ve YouTube Shorts için %100 NATIVE 1080x1920 SESLİ & ANİMASYONLU video üretir!
    - Sıfır maliyetli Türkçe AI Spiker (edge-tts) + kısık arka plan fon müziği (broadcast audio ducking).
    - Büyük, telefonda tek bakışta okunan 5 mobil kartın sırayla sağdan kayarak açılması.
    - Üstte canlı animasyonlu ses dalgası (equalizer) + konuşmayla senkronize alt yazı şeridi.
    - Ham RGB karelerini doğrudan FFmpeg pipe'ına akıtarak saniyeler içinde Full HD MP4 üretir.
    """
    import math
    import re
    import subprocess
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    base_dir = Path(__file__).parent
    if not audio_path or not Path(audio_path).exists():
        audio_path = str(base_dir / "bg_music_loop.mp3")
    if not output_video_path:
        output_video_path = str(base_dir / "latest_story_video.mp4")
    if not output_cover_path:
        output_cover_path = str(base_dir / "latest_vertical_story.png")

    # 0. Türkçe AI Spiker Seslendirmesi (varsa otomatik süre senkronizasyonu!)
    voice_mp3 = ""
    vo_dur = 0.0
    if voice_script:
        voice_mp3, vo_dur = generate_turkish_voiceover(
            script_text=voice_script,
            output_mp3=str(base_dir / "latest_voiceover.mp3"),
            voice=voice,
            rate="+16%",
        )
        if voice_mp3 and vo_dur > 1.0:
            duration_sec = max(9.0, min(24.0, vo_dur + 1.0))

    # Konuşma cümlelerini alt yazı dilimlerine böl (ses kapalı izleyenler için)
    sub_chunks: List[str] = []
    if voice_script:
        raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", voice_script.strip()) if s.strip()]
        sub_chunks = raw_sents[:4]

    W, H = 1080, 1920
    total_frames = int(duration_sec * fps)

    # Önceden hazır arka plan (her karede yeniden çizmek yerine tek seferde üretip kopyalarız - 10x hızlı!)
    bg_base = Image.new("RGB", (W, H), color=(7, 11, 22))
    bg_draw = ImageDraw.Draw(bg_base)
    for y in range(H):
        r = int(7 + (15 - 7) * (y / H))
        g = int(11 + (23 - 11) * (y / H))
        b = int(22 + (44 - 22) * (y / H))
        bg_draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Hafif dekoratif arka plan radar halkaları
    for r_rad in [240, 440, 640]:
        bg_draw.ellipse([(W // 2 - r_rad, 340 - r_rad), (W // 2 + r_rad, 340 + r_rad)], outline=(18, 30, 56), width=2)

    # Fontlar (Mobilde jilet gibi okunacak DEV boyutlar!)
    f_tag = _load_font(21, bold=True)
    f_audio_tag = _load_font(18, bold=True)
    f_hook1 = _load_font(60, bold=True)
    f_hook2 = _load_font(68, bold=True)
    f_sub = _load_font(26, bold=False)
    f_rank = _load_font(30, bold=True)
    f_bank = _load_font(34, bold=True)
    f_bank_sub = _load_font(22, bold=False)
    f_val = _load_font(40, bold=True)
    f_win_badge = _load_font(16, bold=True)
    f_cta = _load_font(26, bold=True)
    f_q = _load_font(23, bold=False)
    f_cap = _load_font(26, bold=True)
    f_brand = _load_font(20, bold=True)
    f_legal = _load_font(15, bold=False)

    # Otomatik taşma önleyici kanca font boyutları
    _tmp_d = ImageDraw.Draw(bg_base)
    for sz in (60, 52, 46, 40):
        cand = _load_font(sz, bold=True)
        bb = _tmp_d.textbbox((0, 0), hook_line1.upper(), font=cand)
        if (bb[2] - bb[0]) <= W - 140:
            f_hook1 = cand
            break
    for sz in (68, 58, 50, 44):
        cand = _load_font(sz, bold=True)
        bb = _tmp_d.textbbox((0, 0), hook_line2.upper(), font=cand)
        if (bb[2] - bb[0]) <= W - 140:
            f_hook2 = cand
            break
    for sz in (26, 23, 20):
        cand = _load_font(sz, bold=True)
        bb = _tmp_d.textbbox((0, 0), cta_text, font=cand)
        if (bb[2] - bb[0]) <= (W - 245):
            f_cta = cand
            break
    for sz in (23, 20, 18):
        cand = _load_font(sz, bold=False)
        bb = _tmp_d.textbbox((0, 0), question_text, font=cand)
        if (bb[2] - bb[0]) <= (W - 220):
            f_q = cand
            break

    def _wrap_caption(txt: str, font, max_w: int) -> List[str]:
        words = txt.split()
        lines, cur = [], []
        for w_tok in words:
            test = " ".join(cur + [w_tok])
            bb = _tmp_d.textbbox((0, 0), test, font=font)
            if (bb[2] - bb[0]) <= max_w:
                cur.append(w_tok)
            else:
                if cur:
                    lines.append(" ".join(cur))
                    cur = [w_tok]
                else:
                    lines.append(w_tok)
        if cur:
            lines.append(" ".join(cur))
        return lines[:3]

    def ease_out_cubic(p: float) -> float:
        p = max(0.0, min(1.0, p))
        return 1.0 - (1.0 - p) ** 3

    # FFmpeg sürecini başlat (Sesli spiker varsa broadcast audio ducking ile miksler!)
    if voice_mp3 and Path(voice_mp3).exists():
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-stream_loop", "-1",
            "-i", str(audio_path),
            "-i", str(voice_mp3),
            "-filter_complex",
            "[1:a]volume=0.14[bg];[2:a]adelay=250|250,volume=1.20[vo];[bg][vo]amix=inputs=2:duration=longest:dropout_transition=2:normalize=0[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-r", "30",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", f"{duration_sec:.2f}",
            str(output_video_path),
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-stream_loop", "-1",
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-r", "30",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-t", f"{duration_sec:.2f}",
            str(output_video_path),
        ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cta_start = max(3.8, duration_sec - 3.4)
    cover_frame_idx = min(total_frames - 4, int(fps * (cta_start + 1.2)))
    rows_to_draw = rows[:5]
    # 5 kartın açılış aralığını toplam konuşma süresine göre akıllıca dağıt
    card_interval = min(0.75, max(0.45, (cta_start - 1.2) / max(1, len(rows_to_draw))))

    try:
        for fi in range(total_frames):
            t = fi / float(fps)  # saniye
            frame = bg_base.copy()
            draw = ImageDraw.Draw(frame)

            # 1. Üst İlerleme Çubuğu
            prog_w = int(W * (fi / max(1, total_frames - 1)))
            draw.rectangle([(0, 0), (W, 8)], fill=(20, 32, 58))
            if prog_w > 0:
                draw.rectangle([(0, 0), (prog_w, 8)], fill=(16, 185, 129))

            # 2. Üst Canlı Rozet + Sağda Animasyonlu Ses Dalgası (Equalizer)
            pulse = 0.5 + 0.5 * math.sin(t * 5.0)
            dot_col = (int(16 + 40 * pulse), int(185 + 55 * pulse), int(129 + 40 * pulse))
            tag_right = 635 if voice_mp3 else 660
            draw.rounded_rectangle([(60, 165), (tag_right, 222)], radius=28, fill=(14, 28, 52), outline=(56, 189, 248), width=2)
            draw.ellipse([(82, 184), (102, 204)], fill=dot_col)
            draw.text((116, 179), tag.upper(), font=f_tag, fill=(226, 232, 240))

            if voice_mp3:
                # Canlı 5 çubuklu equalizer + "SESLİ" rozeti (izleyicinin sesi açmasını sağlar!)
                eq_x1, eq_x2 = 655, W - 125
                draw.rounded_rectangle([(eq_x1, 165), (eq_x2, 222)], radius=28, fill=(12, 42, 36), outline=(16, 185, 129), width=2)
                for bi in range(5):
                    bar_h = int(10 + 18 * (0.5 + 0.5 * math.sin(t * 11.0 + bi * 1.4)))
                    bx = eq_x1 + 24 + bi * 10
                    by_mid = 194
                    draw.rounded_rectangle([(bx, by_mid - bar_h // 2), (bx + 5, by_mid + bar_h // 2)], radius=2, fill=(52, 211, 153))
                draw.text((eq_x1 + 84, 182), "SESLİ ANALİZ", font=f_audio_tag, fill=(167, 243, 208))

            # 3. Dev Kanca Başlık (0.0s - 0.75s arası aşağıdan yumuşak kayarak açılır)
            h_prog = ease_out_cubic(t / 0.75)
            h_offset = int((1.0 - h_prog) * 70)
            draw.text((60, 255 + h_offset), hook_line1.upper(), font=f_hook1, fill=(255, 255, 255))
            draw.text((60, 330 + h_offset), hook_line2.upper(), font=f_hook2, fill=(250, 204, 21))

            # Alt başlık + neon ayraç çizgisi
            if t >= 0.35:
                s_prog = ease_out_cubic((t - 0.35) / 0.5)
                line_end = 60 + int((W - 180) * s_prog)
                draw.text((60, 422), subtitle, font=f_sub, fill=(148, 163, 184))
                draw.rectangle([(60, 470), (line_end, 475)], fill=(16, 185, 129))

            # 4. 5 Büyük Mobil Kart — Konuşma temposuyla senkronize sağdan kayarak girer
            card_left = 60
            card_right = W - 125
            base_y = 510
            card_h = 148
            card_gap = 20

            for idx, item in enumerate(rows_to_draw):
                appear_t = 0.75 + idx * card_interval
                if t < appear_t:
                    continue
                c_prog = ease_out_cubic((t - appear_t) / 0.45)
                slide_x = int((1.0 - c_prog) * 900)

                x1 = card_left + slide_x
                x2 = card_right + slide_x
                y1 = base_y + idx * (card_h + card_gap)
                y2 = y1 + card_h

                is_winner = item.get("highlight", idx == 0)
                if is_winner:
                    g_val = int(185 + 50 * pulse)
                    bg_c = (8, 48, 39)
                    border_c = (32, g_val, 145)
                    border_w = 3
                else:
                    bg_c = (15, 24, 46)
                    border_c = (38, 56, 88)
                    border_w = 2

                draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=22, fill=bg_c, outline=border_c, width=border_w)

                # Sıra Rozeti
                rk_bg = (250, 204, 21) if is_winner else (30, 44, 72)
                rk_fg = (10, 18, 28) if is_winner else (203, 213, 225)
                draw.rounded_rectangle([(x1 + 22, y1 + 36), (x1 + 88, y1 + 112)], radius=16, fill=rk_bg)
                rk_txt = str(item.get("rank", idx + 1))
                rbb = draw.textbbox((0, 0), rk_txt, font=f_rank)
                draw.text((x1 + 55 - (rbb[2] - rbb[0]) // 2, y1 + 54), rk_txt, font=f_rank, fill=rk_fg)

                # Banka / Kalem Başlığı
                title_y = y1 + (28 if is_winner else 34)
                draw.text((x1 + 112, title_y), str(item.get("title", "")), font=f_bank, fill=(255, 255, 255))

                if is_winner:
                    draw.rounded_rectangle([(x1 + 112, y1 + 74), (x1 + 275, y1 + 100)], radius=8, fill=(16, 185, 129))
                    draw.text((x1 + 124, y1 + 78), "EN AVANTAJLI", font=f_win_badge, fill=(8, 22, 16))
                    draw.text((x1 + 288, y1 + 74), str(item.get("sub", "")), font=f_bank_sub, fill=(167, 243, 208))
                else:
                    draw.text((x1 + 112, y1 + 82), str(item.get("sub", "")), font=f_bank_sub, fill=(148, 163, 184))

                # Sağ Büyük Oran / Değer
                val_s = str(item.get("value", ""))
                vbb = draw.textbbox((0, 0), val_s, font=f_val)
                vw = vbb[2] - vbb[0]
                v_col = (250, 204, 21) if is_winner else (56, 189, 248)
                draw.text((x2 - 28 - vw, y1 + 48), val_s, font=f_val, fill=v_col)

            # 5. Alt Alan: CTA açılmadan önce CANLI ALT YAZI, son 3.4 saniyede KAYDET & YORUM CTA KARTI!
            box_center = (84 + (W - 149)) // 2
            if t < cta_start and sub_chunks:
                # Konuşma alt yazısını zaman dilimine göre göster
                chunk_span = max(1.0, (cta_start - 0.25) / max(1, len(sub_chunks) - 1 if len(sub_chunks) > 1 else 1))
                c_idx = min(len(sub_chunks) - 1, max(0, int((t - 0.25) / chunk_span))) if t >= 0.25 else 0
                active_cap = sub_chunks[c_idx]
                cap_lines = _wrap_caption(active_cap, f_cap, (W - 125) - 60 - 56)

                cy_sub = 1392
                draw.rounded_rectangle([(60, cy_sub), (W - 125, cy_sub + 162)], radius=22, fill=(13, 22, 44), outline=(56, 189, 248), width=2)
                total_th = len(cap_lines) * 38
                ty = cy_sub + (162 - total_th) // 2
                for cl in cap_lines:
                    cbb_l = draw.textbbox((0, 0), cl, font=f_cap)
                    lw = cbb_l[2] - cbb_l[0]
                    draw.text((box_center - lw // 2, ty), cl, font=f_cap, fill=(248, 250, 252))
                    ty += 38
            elif t >= cta_start:
                cta_prog = ease_out_cubic((t - cta_start) / 0.6)
                cta_off = int((1.0 - cta_prog) * 180)
                cy = 1385 + cta_off

                draw.rounded_rectangle([(60, cy), (W - 125, cy + 178)], radius=24, fill=(16, 26, 50), outline=(250, 204, 21), width=2)
                draw.rounded_rectangle([(84, cy + 20), (W - 149, cy + 84)], radius=32, fill=(16, 185, 129))
                cbb = draw.textbbox((0, 0), cta_text, font=f_cta)
                cw = cbb[2] - cbb[0]
                draw.text((box_center - cw // 2, cy + 36), cta_text, font=f_cta, fill=(8, 22, 16))

                qbb = draw.textbbox((0, 0), question_text, font=f_q)
                qw = qbb[2] - qbb[0]
                draw.text((box_center - qw // 2, cy + 102), question_text, font=f_q, fill=(241, 245, 249))

                b_sig = "@faizradari  •  Güncel Banka & Piyasa Radarı"
                bsbb = draw.textbbox((0, 0), b_sig, font=f_brand)
                draw.text((box_center - (bsbb[2] - bsbb[0]) // 2, cy + 140), b_sig, font=f_brand, fill=(56, 189, 248))

            # Alt yasal bilgilendirme
            draw.text((60, 1590), "Kamuya açık banka verileridir. Yatırım tavsiyesi değildir.", font=f_legal, fill=(100, 116, 139))

            if fi == cover_frame_idx:
                Path(output_cover_path).parent.mkdir(parents=True, exist_ok=True)
                frame.save(output_cover_path, format="PNG", optimize=True)

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg animated reel encoding failed with exit code {proc.returncode}")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        raise

    return str(output_video_path), str(output_cover_path)


def render_vertical_story_image(
    square_image_path: str,
    title: str = "GÜNÜN FİNANS RAPORU",
    output_path: str = "D:/faiz-radari/latest_vertical_story.png",
) -> str:
    """
    Yedek dikey hikaye görseli (en-boy oranını bozmadan temiz 9:16 çerçeve, spam içermeyen sade CTA).
    """
    v_width, v_height = 1080, 1920
    canvas = Image.new("RGB", (v_width, v_height), color=(8, 13, 24))
    draw = ImageDraw.Draw(canvas)

    for y in range(v_height):
        r = int(7 + (14 - 7) * (y / v_height))
        g = int(11 + (22 - 11) * (y / v_height))
        b = int(22 + (40 - 22) * (y / v_height))
        draw.line([(0, y), (v_width, y)], fill=(r, g, b))

    for x in range(v_width):
        ratio = x / v_width
        cr = int(16 * (1 - ratio) + 14 * ratio)
        cg = int(185 * (1 - ratio) + 165 * ratio)
        cb = int(129 * (1 - ratio) + 233 * ratio)
        draw.line([(x, 0), (x, 6)], fill=(cr, cg, cb))

    f_top = _load_font(18, bold=True)
    f_main = _load_font(42, bold=True)
    f_sub = _load_font(22, bold=True)
    f_cta = _load_font(24, bold=True)
    f_brand = _load_font(20, bold=True)

    draw.rounded_rectangle([(60, 145), (520, 196)], radius=12, fill=(18, 28, 52), outline=(250, 204, 21), width=2)
    draw.text((80, 159), "GÜNCEL PİYASA VERİLERİ", font=f_top, fill=(250, 204, 21))

    draw.text((60, 220), title.upper(), font=f_main, fill=(255, 255, 255))
    draw.text((60, 286), "Bankaların en güncel karşılaştırmalı tablosu", font=f_sub, fill=(52, 211, 153))
    draw.line([(60, 336), (v_width - 60, 336)], fill=(30, 41, 59), width=2)

    # En-boy oranını KORUYARAK ölçekle (asla sıkıştırma/ezme yapma!)
    p = Path(square_image_path)
    bottom_of_img = 1320
    if p.exists():
        sq_img = Image.open(p).convert("RGBA")
        max_w, max_h = 980, 960
        scale = min(max_w / sq_img.width, max_h / sq_img.height)
        new_w = int(sq_img.width * scale)
        new_h = int(sq_img.height * scale)
        sq_resized = sq_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        pos_x = (v_width - new_w) // 2
        pos_y = 365 + (max_h - new_h) // 2
        bottom_of_img = pos_y + new_h

        draw.rounded_rectangle([(pos_x - 6, pos_y - 6), (pos_x + new_w + 6, pos_y + new_h + 6)], radius=18, fill=(15, 23, 42), outline=(30, 58, 95), width=2)
        canvas.paste(sq_resized, (pos_x, pos_y), sq_resized)

    # Temiz, spam içermeyen kaydetme/yorum CTA kartı
    card_y = max(bottom_of_img + 35, 1365)
    card_h = 165
    draw.rounded_rectangle([(60, card_y), (v_width - 60, card_y + card_h)], radius=18, fill=(13, 21, 37), outline=(16, 185, 129), width=2)
    draw.text((90, card_y + 28), "KAYDET — Karar vermeden önce lazım olur!", font=f_cta, fill=(52, 211, 153))
    draw.text((90, card_y + 76), "Sizce hangi banka daha avantajlı? Yorumlara yazın!", font=_load_font(20, bold=False), fill=(241, 245, 249))
    draw.text((90, card_y + 116), "@faizradari  •  Günlük Finans & Oran Takibi", font=f_brand, fill=(56, 189, 248))

    draw.text(
        (60, card_y + card_h + 24),
        "Kamuya açık banka verileridir. Yatırım tavsiyesi niteliği taşımaz.",
        font=_load_font(14, bold=False),
        fill=(100, 116, 139)
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return output_path


def render_vertical_story_video(
    v_image_path: str,
    audio_path: str = None,
    output_path: str = None,
    duration: int = 8
) -> str:
    """
    1080x1920 boyutundaki dikey hikaye görselini telifsiz fon müziğiyle
    birleştirerek TikTok ve Instagram Reels için tam uyumlu Full HD MP4 video üretir.
    """
    import subprocess
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    base_dir = Path(__file__).parent
    if not audio_path or not Path(audio_path).exists():
        audio_path = str(base_dir / "bg_music_loop.mp3")

    if not output_path:
        output_path = str(base_dir / "latest_story_video.mp4")

    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", str(v_image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-t", str(duration),
        str(output_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(output_path)
