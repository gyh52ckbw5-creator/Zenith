"""Zenith PWA ikonlarini uretir (static/icons/icon-*.png).

Bir defaya mahsus gelistirme araci - calistirmak icin Pillow gerekir
(`pip install Pillow`). Uygulamanin kendisi bu script'e veya Pillow'a
bagimli degildir, sadece uretilen PNG dosyalari repo'da tutulur.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"
BG = (11, 15, 25)
ACCENT = (91, 140, 255)


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    margin = size * 0.16
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size * 0.18,
        outline=ACCENT,
        width=max(2, int(size * 0.03)),
    )

    text = "Z"
    font_size = int(size * 0.5)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - text_w) / 2 - bbox[0], (size - text_h) / 2 - bbox[1]),
        text,
        fill=ACCENT,
        font=font,
    )
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        make_icon(size).save(OUT_DIR / f"icon-{size}.png")
        print(f"yazildi: icon-{size}.png")


if __name__ == "__main__":
    main()
