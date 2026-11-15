import math
import subprocess
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

def render_3000_square_image(output_path: str = "faiz_radari_3000_kutlama.png") -> str:
    w, h = 1080, 1080
    img = Image.new("RGB", (w, h), (8, 14, 32))
    draw = ImageDraw.Draw(img)

    # 1. Zarif degrade arka plan
    for y in range(h):
        r = int(8 + (15 - 8) * (y / h))
        g = int(14 + (24 - 14) * (y / h))
        b = int(32 + (50 - 32) * (y / h))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Üst neon çizgi (Zümrüt -> Camgöbeği)
    for x in range(w):
        ratio = x / w
        cr = int(16 * (1 - ratio) + 14 * ratio)
        cg = int(185 * (1 - ratio) + 165 * ratio)
        cb = int(129 * (1 - ratio) + 233 * ratio)
        draw.line([(x, 0), (x, 4)], fill=(cr, cg, cb))

    # Radar çizgileri (Arka plan)
    center_x = w // 2
    radar_y = 280
    for r_base in [120, 240, 360]:
        draw.ellipse([center_x - r_base, radar_y - r_base, center_x + r_base, radar_y + r_base], outline=(20, 35, 65), width=1)

    f_badge = get_font(20, bold=True)
    f_num = get_font(130, bold=True)
    f_title = get_font(42, bold=True)
    f_sub = get_font(26, bold=True)
    f_card_h = get_font(25, bold=True)
    f_desc = get_font(23, bold=False)
    f_brand = get_font(24, bold=True)

    # 2. Üst Rozet
    badge_box = [center_x - 260, 42, center_x + 260, 94]
    draw.rounded_rectangle(badge_box, radius=26, fill=(16, 26, 52), outline=(250, 204, 21), width=2)
    draw_star(draw, badge_box[0] + 28, 68, 10, 4.5, (250, 204, 21))
    b_txt = "TOPLULUK KİLOMETRE TAŞI"
    bbb = draw.textbbox((0, 0), b_txt, font=f_badge)
    bw = bbb[2] - bbb[0]
    draw.text((center_x - bw // 2, 54), b_txt, font=f_badge, fill=(250, 204, 21))
    draw_star(draw, badge_box[2] - 28, 68, 10, 4.5, (250, 204, 21))

    # 3. Dev Sayı: 3.000+
    num_str = "3.000+"
    nbb = draw.textbbox((0, 0), num_str, font=f_num)
    nw = nbb[2] - nbb[0]
    nx = center_x - nw // 2
    ny = 110

    # Keskin gölge
    for ox in range(-5, 6, 3):
        for oy in range(-5, 6, 3):
            if ox != 0 or oy != 0:
                draw.text((nx + ox, ny + oy), num_str, font=f_num, fill=(0, 0, 0))
    # Parlak Altın Rengi
    draw.text((nx, ny), num_str, font=f_num, fill=(251, 191, 36))

    # 4. Ana Başlık & Teşekkür
    head_txt = "KİŞİLİK BÜYÜK BİR AİLE OLDUK!"
    hbb = draw.textbbox((0, 0), head_txt, font=f_title)
    hw = hbb[2] - hbb[0]
    draw.text((center_x - hw // 2, 265), head_txt, font=f_title, fill=(255, 255, 255))

    sub_txt = "İlginiz, desteğiniz ve güveniniz için sonsuz teşekkürler!"
    sbb = draw.textbbox((0, 0), sub_txt, font=f_sub)
    sw = sbb[2] - sbb[0]
    draw.text((center_x - sw // 2, 328), sub_txt, font=f_sub, fill=(52, 211, 153))

    # 5. Geniş ve Doygun İçerik Kartı
    card_box = [60, 400, w - 60, 930]
    draw.rounded_rectangle(card_box, radius=24, fill=(13, 21, 44), outline=(56, 189, 248), width=2)

    # Kart Başlığı
    draw_star(draw, card_box[0] + 45, card_box[1] + 44, 11, 5, (250, 204, 21))
    draw.text((card_box[0] + 70, card_box[1] + 30), "FAİZ RADARI'NDA BİRLİKTE NELER YAPTIK?", font=f_card_h, fill=(250, 204, 21))
    draw.line([(card_box[0] + 45, card_box[1] + 80), (card_box[2] - 45, card_box[1] + 80)], fill=(30, 48, 80), width=1)

    bullets = [
        "Tüm bankaların kredi & mevduat oranlarını anlık radarımıza aldık.",
        "Masrafsız, en avantajlı finans fırsatlarını tarafsızca sunduk.",
        "Dolar, altın ve makas analizleriyle paranızın değerini koruduk.",
        "3.000+ bilinçli tasarrufçu ile Türkiye'nin en şeffaf topluluğu olduk.",
    ]

    by = card_box[1] + 115
    for b_text in bullets:
        # Rozet
        bcx = card_box[0] + 55
        bcy = by + 16
        draw.ellipse([bcx - 16, bcy - 16, bcx + 16, bcy + 16], fill=(16, 185, 129))
        draw.line([(bcx - 7, bcy), (bcx - 2, bcy + 6), (bcx + 8, bcy - 6)], fill=(255, 255, 255), width=3)

        draw.text((card_box[0] + 90, by), b_text, font=f_desc, fill=(241, 245, 249))
        by += 98

    # 6. Alt Marka Rozeti
    footer_box = [center_x - 280, 965, center_x + 280, 1030]
    draw.rounded_rectangle(footer_box, radius=32, fill=(16, 185, 129), outline=(52, 211, 153), width=2)
    f_text = "Faiz Radarı Büyüyor  •  @faizradari"
    ftbb = draw.textbbox((0, 0), f_text, font=f_brand)
    ftw = ftbb[2] - ftbb[0]
    draw.text((center_x - ftw // 2, 982), f_text, font=f_brand, fill=(10, 24, 18))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    print(f"[BAŞARILI] 3.000 Kutlama Görseli üretildi: {output_path}")
    return output_path

def render_3000_vertical_image(square_img_path: str, output_path: str = "faiz_radari_3000_vertical.png") -> str:
    v_width = 1080
    v_height = 1920
    canvas = Image.new("RGB", (v_width, v_height), color=(8, 13, 26))
    draw = ImageDraw.Draw(canvas)

    for y in range(v_height):
        r = int(8 + (15 - 8) * (y / v_height))
        g = int(13 + (24 - 13) * (y / v_height))
        b = int(26 + (48 - 26) * (y / v_height))
        draw.line([(0, y), (v_width, y)], fill=(r, g, b))

    # Üst neon çizgi
    for x in range(v_width):
        ratio = x / v_width
        cr = int(16 * (1 - ratio) + 14 * ratio)
        cg = int(185 * (1 - ratio) + 165 * ratio)
        cb = int(129 * (1 - ratio) + 233 * ratio)
        draw.line([(x, 0), (x, 6)], fill=(cr, cg, cb))

    f_top = get_font(18, bold=True)
    f_main = get_font(42, bold=True)
    f_sub = get_font(23, bold=True)
    f_btn = get_font(23, bold=True)
    f_cta_p = get_font(20, bold=False)
    f_brand = get_font(20, bold=True)

    # 1. Üst Alan
    draw.rounded_rectangle([(60, 130), (520, 182)], radius=12, fill=(18, 28, 56), outline=(250, 204, 21), width=2)
    draw.text((82, 145), "★ 3.000 KİŞİYİ GEÇTİK ★", font=f_top, fill=(250, 204, 21))

    draw.text((60, 205), "İLGİNİZE TEŞEKKÜRLER!", font=f_main, fill=(255, 255, 255))
    draw.text((60, 268), "Bilinçli Tasarrufun 1 Numaralı Radarı Büyüyor!", font=f_sub, fill=(52, 211, 153))

    draw.line([(60, 320), (v_width - 60, 320)], fill=(30, 48, 80), width=2)

    # 2. Ortalanmış Kare İnfografik
    sq_img = Image.open(square_img_path).convert("RGBA")
    target_size = 980
    sq_resized = sq_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    pos_x = (v_width - target_size) // 2
    pos_y = 350

    draw.rounded_rectangle([(pos_x - 6, pos_y - 6), (pos_x + target_size + 6, pos_y + target_size + 6)], radius=20, fill=(13, 21, 42), outline=(30, 58, 95), width=2)
    canvas.paste(sq_resized, (pos_x, pos_y), sq_resized)

    # 3. Alt Eylem Butonu & CTA Kartı
    card_y = 1365
    card_h = 195
    draw.rounded_rectangle([(60, card_y), (v_width - 60, card_y + card_h)], radius=20, fill=(13, 21, 42), outline=(250, 204, 21), width=2)

    btn_box = [(85, card_y + 18), (v_width - 85, card_y + 78)]
    draw.rounded_rectangle(btn_box, radius=30, fill=(16, 185, 129), outline=(52, 211, 153), width=2)
    b_txt = "► BÜTÇENE GÖRE EN UYGUN BANKAYI BUL ◄"
    bbb = draw.textbbox((0, 0), b_txt, font=f_btn)
    bw = bbb[2] - bbb[0]
    draw.text(((v_width - bw) // 2, card_y + 34), b_txt, font=f_btn, fill=(10, 24, 18))

    draw.text((90, card_y + 96), "Sıfır faizli nakit avans & net masraf kontrolü profildeki linkte:", font=f_cta_p, fill=(241, 245, 249))
    draw.text((90, card_y + 136), "► t.me/faizradari  •  @faizradari", font=f_brand, fill=(56, 189, 248))

    # Alt yasal uyarı
    draw.text(
        (60, 1585),
        "• Kamuya açık banka verileridir. Yatırım tavsiyesi niteliği taşımaz.",
        font=get_font(15, bold=False),
        fill=(100, 116, 139)
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    print(f"[BAŞARILI] 3.000 Dikey Görsel üretildi: {output_path}")
    return output_path

def render_3000_video(v_image_path: str, audio_path: str = "bg_music_loop.mp3", output_path: str = "faiz_radari_3000_video.mp4", duration: int = 8) -> str:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

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
    print(f"[BAŞARILI] 3.000 Sesli Dikey Video üretildi: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    sq = render_3000_square_image("faiz_radari_3000_kutlama.png")
    vt = render_3000_vertical_image(sq, "faiz_radari_3000_vertical.png")
    vd = render_3000_video(vt, "bg_music_loop.mp3", "faiz_radari_3000_video.mp4", duration=8)
    print("Tüm 3.000 kutlama medyaları başarıyla hazırlandı!")
