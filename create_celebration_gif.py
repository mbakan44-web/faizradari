import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int, bold: bool = False):
    font_candidates = (
        [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    )
    for p in font_candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_star(draw, cx, cy, r_outer, r_inner, fill, points=5):
    coords = []
    angle_offset = -math.pi / 2
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        ang = angle_offset + i * math.pi / points
        coords.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(coords, fill=fill)

def generate_celebration_gif(output_path: str = "faiz_radari_1500_kutlama.gif", num_frames: int = 32):
    w, h = 720, 720
    frames = []

    # Tipografi - Net, okunaklı, kararlı ve dengeli font boyutları
    f_badge = get_font(16, bold=True)
    f_number = get_font(92, bold=True)
    f_title = get_font(28, bold=True)
    f_subtitle = get_font(18, bold=True)
    f_card_title = get_font(21, bold=True)
    f_desc = get_font(18, bold=False)
    f_brand = get_font(20, bold=True)

    # Konfeti parçacıkları - Metinleri kapatmayacak şekilde kenarlardan akar
    random.seed(99)
    confetti_list = []
    colors = [
        (251, 191, 36),   # Altın Sarısı
        (56, 189, 248),   # Camgöbeği Mavi
        (52, 211, 153),   # Zümrüt Yeşili
        (244, 63, 94),    # Gül Pembesi
        (250, 204, 21),   # Canlı Sarı
        (255, 255, 255),  # Beyaz
    ]
    for _ in range(50):
        # Kenarlara ağırlık ver
        is_side = random.random() < 0.75
        x_val = random.choice([random.randint(15, 110), random.randint(w - 110, w - 15)]) if is_side else random.randint(20, w - 20)
        confetti_list.append({
            "x": x_val,
            "y": random.uniform(0, h),
            "size": random.randint(5, 10),
            "speed": random.uniform(2.5, 5.5),
            "drift_speed": random.uniform(1.0, 2.5),
            "drift_phase": random.uniform(0, math.pi * 2),
            "color": random.choice(colors),
            "rot": random.uniform(0, 360),
            "rot_speed": random.uniform(8, 16),
            "type": random.choice(["rect", "circle", "spark"])
        })

    center_x = w // 2
    center_y = 190

    for frame_idx in range(num_frames):
        t = frame_idx / num_frames  # 0.0 to 1.0

        # Arka plan: Derin kurumsal lacivert (#090e21)
        img = Image.new("RGBA", (w, h), (9, 14, 33, 255))
        draw = ImageDraw.Draw(img)

        # 1. Arka Plan Dinamik Radar Halka ve Tarama Çizgisi
        radar_rings = [60, 130, 210, 280]
        for r_base in radar_rings:
            draw.ellipse(
                [center_x - r_base, center_y - r_base, center_x + r_base, center_y + r_base],
                outline=(24, 38, 70, 110),
                width=1
            )

        for p_idx in range(2):
            p_t = (t + p_idx / 2.0) % 1.0
            r_pulse = int(50 + p_t * 240)
            alpha_pulse = int(90 * (1.0 - p_t))
            draw.ellipse(
                [center_x - r_pulse, center_y - r_pulse, center_x + r_pulse, center_y + r_pulse],
                outline=(56, 189, 248, alpha_pulse),
                width=2
            )

        # 360 Derece Dönen Radar Işığı
        sweep_angle = t * 2 * math.pi
        sweep_len = 260
        sx = center_x + sweep_len * math.cos(sweep_angle)
        sy = center_y + sweep_len * math.sin(sweep_angle)
        draw.line([(center_x, center_y), (sx, sy)], fill=(56, 189, 248, 60), width=2)

        # 2. Konfeti Parçacıkları (Metin kutularının arkasında kalır)
        for c in confetti_list:
            cy = (c["y"] + frame_idx * c["speed"] * 7.0) % (h + 30) - 15
            cx = (c["x"] + math.sin(t * math.pi * 2 * c["drift_speed"] + c["drift_phase"]) * 18) % w
            c_color = c["color"] + (210,)
            rot_ang = (c["rot"] + frame_idx * c["rot_speed"]) * math.pi / 180.0
            s = c["size"]

            # Ana metin alanlarını temiz tut
            if 140 < cx < 580 and 50 < cy < 250:
                continue

            if c["type"] == "circle":
                draw.ellipse([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=c_color)
            elif c["type"] == "spark":
                draw_star(draw, cx, cy, s, s // 2.5, c_color, points=4)
            else:
                dx = math.cos(rot_ang) * s
                dy = math.sin(rot_ang) * (s * 0.5)
                draw.polygon([
                    (cx - dx, cy - dy),
                    (cx + dy, cy - dx),
                    (cx + dx, cy + dy),
                    (cx - dy, cy + dx)
                ], fill=c_color)

        # 3. Üst Rozet (Yukarıdaki boşluk kısıldı: y=20)
        badge_box = [center_x - 180, 20, center_x + 180, 56]
        draw.rounded_rectangle(badge_box, radius=18, fill=(16, 24, 48, 240), outline=(251, 191, 36, 230), width=2)
        draw_star(draw, badge_box[0] + 18, 38, 7, 3, (251, 191, 36))
        b_txt = "TELEGRAM KİLOMETRE TAŞI"
        bbb = draw.textbbox((0, 0), b_txt, font=f_badge)
        bw = bbb[2] - bbb[0]
        draw.text((center_x - bw // 2, 28), b_txt, font=f_badge, fill=(251, 191, 36))
        draw_star(draw, badge_box[2] - 18, 38, 7, 3, (251, 191, 36))

        # 4. Dev Sayı: 1.500+ (Tamamen stabil, titreşimsiz, net siyah konturlu)
        num_str = "1.500+"
        nbb = draw.textbbox((0, 0), num_str, font=f_number)
        nw = nbb[2] - nbb[0]
        nx = center_x - nw // 2
        ny = 66

        # Keskin siyah gölge
        for ox in range(-3, 4, 3):
            for oy in range(-3, 4, 3):
                if ox != 0 or oy != 0:
                    draw.text((nx + ox, ny + oy), num_str, font=f_number, fill=(0, 0, 0, 240))
        # Sabit Altın Sarısı
        draw.text((nx, ny), num_str, font=f_number, fill=(251, 191, 36))

        # 5. Başlıklar (Yüksek kontrast, stabil)
        head_text = "KİŞİLİK BÜYÜK BİR AİLE OLDUK!"
        hbb = draw.textbbox((0, 0), head_text, font=f_title)
        hw = hbb[2] - hbb[0]
        draw.text((center_x - hw // 2, 172), head_text, font=f_title, fill=(255, 255, 255))

        sub_text = "Katkılarınız, güveniniz ve desteğiniz için sonsuz teşekkürler!"
        sbb = draw.textbbox((0, 0), sub_text, font=f_subtitle)
        sw = sbb[2] - sbb[0]
        draw.text((center_x - sw // 2, 214), sub_text, font=f_subtitle, fill=(52, 211, 153))

        # 6. Bilgi Kartı (Sağ ve sol boşluğu kapatan, geniş ve dengeli tasarım)
        # Kart y=252'de başlar, y=596'ya kadar uzanır.
        card_box = [32, 252, w - 32, 596]
        draw.rounded_rectangle(card_box, radius=20, fill=(13, 21, 42, 250), outline=(56, 189, 248, 220), width=2)

        # Kart Başlığı
        draw_star(draw, card_box[0] + 32, card_box[1] + 30, 8, 3.5, (250, 204, 21))
        draw.text((card_box[0] + 50, card_box[1] + 20), "FAİZ RADARI'NDA BİRLİKTE NELER YAPTIK?", font=f_card_title, fill=(250, 204, 21))

        # 4 Madde - Sağa ve sola tam yayılan, doygun metinler
        bullets = [
            "Tüm bankaların mevduat & kredi oranlarını anlık radarımıza aldık.",
            "Masrafsız, en avantajlı finans fırsatlarını tarafsız sunduk.",
            "Dolar, altın ve makas analizleriyle paranızın değerini koruduk.",
            "1.500+ bilinçli tasarrufçu ile Türkiye'nin en şeffaf topluluğu olduk.",
        ]

        by = card_box[1] + 66
        for b_text in bullets:
            bcx = card_box[0] + 36
            bcy = by + 11
            # Yeşil onay rozeti
            draw.ellipse([bcx - 11, bcy - 11, bcx + 11, bcy + 11], fill=(16, 185, 129, 60), outline=(52, 211, 153, 240), width=2)
            draw.line([(bcx - 5, bcy), (bcx - 1, bcy + 4), (bcx + 5, bcy - 4)], fill=(255, 255, 255), width=2)

            # Stabil beyaz yazı
            draw.text((card_box[0] + 60, by), b_text, font=f_desc, fill=(241, 245, 249))
            by += 42

        # 7. Alt Marka Rozeti
        footer_box = [center_x - 220, 622, center_x + 220, 676]
        draw.rounded_rectangle(footer_box, radius=27, fill=(15, 23, 42, 255), outline=(52, 211, 153, 230), width=2)
        f_text = "Birlikte Daha Güçlüyüz: @faizradari"
        ftbb = draw.textbbox((0, 0), f_text, font=f_brand)
        ftw = ftbb[2] - ftbb[0]
        draw_star(draw, center_x - ftw // 2 - 18, 649, 7, 3, (52, 211, 153))
        draw.text((center_x - ftw // 2, 636), f_text, font=f_brand, fill=(255, 255, 255))
        draw_star(draw, center_x + ftw // 2 + 18, 649, 7, 3, (52, 211, 153))

        # Convert to RGB
        rgb_frame = img.convert("RGB")
        frames.append(rgb_frame)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        optimize=True
    )
    print(f"Mükemmel dengeli, stabil ve okunabilir GIF başarıyla üretildi: {output_path}")

if __name__ == "__main__":
    generate_celebration_gif()
