"""Generate 6 PNG frames of an idle coffee-cup sprite with rising steam.

Output: claudy_idle_frame_0..5.png (88x88 RGBA)
- Warm ceramic mug with subtle highlight + handle.
- 3 steam wisps that rise and fade across frames (offset phases).
- Saucer underneath.
"""
from __future__ import annotations
import math
import os
from PIL import Image, ImageDraw, ImageFilter

SIZE = 88
FRAMES = 6
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

MUG_BODY = (231, 226, 218, 255)
MUG_SHADOW = (180, 168, 150, 255)
MUG_RIM = (252, 248, 240, 255)
COFFEE = (74, 47, 33, 255)
COFFEE_FOAM = (160, 120, 90, 255)
SAUCER = (210, 198, 178, 255)
SAUCER_SHADOW = (130, 118, 100, 200)
STEAM = (255, 252, 245, 220)


def _draw_steam(img: Image.Image, frame: int) -> None:
    """3 wisps rising — vertical position + opacity vary with phase."""
    t = frame / FRAMES
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    wisps = [
        {"x": 36, "delay": 0.0, "amp": 4.5},
        {"x": 44, "delay": 0.4, "amp": 5.5},
        {"x": 52, "delay": 0.7, "amp": 4.0},
    ]
    for w in wisps:
        phase = (t - w["delay"]) % 1.0
        rise = phase * 22  # px traveled upward
        alpha = int(220 * (1 - phase) * (phase * 4 if phase < 0.25 else 1))
        if alpha < 20:
            continue
        # Curvy wisp as a thick squiggle.
        cx = w["x"]
        cy_base = 36
        steps = 8
        pts = []
        for s in range(steps):
            y = cy_base - rise - s * 2
            x = cx + math.sin((s / 2) + phase * math.tau) * w["amp"]
            pts.append((x, y))
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            od.line([(ax, ay), (bx, by)], fill=(STEAM[0], STEAM[1], STEAM[2], alpha),
                    width=3)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.alpha_composite(overlay)


def _draw_mug(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    # Saucer (ellipse).
    d.ellipse((14, 64, 74, 80), fill=SAUCER)
    d.ellipse((18, 66, 70, 76), fill=SAUCER_SHADOW)

    # Mug body — rounded trapezoid via rounded rect.
    mug_box = (26, 40, 62, 70)
    d.rounded_rectangle(mug_box, radius=6, fill=MUG_BODY)
    # Body shading on right side.
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rounded_rectangle((48, 40, 62, 70), radius=6, fill=(*MUG_SHADOW[:3], 130))
    shade = shade.filter(ImageFilter.GaussianBlur(radius=2))
    img.alpha_composite(shade)

    # Handle — open ring on the right.
    handle = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(handle)
    hd.ellipse((58, 46, 76, 64), outline=MUG_BODY, width=4)
    # Cut left half so it attaches to the mug.
    cut = Image.new("L", img.size, 0)
    cd = ImageDraw.Draw(cut)
    cd.rectangle((0, 0, 62, 88), fill=255)
    r, g, b, a = handle.split()
    new_a = Image.eval(a, lambda v: v)
    new_a = Image.composite(Image.new("L", img.size, 0), a, cut)
    handle.putalpha(new_a)
    img.alpha_composite(handle)

    # Coffee surface (ellipse inside top of mug).
    d.ellipse((28, 38, 60, 46), fill=COFFEE)
    # Foam ring.
    d.ellipse((30, 38, 58, 44), outline=COFFEE_FOAM, width=1)

    # Top rim highlight.
    d.line((28, 42, 60, 42), fill=MUG_RIM, width=1)
    # Bottom shadow of mug on saucer.
    d.ellipse((26, 66, 62, 74), fill=(70, 60, 50, 100))


def make_frame(frame: int) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    _draw_mug(img)
    _draw_steam(img, frame)
    return img


def main() -> None:
    for i in range(FRAMES):
        img = make_frame(i)
        path = os.path.join(OUT_DIR, f"claudy_idle_frame_{i}.png")
        img.save(path, "PNG")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
