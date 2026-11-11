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
    w, h = 800, 800
    frames = []

    # Extra bold, large, legible fonts
    f_badge = get_font(21, bold=True)
    f_number = get_font(120, bold=True)
    f_thanks = get_font(36, bold=True)
    f_headline = get_font(44, bold=True)
    f_sub = get_font(24, bold=True)
    f_card_h = get_font(24, bold=True)
    f_card_text = get_font(23, bold=True)
    f_brand = get_font(24, bold=True)

    # Confetti setup - spawn on sides and top/bottom to frame the text without blocking letters
    random.seed(42)
    confetti_list = []
    colors = [
        (251, 191, 36),   # Gold
        (56, 189, 248),   # Cyan
        (52, 211, 153),   # Emerald
        (244, 63, 94),    # Rose
        (250, 204, 21),   # Yellow
        (255, 255, 255),  # White
    ]
    for _ in range(45):
        # Place mostly in outer edges (x < 140 or x > 660, or y < 90 or y > 680)
        is_side = random.random() < 0.8
        if is_side:
            x_val = random.choice([random.randint(15, 140), random.randint(w - 140, w - 15)])
        else:
            x_val = random.randint(15, w - 15)

        confetti_list.append({
            "x": x_val,
            "y": random.uniform(0, h),
            "size": random.randint(6, 13),
            "speed": random.uniform(2.5, 5.0),
            "drift_speed": random.uniform(1.0, 2.5),
            "drift_phase": random.uniform(0, math.pi * 2),
            "color": random.choice(colors),
            "rot": random.uniform(0, 360),
            "rot_speed": random.uniform(8, 16),
            "type": random.choice(["rect", "circle", "spark"])
        })

    center_x = w // 2

    for frame_idx in range(num_frames):
        t = frame_idx / num_frames  # 0.0 to 1.0

        # Base canvas: Pure solid deep dark navy background (#070d1e)
        img = Image.new("RGBA", (w, h), (7, 13, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Subtle Background Radar Sweep & Pulse (clean & calm)
        radar_center_y = 230
        for r_base in [100, 210, 320]:
            draw.ellipse(
                [center_x - r_base, radar_center_y - r_base, center_x + r_base, radar_center_y + r_base],
                outline=(22, 38, 70, 130),
                width=1
            )

        for p_idx in range(2):
            p_t = (t + p_idx / 2.0) % 1.0
            r_pulse = int(70 + p_t * 260)
            alpha_pulse = int(80 * (1.0 - p_t))
            draw.ellipse(
                [center_x - r_pulse, radar_center_y - r_pulse, center_x + r_pulse, radar_center_y + r_pulse],
                outline=(56, 189, 248, alpha_pulse),
                width=2
            )

        # 2. Confetti Particles (Framing the borders)
        for c in confetti_list:
            cy = (c["y"] + frame_idx * c["speed"] * 8.0) % (h + 30) - 15
            cx = (c["x"] + math.sin(t * math.pi * 2 * c["drift_speed"] + c["drift_phase"]) * 14) % w
            c_color = c["color"] + (210,)
            rot_ang = (c["rot"] + frame_idx * c["rot_speed"]) * math.pi / 180.0
            s = c["size"]

            # Skip drawing if right inside the sensitive text area
            if 150 < cx < 650 and 220 < cy < 370:
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

        # 3. Top Milestone Badge
        badge_box = [center_x - 225, 34, center_x + 225, 82]
        draw.rounded_rectangle(badge_box, radius=24, fill=(13, 22, 45, 255), outline=(250, 204, 21, 255), width=2)
        draw_star(draw, badge_box[0] + 24, 58, 9, 4, (250, 204, 21))
        badge_txt = "TELEGRAM'DA BÜYÜYORUZ"
        bbb = draw.textbbox((0, 0), badge_txt, font=f_badge)
        bw = bbb[2] - bbb[0]
        draw.text((center_x - bw // 2, 45), badge_txt, font=f_badge, fill=(250, 204, 21))
        draw_star(draw, badge_box[2] - 24, 58, 9, 4, (250, 204, 21))

        # 4. Ultra Bold Giant Number: 1.500+
        pulse = math.sin(t * 2 * math.pi)
        num_str = "1.500+"
        nbb = draw.textbbox((0, 0), num_str, font=f_number)
        nw = nbb[2] - nbb[0]
        nx = center_x - nw // 2
        ny = 92

        # Solid black outline for razor sharp separation
        for ox in range(-5, 6, 2):
            for oy in range(-5, 6, 2):
                if ox != 0 or oy != 0:
                    draw.text((nx + ox, ny + oy), num_str, font=f_number, fill=(0, 0, 0, 255))

        num_fill = (255, 235, 90) if pulse > 0.3 else (251, 191, 36)
        draw.text((nx, ny), num_str, font=f_number, fill=num_fill)

        # 5. Clean, High-Contrast Header Titles
        t_text = "TEŞEKKÜRLER!"
        tbb = draw.textbbox((0, 0), t_text, font=f_thanks)
        tw = tbb[2] - tbb[0]
        draw.text((center_x - tw // 2, 234), t_text, font=f_thanks, fill=(52, 211, 153))

        h_text = "1.500 KİŞİYİ GEÇTİK"
        hbb = draw.textbbox((0, 0), h_text, font=f_headline)
        hw = hbb[2] - hbb[0]
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((center_x - hw // 2 + dx, 280 + dy), h_text, font=f_headline, fill=(0, 0, 0, 255))
        draw.text((center_x - hw // 2, 280), h_text, font=f_headline, fill=(255, 255, 255))

        s_text = "Katkılarınız ve güveniniz için sonsuz teşekkürler!"
        sbb = draw.textbbox((0, 0), s_text, font=f_sub)
        sw = sbb[2] - sbb[0]
        draw.text((center_x - sw // 2, 338), s_text, font=f_sub, fill=(226, 232, 240))

        # 6. Ultra-Crisp Content Container
        card_box = [38, 385, w - 38, 680]
        border_glow = (56, 189, 248, int(210 + 45 * pulse))
        draw.rounded_rectangle(card_box, radius=24, fill=(12, 20, 42, 255), outline=border_glow, width=3)

        # Inner Header
        draw_star(draw, card_box[0] + 36, card_box[1] + 32, 10, 4.5, (250, 204, 21))
        c_title = "FAİZ RADARI TOPLULUĞU"
        draw.text((card_box[0] + 58, card_box[1] + 20), c_title, font=f_card_h, fill=(250, 204, 21))

        # 3 Big, Readable Feature Rows
        features = [
            "Bankaların Gizli & En Yüksek Faiz Oranları",
            "Kredi & Mevduatta Tarafsız Canlı Karşılaştırma",
            "Bilinçli Tasarrufun Türkiye'deki 1 Numaralı Radarı",
        ]

        row_y = card_box[1] + 75
        for feat_text in features:
            pill_box = [card_box[0] + 20, row_y, card_box[2] - 20, row_y + 54]
            draw.rounded_rectangle(pill_box, radius=14, fill=(19, 30, 60, 255), outline=(38, 56, 95, 255), width=1)
            
            # Badge icon circle
            icx = pill_box[0] + 30
            icy = row_y + 27
            draw.ellipse([icx - 14, icy - 14, icx + 14, icy + 14], fill=(16, 185, 129, 255))
            # Clean white checkmark
            draw.line([(icx - 6, icy), (icx - 2, icy + 5), (icx + 6, icy - 5)], fill=(255, 255, 255), width=3)

            # High contrast text
            draw.text((pill_box[0] + 58, row_y + 14), feat_text, font=f_card_text, fill=(255, 255, 255))
            row_y += 66

        # 7. Bottom Brand Footer Pill
        footer_box = [center_x - 245, 706, center_x + 245, 762]
        draw.rounded_rectangle(footer_box, radius=28, fill=(16, 185, 129, 255), outline=(52, 211, 153, 255), width=2)
        f_text = "Faiz Radarı Ailesi Büyüyor: @faizradari"
        ftbb = draw.textbbox((0, 0), f_text, font=f_brand)
        ftw = ftbb[2] - ftbb[0]
        draw.text((center_x - ftw // 2, 720), f_text, font=f_brand, fill=(10, 24, 18))

        # Convert to RGB
        rgb_frame = img.convert("RGB")
        frames.append(rgb_frame)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True
    )
    print(f"Büyük ve kusursuz okunabilir yeni GIF üretildi: {output_path}")

if __name__ == "__main__":
    generate_celebration_gif()
