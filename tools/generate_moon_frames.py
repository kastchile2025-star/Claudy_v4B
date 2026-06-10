"""Generate 6 PNG frames of the idle moon sprite for Claudy.

Each frame is 88x88 RGBA with:
- Soft dark gradient halo (night vibe).
- Crescent moon (subtractive overlap) with warm cream color and rim glow.
- 3 sparkle stars at varying brightness.
- "Zzz" text floating upward across frames, fading.
"""
from __future__ import annotations
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 88
FRAMES = 6
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

MOON_COLOR = (255, 244, 196, 255)
MOON_RIM = (255, 216, 92, 255)
HALO_COLOR = (255, 226, 122, 110)
SHADOW_COLOR = (10, 10, 28, 255)
STAR_COLOR = (255, 234, 110, 255)
STAR_SOFT = (255, 248, 170, 180)
ZZZ_COLOR = (255, 248, 220, 255)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("seguiemj.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_halo(img: Image.Image, cx: int, cy: int, radius: int, intensity: float) -> None:
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(halo)
    layers = 4
    for i in range(layers, 0, -1):
        r = radius + i * 4
        a = int(HALO_COLOR[3] * (i / layers) * intensity * 0.55)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(HALO_COLOR[0], HALO_COLOR[1], HALO_COLOR[2], a))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=4))
    img.alpha_composite(halo)


def _draw_crescent(img: Image.Image, cx: int, cy: int, r: int) -> None:
    # Moon disc.
    disc = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MOON_COLOR, outline=MOON_RIM, width=2)
    # Carve crescent by drawing dark disc offset to upper-right.
    offset_x = int(r * 0.55)
    offset_y = -int(r * 0.18)
    shadow_r = int(r * 1.05)
    dd.ellipse(
        (cx + offset_x - shadow_r, cy + offset_y - shadow_r,
         cx + offset_x + shadow_r, cy + offset_y + shadow_r),
        fill=(0, 0, 0, 0),
    )
    # Use a mask trick: draw a fully-opaque shadow on a separate layer, then composite via dest-out.
    cut = Image.new("L", img.size, 0)
    cd = ImageDraw.Draw(cut)
    cd.ellipse(
        (cx + offset_x - shadow_r, cy + offset_y - shadow_r,
         cx + offset_x + shadow_r, cy + offset_y + shadow_r),
        fill=255,
    )
    # Subtract cut from disc alpha.
    r_, g_, b_, a_ = disc.split()
    inv_cut = Image.eval(cut, lambda v: 255 - v)
    new_a = Image.eval(a_, lambda v: v)
    new_a = Image.composite(a_, Image.new("L", img.size, 0), inv_cut)
    disc.putalpha(new_a)
    img.alpha_composite(disc)


def _draw_star(d: ImageDraw.ImageDraw, x: float, y: float, size: float, alpha: int) -> None:
    color = (STAR_COLOR[0], STAR_COLOR[1], STAR_COLOR[2], alpha)
    soft = (STAR_SOFT[0], STAR_SOFT[1], STAR_SOFT[2], int(alpha * 0.5))
    s = size
    # 4-pointed sparkle: long vertical + horizontal bar.
    d.line((x - s, y, x + s, y), fill=color, width=1)
    d.line((x, y - s, x, y + s), fill=color, width=1)
    d.line((x - s * 0.6, y - s * 0.6, x + s * 0.6, y + s * 0.6), fill=soft, width=1)
    d.line((x - s * 0.6, y + s * 0.6, x + s * 0.6, y - s * 0.6), fill=soft, width=1)
    d.ellipse((x - 1.2, y - 1.2, x + 1.2, y + 1.2), fill=color)


def _draw_zzz(img: Image.Image, frame: int) -> None:
    # 3 Zs floating up, each delayed; opacity fades, position rises across frames.
    t = frame / FRAMES
    zs = [
        {"x": 14, "y_base": 22, "size": 11, "delay": 0.0},
        {"x": 22, "y_base": 14, "size": 13, "delay": 0.33},
        {"x": 30, "y_base": 6, "size": 16, "delay": 0.66},
    ]
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for z in zs:
        phase = (t - z["delay"]) % 1.0
        rise = phase * 14
        alpha = int(255 * (1 - phase) * 0.95)
        if alpha < 20:
            continue
        font = _font(z["size"])
        col = (ZZZ_COLOR[0], ZZZ_COLOR[1], ZZZ_COLOR[2], alpha)
        # Soft shadow for legibility.
        od.text((z["x"] + 1, z["y_base"] - rise + 1), "Z",
                font=font, fill=(0, 0, 0, int(alpha * 0.5)))
        od.text((z["x"], z["y_base"] - rise), "Z", font=font, fill=col)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.4))
    img.alpha_composite(overlay)


def make_frame(frame: int) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    cx, cy = SIZE // 2 + 6, SIZE // 2 + 4
    bob = math.sin((frame / FRAMES) * math.tau) * 2.2

    _draw_halo(img, cx, int(cy + bob), 18, intensity=0.6 + 0.4 * math.sin((frame / FRAMES) * math.tau))
    _draw_crescent(img, cx, int(cy + bob), 16)

    # Stars: twinkle alpha per-frame.
    star_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(star_overlay)
    star_specs = [
        (cx - 22, cy - 14, 3.5, 0.0),
        (cx + 18, cy - 22, 2.5, 0.5),
        (cx - 18, cy + 22, 3.0, 0.25),
        (cx + 24, cy + 12, 2.0, 0.75),
    ]
    for sx, sy, ssize, phase in star_specs:
        twinkle = 0.5 + 0.5 * math.sin((frame / FRAMES + phase) * math.tau)
        _draw_star(sd, sx, sy + bob * 0.3, ssize, int(120 + 135 * twinkle))
    img.alpha_composite(star_overlay)

    _draw_zzz(img, frame)
    return img


def main() -> None:
    for i in range(FRAMES):
        img = make_frame(i)
        path = os.path.join(OUT_DIR, f"claudy_moon_frame_{i}.png")
        img.save(path, "PNG")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
