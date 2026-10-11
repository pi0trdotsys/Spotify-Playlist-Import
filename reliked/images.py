"""Grafiki rysowane w Pillow: wygładzone kształty, poświata, winyl, okładki.

Canvas w Tk nie wygładza krawędzi, więc wszystko, co okrągłe, powstaje tutaj
jako obraz RGBA i trafia na Canvas jako PhotoImage.
"""

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

from . import theme as t

LANCZOS = Image.Resampling.LANCZOS
BICUBIC = Image.Resampling.BICUBIC


def rgb(color, alpha=None):
    value = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    return value if alpha is None else value + (alpha,)


# --- Prostokąty z zaokrąglonymi rogami -------------------------------------

def _rounded_rect_image(w, h, r, fill, outline, width):
    r = max(0, min(r, w // 2, h // 2))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill_c = rgb(fill, 255) if fill else (0, 0, 0, 0)
    if r == 0:
        draw.rectangle((0, 0, w - 1, h - 1), fill=fill_c,
                       outline=rgb(outline, 255) if outline else None, width=width)
        return img
    # Róg rysowany w 4× i zmniejszany — reszta to proste prostokąty (szybko przy każdym rozmiarze).
    s = 4
    big = Image.new("RGBA", (r * s, r * s), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    box = (0, 0, 2 * r * s - 1, 2 * r * s - 1)
    if outline:
        k = width * s
        bd.ellipse(box, fill=rgb(outline, 255))
        bd.ellipse((k, k, box[2] - k, box[3] - k), fill=fill_c)
    else:
        bd.ellipse(box, fill=fill_c)
    corner = big.resize((r, r), LANCZOS)
    img.paste(corner, (0, 0))
    img.paste(corner.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (w - r, 0))
    img.paste(corner.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, h - r))
    img.paste(corner.transpose(Image.Transpose.ROTATE_180), (w - r, h - r))
    if w - r - 1 >= r:
        draw.rectangle((r, 0, w - r - 1, h - 1), fill=fill_c)
    if h - r - 1 >= r:
        draw.rectangle((0, r, w - 1, h - r - 1), fill=fill_c)
    if outline:
        oc = rgb(outline, 255)
        if w - r - 1 >= r:
            draw.rectangle((r, 0, w - r - 1, width - 1), fill=oc)
            draw.rectangle((r, h - width, w - r - 1, h - 1), fill=oc)
        if h - r - 1 >= r:
            draw.rectangle((0, r, width - 1, h - r - 1), fill=oc)
            draw.rectangle((w - width, r, w - 1, h - r - 1), fill=oc)
    return img


def _round_rect_path(x0, y0, x1, y1, r, steps=12):
    corners = ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180))
    points = [(x0 + r, y0)]
    for cx, cy, start in corners:
        for i in range(steps + 1):
            a = math.radians(start + 90 * i / steps)
            points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    points.append((x0 + r, y0))
    return points


def _dash_segments(points, on, off):
    period = on + off
    pos = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        done = 0.0
        while done < length:
            phase = pos % period
            step = min((on - phase) if phase < on else (period - phase), length - done)
            if phase < on:
                a, b = done / length, (done + step) / length
                yield (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)
            done += step
            pos += step


def _dashed_rect_image(w, h, r, fill, outline, width, dash, gap):
    s = 3
    W, H, R, k = w * s, h * s, r * s, width * s
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, W - 1, H - 1), R, fill=rgb(fill, 255) if fill else None)
    path = _round_rect_path(k / 2, k / 2, W - 1 - k / 2, H - 1 - k / 2, max(1, R - k / 2))
    for a, b in _dash_segments(path, dash * s, gap * s):
        draw.line((a, b), fill=rgb(outline, 255), width=k)
    return img.resize((w, h), LANCZOS)


@lru_cache(maxsize=600)
def rounded_rect(w, h, r, fill, outline=None, width=1, dashed=False):
    w, h = max(1, w), max(1, h)
    if dashed and outline:
        img = _dashed_rect_image(w, h, r, fill, outline, width, t.px(7), t.px(5))
    else:
        img = _rounded_rect_image(w, h, r, fill, outline, width)
    return ImageTk.PhotoImage(img)


@lru_cache(maxsize=64)
def circle(d, fill, outline=None, width=1):
    s = 4
    D = d * s
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if outline:
        draw.ellipse((0, 0, D - 1, D - 1), fill=rgb(outline, 255))
        k = width * s
        draw.ellipse((k, k, D - 1 - k, D - 1 - k), fill=rgb(fill, 255) if fill else (0, 0, 0, 0))
    else:
        draw.ellipse((0, 0, D - 1, D - 1), fill=rgb(fill, 255))
    return ImageTk.PhotoImage(img.resize((d, d), LANCZOS))


# --- Tło z poświatą ---------------------------------------------------------

def glow_background(w, h, bg, spots, fade=0.4):
    """Tło z miękkimi, eliptycznymi poświatami: spots = [(cx, cy, rx, ry, kolor, siła)].

    Dolne `fade` wysokości przechodzi w czyste tło, żeby nie było szwu z tym, co pod spodem.
    """
    q = 4  # liczone w 1/4 rozdzielczości — i tak jest rozmyte
    size = (max(1, w // q), max(1, h // q))
    base = Image.new("RGB", size, rgb(bg))
    # radial_gradient osiąga 255 w rogach; na krawędzi okręgu wpisanego ma ok. 181.
    radial = Image.radial_gradient("L")
    for cx, cy, rx, ry, color, strength in spots:
        spot = (max(2, int(2 * rx / q)), max(2, int(2 * ry / q)))
        mask = radial.resize(spot, BICUBIC).point(
            lambda v, s=strength: int(max(0.0, 1 - v / 181) ** 2.2 * 255 * s))
        base.paste(Image.new("RGB", spot, rgb(color)), (int((cx - rx) / q), int((cy - ry) / q)), mask)
    keep = Image.linear_gradient("L").resize(size, BICUBIC).point(
        lambda v: 255 if v <= (1 - fade) * 255 else int(255 * (255 - v) / (fade * 255)))
    base = Image.composite(base, Image.new("RGB", size, rgb(bg)), keep)
    return ImageTk.PhotoImage(base.resize((w, h), BICUBIC).filter(ImageFilter.GaussianBlur(2)))


# --- Winyl i ramię gramofonu ------------------------------------------------

def _vinyl_base(D, s):
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = D / 2
    draw.ellipse((0, 0, D - 1, D - 1), fill=rgb("#0D1310", 255))
    r, i = c - 3 * s, 0
    label_r = D * 0.19
    while r > label_r + 2 * s:
        color = "#1A241F" if i % 2 == 0 else "#111915"
        draw.ellipse((c - r, c - r, c + r, c + r), outline=rgb(color, 255), width=max(1, int(1.1 * s)))
        r -= 2.4 * s
        i += 1
    draw.ellipse((0, 0, D - 1, D - 1), outline=rgb(t.LINE_STRONG, 255), width=int(1.4 * s))
    draw.ellipse((c - label_r, c - label_r, c + label_r, c + label_r), fill=rgb(t.GREEN, 255))
    inner = label_r * 0.86
    draw.ellipse((c - inner, c - inner, c + inner, c + inner), outline=rgb("#19BF55", 255), width=max(1, s))
    return img, label_r


@lru_cache(maxsize=4)
def vinyl_frames(d, count=24):
    """Klatki obracającego się winylu (odblask ma okres 180°)."""
    s = 2
    D = d * s
    base, label_r = _vinyl_base(D, s)
    sheen = Image.new("L", (D, D), 0)
    sd = ImageDraw.Draw(sheen)
    sd.pieslice((0, 0, D - 1, D - 1), -40, -8, fill=95)
    sd.pieslice((0, 0, D - 1, D - 1), 140, 172, fill=95)
    sheen = sheen.filter(ImageFilter.GaussianBlur(D * 0.05))
    ring = Image.new("L", (D, D), 0)
    rd = ImageDraw.Draw(ring)
    rd.ellipse((2 * s, 2 * s, D - 1 - 2 * s, D - 1 - 2 * s), fill=255)
    c, lr = D / 2, label_r * 1.06
    rd.ellipse((c - lr, c - lr, c + lr, c + lr), fill=0)
    frames = []
    for k in range(count):
        light = ImageChops.multiply(sheen.rotate(-k * 180 / count, resample=BICUBIC), ring)
        layer = Image.new("RGBA", (D, D), (255, 255, 255, 0))
        layer.putalpha(light)
        frame = Image.alpha_composite(base, layer).resize((d, d), LANCZOS)
        frames.append(ImageTk.PhotoImage(frame))
    return frames


@lru_cache(maxsize=4)
def tonearm(d, playing):
    """Ramię gramofonu; obraz o szerokości 1,25·d, środek płyty w (d/2, d/2)."""
    s = 3
    R = d / 2 * s
    W, H = int(d * 1.25 * s), int(d * s)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pivot = (2.2 * R, 0.2 * R)
    length = 1.16 * R

    def stylus(angle):
        a = math.radians(angle)
        return pivot[0] - length * math.sin(a), pivot[1] + length * math.cos(a)

    if playing:
        # Kąt, przy którym igła trafia ok. 0,82 R od środka płyty.
        angle = min(range(0, 70), key=lambda a: abs(math.dist(stylus(a), (R, R)) - 0.82 * R))
    else:
        angle = 3
    tip = stylus(angle)
    a = math.radians(angle)
    back = (pivot[0] + 0.24 * R * math.sin(a), pivot[1] - 0.24 * R * math.cos(a))
    metal, shade = rgb("#AEBDB4", 255), rgb("#5E7066", 255)
    draw.line((back, pivot), fill=shade, width=int(0.13 * R))
    draw.line((pivot, tip), fill=metal, width=max(2, int(0.045 * R)))
    # Główka ramienia odchylona o 22°.
    h_angle = math.radians(angle + 22)
    head_end = (tip[0] - 0.16 * R * math.sin(h_angle), tip[1] + 0.16 * R * math.cos(h_angle))
    draw.line((tip, head_end), fill=metal, width=int(0.1 * R))
    pr = 0.15 * R
    draw.ellipse((pivot[0] - pr, pivot[1] - pr, pivot[0] + pr, pivot[1] + pr), fill=rgb(t.LINE_STRONG, 255))
    pr2 = 0.07 * R
    draw.ellipse((pivot[0] - pr2, pivot[1] - pr2, pivot[0] + pr2, pivot[1] + pr2), fill=metal)
    return ImageTk.PhotoImage(img.resize((W // s, H // s), LANCZOS))


# --- Logo, okładki, ikona okna ----------------------------------------------

def _bezier(p0, p1, p2, steps=40):
    for i in range(steps + 1):
        u = i / steps
        yield ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
               (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1])


@lru_cache(maxsize=8)
def spotify_logo(d):
    s = 4
    D = d * s
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, D - 1, D - 1), fill=rgb(t.GREEN, 255))
    ink = rgb("#08100C", 255)
    for y, half, thick, bend in ((0.36, 0.30, 0.085, 0.075), (0.53, 0.255, 0.07, 0.06), (0.685, 0.215, 0.058, 0.048)):
        p0 = ((0.5 - half) * D, (y + bend) * D)
        p1 = (0.5 * D, (y - bend) * D)
        p2 = ((0.5 + half) * D, (y + bend * 1.25) * D)
        pts = list(_bezier(p0, p1, p2))
        width = int(thick * D)
        draw.line(pts, fill=ink, width=width, joint="curve")
        for x, yy in (pts[0], pts[-1]):
            draw.ellipse((x - width / 2, yy - width / 2, x + width / 2, yy + width / 2), fill=ink)
    return ImageTk.PhotoImage(img.resize((d, d), LANCZOS))


COVER_GRADIENTS = (
    ("#FF5F6D", "#7B2FF7"), ("#4FACFE", "#00F2A9"), ("#F7971E", "#FFD200"),
    ("#1ED760", "#0B6E4F"), ("#EE0979", "#FF6A00"), ("#8E2DE2", "#4A00E0"),
    ("#00C9FF", "#92FE9D"), ("#FC466B", "#3F5EFB"), ("#F953C6", "#B91D73"),
    ("#43CEA2", "#185A9D"), ("#FFB347", "#FF5E62"), ("#654EA3", "#EAAFC8"),
)


@lru_cache(maxsize=32)
def cover(size, index):
    """Okładka zastępcza: gradient ze śladem płyty."""
    s = 3
    S = size * s
    c1, c2 = (rgb(c) for c in COVER_GRADIENTS[index % len(COVER_GRADIENTS)])
    mid = tuple((a + b) // 2 for a, b in zip(c1, c2))
    grad = Image.new("RGB", (2, 2))
    grad.putdata([c1, mid, mid, c2])
    art = grad.resize((S, S), Image.Resampling.BILINEAR).convert("RGBA")
    overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    c, r = S / 2, S * 0.3
    od.ellipse((c - r, c - r, c + r, c + r), outline=(255, 255, 255, 70), width=s)
    r = S * 0.07
    od.ellipse((c - r, c - r, c + r, c + r), fill=(255, 255, 255, 150))
    art = Image.alpha_composite(art, overlay)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), int(S * 0.16), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(art, (0, 0), mask)
    return ImageTk.PhotoImage(out.resize((size, size), LANCZOS))


def app_icon(size):
    s = 4
    D = size * s
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, D - 1, D - 1), fill=rgb(t.GREEN, 255))
    try:
        glyph = ImageFont.truetype("SegoeIcons.ttf", int(D * 0.52))
        draw.text((D / 2, D / 2 + D * 0.02), t.ICON["music"], font=glyph, fill=rgb(t.GREEN_INK, 255), anchor="mm")
    except OSError:
        r = D * 0.12
        draw.ellipse((D / 2 - r, D / 2 - r, D / 2 + r, D / 2 + r), fill=rgb(t.GREEN_INK, 255))
    return ImageTk.PhotoImage(img.resize((size, size), LANCZOS))
