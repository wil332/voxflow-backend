import os
from PIL import Image, ImageDraw, ImageFont

# 1. Buat folder assets jika belum ada
os.makedirs("assets", exist_ok=True)

# 2. Buat kanvas 1080x1920 (9:16 TikTok)
width, height = 1080, 1920
img = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(img)

# 3. Warna background gradasi futuristik
for y in range(height):
    r = int(15 + (25 - 15) * (y / height))
    g = int(23 + (35 - 23) * (y / height))
    b = int(42 + (75 - 42) * (y / height))
    draw.line([(0, y), (width, y)], fill=(r, g, b))

# 4. Efek Cahaya / Glow
glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow_overlay)
glow_draw.ellipse([width//2 - 400, 100, width//2 + 400, 900], fill=(37, 99, 235, 40))
glow_draw.ellipse([width//2 - 250, 250, width//2 + 250, 750], fill=(6, 182, 212, 50))
img = Image.alpha_composite(img.convert("RGBA"), glow_overlay)
draw = ImageDraw.Draw(img)

try:
    title_font = ImageFont.truetype("arial.ttf", 54)
    subtitle_font = ImageFont.truetype("arial.ttf", 32)
    tag_font = ImageFont.truetype("arial.ttf", 28)
except IOError:
    title_font = subtitle_font = tag_font = ImageFont.load_default()

# 5. Header & Branding PodFlow AI
draw.rounded_rectangle([width//2 - 180, 160, width//2 + 180, 220], radius=30, fill=(37, 99, 235, 200), outline=(6, 182, 212, 255), width=2)
draw.text((width//2, 190), "AI PODCAST EPISODE", fill=(255, 255, 255), font=tag_font, anchor="mm")

draw.text((width//2, 290), "PODFLOW AI", fill=(255, 255, 255), font=title_font, anchor="mm")
draw.text((width//2, 345), "Otomatisasi Konten & Auto-Publish TikTok", fill=(6, 182, 212), font=subtitle_font, anchor="mm")
draw.line([(width//2 - 200, 410), (width//2 + 200, 410)], fill=(37, 99, 235, 180), width=3)

# 6. Speaker Badges (Budi & Siti)
draw.rounded_rectangle([120, 470, 480, 550], radius=20, fill=(30, 41, 59, 230), outline=(37, 99, 235, 255), width=2)
draw.text((300, 510), "🎙️ Host A: Budi", fill=(255, 255, 255), font=tag_font, anchor="mm")

draw.rounded_rectangle([600, 470, 960, 550], radius=20, fill=(30, 41, 59, 230), outline=(6, 182, 212, 255), width=2)
draw.text((780, 510), "🎙️ Host B: Siti", fill=(255, 255, 255), font=tag_font, anchor="mm")

# 7. Bingkai Tengah untuk Waveform & Subtitle
draw.rounded_rectangle([80, 600, 1000, 1550], radius=30, fill=(15, 23, 42, 120), outline=(51, 65, 85, 180), width=2)

# 8. Footer Branding MAXY
draw.rounded_rectangle([width//2 - 250, 1680, width//2 + 250, 1750], radius=35, fill=(37, 99, 235, 220))
draw.text((width//2, 1715), "Powered by PodFlow AI × MAXY", fill=(255, 255, 255), font=subtitle_font, anchor="mm")

# 9. Simpan file
output_path = "assets/tiktok_bg.png"
img.save(output_path, "PNG")
print(f"✅ SUKSES: Gambar background telah tersimpan di '{output_path}'!")