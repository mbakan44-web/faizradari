from datetime import datetime
from pathlib import Path
from typing import Dict, List
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
        "Yıllık brüt mevduat faiz oranları üzerinden %10 stopaj vergisi düşülerek net ele geçecek kazanç hesaplanmıştır.",
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
    Bir banka faiz indirdiğinde otomatik üretilen FLAŞ FAİZ İNDİRİMİ ALARMI görseli.
    """
    width = 1200
    row_h = 90
    height = 280 + (len(alerts) * row_h) + 120

    img = Image.new("RGB", (width, height), color=(15, 10, 28))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (width, 110)], fill=(127, 29, 29))
    draw.rectangle([(0, 106), (width, 110)], fill=(250, 204, 21))

    draw.text((45, 22), "FLAŞ ALARM | BANKA FAİZ İNDİRİMİ YAKALANDI!", font=_load_font(32, bold=True), fill=(255, 255, 255))
    draw.text((45, 65), "FAİZ RADARI ANLIK ORAN DEĞİŞİM MONİTÖRÜ  •  t.me/faizradari", font=_load_font(19, bold=False), fill=(254, 202, 202))

    y = 140
    for alert in alerts:
        draw.rounded_rectangle([(40, y), (width - 40, y + row_h - 12)], radius=10, fill=(6, 58, 46), outline=(16, 185, 129), width=2)
        old_s = f"%{alert.old_rate:.2f}".replace(".", ",")
        new_s = f"%{alert.new_rate:.2f}".replace(".", ",")
        line1 = f"{alert.bank_name}  |  Eski Oran: {old_s}  -->  YENİ ORAN: {new_s}"
        line2 = (
            f"{format_tl(alert.principal)} ({alert.months} Ay) kredide toplam geri ödeme "
            f"{format_tl(alert.total_savings)} AZALDI! (Yeni Taksit: {format_tl(alert.new_offer.monthly_installment)})"
        )
        draw.text((65, y + 14), line1, font=_load_font(23, bold=True), fill=(250, 204, 21))
        draw.text((65, y + 46), line2, font=_load_font(18, bold=False), fill=(241, 245, 249))
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
