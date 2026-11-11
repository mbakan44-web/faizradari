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

def generate_external_promo(
    gif_path: str = "faiz_radari_promo_external.gif",
    png_path: str = "faiz_radari_promo_external.png",
    story_path: str = "faiz_radari_promo_external_story.png",
    num_frames: int = 32
):
    w, h = 800, 800
    frames = []

    # Fonts
    f_badge = get_font(20, bold=True)
    f_top_sub = get_font(28, bold=True)
    f_headline = get_font(46, bold=True)
    f_number = get_font(88, bold=True)
    f_sub = get_font(23, bold=True)
    f_card_h = get_font(24, bold=True)
    f_card_text = get_font(22, bold=True)
    f_cta_btn = get_font(25, bold=True)

    # Framing confetti setup
    random.seed(77)
    confetti_list = []
    colors = [
        (251, 191, 36),   # Gold
        (56, 189, 248),   # Cyan
        (52, 211, 153),   # Emerald
        (244, 63, 94),    # Rose
        (255, 255, 255),  # White
    ]
    for _ in range(45):
        is_side = random.random() < 0.8
        x_val = random.choice([random.randint(15, 130), random.randint(w - 130, w - 15)]) if is_side else random.randint(15, w - 15)
        confetti_list.append({
            "x": x_val,
            "y": random.uniform(0, h),
            "size": random.randint(6, 12),
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

        # 1. Subtle Background Radar Pulse
        radar_center_y = 210
        for r_base in [90, 190, 290]:
            draw.ellipse(
                [center_x - r_base, radar_center_y - r_base, center_x + r_base, radar_center_y + r_base],
                outline=(22, 38, 70, 120),
                width=1
            )

        for p_idx in range(2):
            p_t = (t + p_idx / 2.0) % 1.0
            r_pulse = int(60 + p_t * 260)
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

            # Exclude central text area completely
            if 90 < cx < 710 and 60 < cy < 355:
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

        # 3. Top Milestone Pill Badge
        badge_box = [center_x - 225, 34, center_x + 225, 80]
        draw.rounded_rectangle(badge_box, radius=23, fill=(13, 22, 45, 255), outline=(56, 189, 248, 255), width=2)
        draw_star(draw, badge_box[0] + 24, 57, 9, 4, (56, 189, 248))
        badge_txt = "FAİZ RADARI BÜYÜYOR"
        bbb = draw.textbbox((0, 0), badge_txt, font=f_badge)
        bw = bbb[2] - bbb[0]
        draw.text((center_x - bw // 2, 45), badge_txt, font=f_badge, fill=(56, 189, 248))
        draw_star(draw, badge_box[2] - 24, 57, 9, 4, (56, 189, 248))

        # 4. Hero Headlines: TELEGRAM KANALIMIZ HIZLA BÜYÜYOR!
        top_txt = "TELEGRAM KANALIMIZ"
        tbb = draw.textbbox((0, 0), top_txt, font=f_top_sub)
        tw = tbb[2] - tbb[0]
        draw.text((center_x - tw // 2, 94), top_txt, font=f_top_sub, fill=(203, 213, 225))

        h_text = "HIZLA BÜYÜYOR!"
        hbb = draw.textbbox((0, 0), h_text, font=f_headline)
        hw = hbb[2] - hbb[0]
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((center_x - hw // 2 + dx, 134 + dy), h_text, font=f_headline, fill=(0, 0, 0, 255))
        draw.text((center_x - hw // 2, 134), h_text, font=f_headline, fill=(255, 255, 255))

        # 5. Glowing Milestone: 1.500+ ABONE
        pulse = math.sin(t * 2 * math.pi)
        num_str = "1.500+ ABONE"
        nbb = draw.textbbox((0, 0), num_str, font=f_number)
        nw = nbb[2] - nbb[0]
        nx = center_x - nw // 2
        ny = 196

        for ox in range(-4, 5, 2):
            for oy in range(-4, 5, 2):
                if ox != 0 or oy != 0:
                    draw.text((nx + ox, ny + oy), num_str, font=f_number, fill=(0, 0, 0, 255))

        num_fill = (255, 235, 90) if pulse > 0.3 else (251, 191, 36)
        draw.text((nx, ny), num_str, font=f_number, fill=num_fill)

        sub_desc = "Tüm bankaların gizli oranları tek bir ekranda!"
        sbb = draw.textbbox((0, 0), sub_desc, font=f_sub)
        sw = sbb[2] - sbb[0]
        draw.text((center_x - sw // 2, 304), sub_desc, font=f_sub, fill=(52, 211, 153))

        # 6. Ultra-Crisp Content Container (Why Join Telegram?)
        card_box = [38, 355, w - 38, 665]
        border_glow = (250, 204, 21, int(200 + 55 * pulse))
        draw.rounded_rectangle(card_box, radius=24, fill=(12, 20, 42, 255), outline=border_glow, width=3)

        # Inner Header
        draw_star(draw, card_box[0] + 36, card_box[1] + 32, 10, 4.5, (56, 189, 248))
        c_title = "NEDEN TELEGRAM KANALIMIZA GELMELİSİNİZ?"
        draw.text((card_box[0] + 58, card_box[1] + 20), c_title, font=f_card_h, fill=(56, 189, 248))

        # 3 Big, High Contrast Benefit Rows
        benefits = [
            "Anlık Faiz İndirimleri & Yüksek Mevduat Bildirimleri",
            "Gizli Masrafsız, En Uygun Kredi Hesaplama Botu",
            "Sabah 10 Maddelik Günün Finans Raporu & Bültenler",
        ]

        row_y = card_box[1] + 74
        for b_text in benefits:
            pill_box = [card_box[0] + 20, row_y, card_box[2] - 20, row_y + 54]
            draw.rounded_rectangle(pill_box, radius=14, fill=(19, 30, 60, 255), outline=(38, 56, 95, 255), width=1)
            
            icx = pill_box[0] + 30
            icy = row_y + 27
            draw.ellipse([icx - 14, icy - 14, icx + 14, icy + 14], fill=(245, 158, 11, 255))
            draw.line([(icx - 6, icy), (icx - 2, icy + 5), (icx + 6, icy - 5)], fill=(255, 255, 255), width=3)

            draw.text((pill_box[0] + 58, row_y + 14), b_text, font=f_card_text, fill=(255, 255, 255))
            row_y += 66

        # 7. Big Glowing Call To Action Button (Bottom)
        footer_box = [center_x - 260, 695, center_x + 260, 755]
        btn_glow = (52, 211, 153, 255) if pulse > 0 else (16, 185, 129, 255)
        draw.rounded_rectangle(footer_box, radius=30, fill=btn_glow, outline=(255, 255, 255, 255), width=2)
        btn_text = "► ARAMIZA KATILIN: t.me/faizradari"
        btbb = draw.textbbox((0, 0), btn_text, font=f_cta_btn)
        btw = btbb[2] - btbb[0]
        draw.text((center_x - btw // 2, 710), btn_text, font=f_cta_btn, fill=(10, 24, 18))

        # Convert to RGB
        rgb_frame = img.convert("RGB")
        frames.append(rgb_frame)

    # Save animated GIF
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True
    )
    print(f"Tanıtım GIF'i kaydedildi: {gif_path}")

    # Save high-res still PNG (frame 10)
    frames[10].save(png_path)
    print(f"Kare PNG kaydedildi: {png_path}")

    # Render Vertical 1080x1920 Story/Reels/TikTok PNG
    from image_generator import render_vertical_story_image
    render_vertical_story_image(
        square_image_path=png_path,
        title="TELEGRAM'DA HIZLA BÜYÜYORUZ!",
        output_path=story_path
    )
    print(f"Dikey 1080x1920 Hikaye kaydedildi: {story_path}")

if __name__ == "__main__":
    generate_external_promo()
