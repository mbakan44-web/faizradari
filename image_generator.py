from datetime import datetime
from pathlib import Path
from typing import Dict, List
from PIL import Image, ImageDraw, ImageFont
from calculator import LoanOffer, SpreadOffer, format_tl, format_price


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
    Kurumsal Bloomberg/Fintech tarzında yüksek çözünürlüklü Kredi Karşılaştırma Tablosu (PNG) üretir.
    En altında yasal sorumluluk reddi (disclaimer) yer alır.
    """
    width = 1280
    row_height = 68
    num_rows = len(offers)
    height = 380 + (num_rows * row_height) + 170

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
    draw.rectangle([(0, 107), (width, 110)], fill=(16, 185, 129))

    draw.rounded_rectangle([(40, 24), (98, 82)], radius=14, fill=(16, 185, 129))
    draw.text((55, 30), "%", font=_load_font(36, bold=True), fill=(11, 17, 32))
    draw.text((115, 22), "FAİZ RADARI", font=f_brand, fill=(248, 250, 252))
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
        f"{principal_str} İHTİYAÇ KREDİSİ — {months_val} AY VADE NET GERİ ÖDEME TABLOSU",
        font=f_title,
        fill=(255, 255, 255),
    )
    draw.text(
        (40, 240),
        "Tüm bankalar için %15 KKDF, %15 BSMV vergileri ve yasal dosya masrafı (tahsis ücreti) dahil net hesaplamadır.",
        font=_load_font(17, bold=False),
        fill=(148, 163, 184),
    )

    # 4. Tablo Sütun Başlıkları
    table_top = 280
    draw.rounded_rectangle([(40, table_top), (width - 40, table_top + 52)], radius=8, fill=(30, 41, 59))

    col_x = {
        "bank": 65,
        "rate": 430,
        "monthly": 620,
        "fee": 845,
        "total": 1035,
    }
    draw.text((col_x["bank"], table_top + 14), "BANKA", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["rate"], table_top + 14), "FAİZ ORANI", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["monthly"], table_top + 14), "AYLIK TAKSİT", font=f_th, fill=(203, 213, 225))
    draw.text((col_x["fee"], table_top + 14), "DOSYA MASRAFI", font=f_th, fill=(203, 213, 225))
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
    draw.rectangle([(0, 105), (width, 108)], fill=(245, 158, 11))  # Altın sarısı çizgi

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

    # Sol Panel Başlığı: DOLAR
    draw.rounded_rectangle([(left_x1, top_y), (left_x2, top_y + 50)], radius=8, fill=(6, 78, 59))
    draw.text((left_x1 + 20, top_y + 12), "[$] BANKALARDA DOLAR (USD) MAKAS TABLOSU", font=f_panel_title, fill=(167, 243, 208))

    # Sağ Panel Başlığı: GRAM ALTIN
    draw.rounded_rectangle([(right_x1, top_y), (right_x2, top_y + 50)], radius=8, fill=(120, 53, 15))
    draw.text((right_x1 + 20, top_y + 12), "[AU] BANKALARDA GRAM ALTIN MAKAS TABLOSU", font=f_panel_title, fill=(253, 230, 138))

    # Sütun Başlıkları Yardımcı Fonksiyonu
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
