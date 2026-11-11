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

def generate_celebration_gif(output_path: str = "faiz_radari_1500_kutlama.gif", num_frames: int = 36):
    w, h = 720, 720
    frames = []

    # Fonts
    f_badge = get_font(17, bold=True)
    f_number = get_font(84, bold=True)
    f_title = get_font(30, bold=True)
    f_subtitle = get_font(19, bold=True)
    f_desc = get_font(18, bold=False)
    f_card_title = get_font(21, bold=True)
    f_brand = get_font(21, bold=True)

    # Confetti setup
    random.seed(99)
    confetti_list = []
    colors = [
        (251, 191, 36),   # Gold
        (56, 189, 248),   # Cyan
        (52, 211, 153),   # Emerald
        (244, 63, 94),    # Rose
        (250, 204, 21),   # Yellow
        (255, 255, 255),  # White
    ]
    for _ in range(65):
        confetti_list.append({
            "x": random.randint(20, w - 20),
            "y": random.uniform(0, h),
            "size": random.randint(5, 11),
            "speed": random.uniform(2.5, 6.0),
            "drift_speed": random.uniform(1.0, 3.0),
            "drift_phase": random.uniform(0, math.pi * 2),
            "color": random.choice(colors),
            "rot": random.uniform(0, 360),
            "rot_speed": random.uniform(8, 20),
            "type": random.choice(["rect", "circle", "spark"])
        })

    center_x = w // 2
    center_y = 210

    for frame_idx in range(num_frames):
        t = frame_idx / num_frames  # 0.0 to 1.0

        # Background base: Deep Luxury Dark Blue
        img = Image.new("RGBA", (w, h), (10, 16, 33, 255))
        draw = ImageDraw.Draw(img)

        # 1. Background Radar Grid & Rings
        radar_rings = [60, 130, 210, 290]
        for r_base in radar_rings:
            draw.ellipse(
                [center_x - r_base, center_y - r_base, center_x + r_base, center_y + r_base],
                outline=(30, 48, 85, 100),
                width=1
            )

        # Pulsing radar waves expanding outwards
        for p_idx in range(3):
            p_t = (t + p_idx / 3.0) % 1.0
            r_pulse = int(50 + p_t * 260)
            alpha_pulse = int(120 * (1.0 - p_t))
            draw.ellipse(
                [center_x - r_pulse, center_y - r_pulse, center_x + r_pulse, center_y + r_pulse],
                outline=(56, 189, 248, alpha_pulse),
                width=2
            )

        # Rotating Radar Sweep line (360 degrees)
        sweep_angle = t * 2 * math.pi
        sweep_len = 280
        sx = center_x + sweep_len * math.cos(sweep_angle)
        sy = center_y + sweep_len * math.sin(sweep_angle)
        draw.line([(center_x, center_y), (sx, sy)], fill=(56, 189, 248, 65), width=2)

        # 2. Confetti Particles
        for c in confetti_list:
            cy = (c["y"] + frame_idx * c["speed"] * 7.5) % (h + 40) - 20
            cx = (c["x"] + math.sin(t * math.pi * 2 * c["drift_speed"] + c["drift_phase"]) * 22) % w
            c_color = c["color"] + (220,)
            
            rot_ang = (c["rot"] + frame_idx * c["rot_speed"]) * math.pi / 180.0
            s = c["size"]
            
            if c["type"] == "circle":
                draw.ellipse([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=c_color)
            elif c["type"] == "spark":
                draw_star(draw, cx, cy, s, s // 2.5, c_color, points=4)
            else:
                # rotated small ribbon/rect
                dx = math.cos(rot_ang) * s
                dy = math.sin(rot_ang) * (s * 0.5)
                draw.polygon([
                    (cx - dx, cy - dy),
                    (cx + dy, cy - dx),
                    (cx + dx, cy + dy),
                    (cx - dy, cy + dx)
                ], fill=c_color)

        # 3. Top Milestone Badge
        badge_box = [center_x - 195, 38, center_x + 195, 78]
        draw.rounded_rectangle(badge_box, radius=20, fill=(17, 24, 45, 230), outline=(251, 191, 36, 210), width=2)
        # Gold Stars on sides
        draw_star(draw, badge_box[0] + 20, 58, 8, 3.5, (251, 191, 36))
        draw.text((badge_box[0] + 36, 47), "TELEGRAM KİLOMETRE TAŞI", font=f_badge, fill=(251, 191, 36))
        draw_star(draw, badge_box[2] - 20, 58, 8, 3.5, (251, 191, 36))

        # 4. Big 1.500+ Counter (Pulsing Glow)
        pulse = math.sin(t * 2 * math.pi)
        num_str = "1.500+"
        nbb = draw.textbbox((0, 0), num_str, font=f_number)
        nw = nbb[2] - nbb[0]
        nx = center_x - nw // 2
        ny = 98

        # Glow Layers
        for offset_r in [4, 3, 2]:
            glow_color = (245, 158, 11, int(45 + 30 * pulse))
            for ang in range(0, 360, 45):
                rad = math.radians(ang)
                draw.text((nx + offset_r * math.cos(rad), ny + offset_r * math.sin(rad)), num_str, font=f_number, fill=glow_color)

        # Main Gold Number
        main_gold = (255, 235, 120) if pulse > 0.4 else (251, 191, 36)
        draw.text((nx, ny), num_str, font=f_number, fill=main_gold)

        # 5. Header Texts
        head_text = "KİŞİLİK BÜYÜK BİR AİLE OLDUK!"
        hbb = draw.textbbox((0, 0), head_text, font=f_title)
        hw = hbb[2] - hbb[0]
        draw.text((center_x - hw // 2, 204), head_text, font=f_title, fill=(255, 255, 255))

        sub_text = "Katkılarınız, güveniniz ve desteğiniz için sonsuz teşekkürler!"
        sbb = draw.textbbox((0, 0), sub_text, font=f_subtitle)
        sw = sbb[2] - sbb[0]
        draw.text((center_x - sw // 2, 252), sub_text, font=f_subtitle, fill=(52, 211, 153))

        # 6. Glassmorphism Card in Lower Half
        card_box = [45, 305, w - 45, 605]
        card_border_alpha = int(180 + 70 * math.sin(t * 2 * math.pi + 1.0))
        draw.rounded_rectangle(card_box, radius=24, fill=(15, 23, 42, 240), outline=(56, 189, 248, card_border_alpha), width=2)

        # Card Title Header
        draw_star(draw, card_box[0] + 35, card_box[1] + 35, 9, 4, (250, 204, 21))
        draw.text((card_box[0] + 55, card_box[1] + 24), "FAİZ RADARI'NDA BİRLİKTE NELER YAPTIK?", font=f_card_title, fill=(250, 204, 21))

        # Bullets with custom drawn sleek badge icons
        bullets = [
            "Tüm bankaların mevduat & kredi oranlarını anlık radarımıza aldık.",
            "Gizli masrafsız, en karlı finans fırsatlarını tarafsız sunduk.",
            "Dolar, altın ve makas analizleriyle paranızın değerini koruduk.",
            "1.500+ bilinçli tasarrufçu ile Türkiye'nin en şeffaf topluluğu olduk.",
        ]

        by = card_box[1] + 74
        for b_idx, b_text in enumerate(bullets):
            # Checkmark badge circle
            badge_r = 11
            bcx = card_box[0] + 40
            bcy = by + 12
            draw.ellipse([bcx - badge_r, bcy - badge_r, bcx + badge_r, bcy + badge_r], fill=(16, 185, 129, 60), outline=(52, 211, 153, 230), width=2)
            # Checkmark lines
            draw.line([(bcx - 5, bcy), (bcx - 1, bcy + 4), (bcx + 5, bcy - 4)], fill=(255, 255, 255), width=2)

            draw.text((card_box[0] + 66, by), b_text, font=f_desc, fill=(241, 245, 249))
            by += 46

        # 7. Bottom Brand Footer Pill
        footer_box = [center_x - 225, 630, center_x + 225, 684]
        draw.rounded_rectangle(footer_box, radius=27, fill=(15, 23, 42, 255), outline=(52, 211, 153, 220), width=2)
        f_text = "Birlikte Daha Güçlüyüz: @faizradari"
        ftbb = draw.textbbox((0, 0), f_text, font=f_brand)
        ftw = ftbb[2] - ftbb[0]
        draw_star(draw, center_x - ftw // 2 - 18, 657, 8, 3.5, (52, 211, 153))
        draw.text((center_x - ftw // 2, 644), f_text, font=f_brand, fill=(255, 255, 255))
        draw_star(draw, center_x + ftw // 2 + 18, 657, 8, 3.5, (52, 211, 153))

        # Convert to RGB
        rgb_frame = img.convert("RGB")
        frames.append(rgb_frame)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=80,  # 80ms per frame = 12.5 fps
        loop=0,
        optimize=True
    )
    print(f"Yeni GIF başarıyla üretildi: {output_path}")

if __name__ == "__main__":
    generate_celebration_gif()
