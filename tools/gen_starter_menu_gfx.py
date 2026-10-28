#!/usr/bin/env python3
"""Generate original starter-choose chrome (layout cloned from Quetzal, not ripped)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphics" / "starter_choose"

# Reserved 4bpp indices. Colors 1-2 are swapped at runtime per type.
PALETTE = [
    (0, 0, 0),          # 0 transparent / unused
    (168, 212, 140),    # 1 type fill (placeholder grass)
    (148, 196, 128),    # 2 type watermark
    (27, 74, 92),       # 3 header / footer / name bar teal
    (20, 58, 74),       # 4 teal shadow
    (236, 241, 244),    # 5 panel fill
    (196, 206, 212),    # 6 panel / cell border
    (248, 250, 252),    # 7 cell fill
    (255, 255, 255),    # 8 white
    (255, 214, 90),     # 9 cursor yellow (tiles unused)
    (18, 48, 60),       # 10 darker teal
    (210, 220, 226),    # 11 panel highlight
    (40, 96, 116),      # 12 teal light
    (120, 140, 150),    # 13 unused
    (80, 80, 80),       # 14 unused
    (16, 16, 16),       # 15 unused
]

W, H = 256, 160
HEADER_H = 16
FOOTER_Y = 144

# Must match src/starter_choose.c
GRID_ORIGINS = [(32, 48), (72, 48), (112, 48),
                (32, 84), (72, 84), (112, 84),
                (32, 120), (72, 120), (112, 120)]
CELL = 36
LEFT_PANEL = (8, 22, 128, 140)
RIGHT_PANEL = (136, 22, 232, 140)
NAME_BAR = (140, 104, 228, 120)


def pal_index(rgb):
    return PALETTE.index(tuple(rgb))


def new_canvas():
    # Index 0 is transparent so BG3's scrolling type pattern shows through.
    img = Image.new("P", (W, H), 0)
    img.putpalette([c for rgb in PALETTE for c in rgb] + [0] * (768 - 16 * 3))
    return img


def draw_hex_watermark(px):
    # Regular hex grid using palette index 2.
    r = 10
    h_step = int(r * 1.732)
    for row, y in enumerate(range(-8, H, h_step)):
        xoff = (r * 3 // 2) if row % 2 else 0
        for x in range(-8 + xoff, W, r * 3):
            for i in range(6):
                # diamond-ish hex outline
                pass
            pts = []
            for i in range(6):
                from math import cos, sin, pi
                a = pi / 6 + i * pi / 3
                pts.append((int(x + r * cos(a)), int(y + r * sin(a))))
            for i in range(6):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % 6]
                _line(px, x0, y0, x1, y1, 2)


def _line(px, x0, y0, x1, y1, color):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < W and HEADER_H <= y0 < FOOTER_Y:
            px[x0, y0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_pokeball_mark(px, cx, cy, radius=14):
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if not (0 <= x < W and HEADER_H <= y < FOOTER_Y):
                continue
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if abs(d2 - radius * radius) <= radius or abs(y - cy) <= 0 and d2 <= radius * radius:
                if px[x, y] == 1:
                    px[x, y] = 2
            if d2 <= 9 and px[x, y] == 1:
                px[x, y] = 2


def fill_rect(px, box, color, filled=True, width=1):
    x0, y0, x1, y1 = box
    if filled:
        for y in range(y0, y1):
            for x in range(x0, x1):
                if 0 <= x < W and 0 <= y < H:
                    px[x, y] = color
    else:
        for x in range(x0, x1):
            for t in range(width):
                if 0 <= x < W:
                    if 0 <= y0 + t < H:
                        px[x, y0 + t] = color
                    if 0 <= y1 - 1 - t < H:
                        px[x, y1 - 1 - t] = color
        for y in range(y0, y1):
            for t in range(width):
                if 0 <= y < H:
                    if 0 <= x0 + t < W:
                        px[x0 + t, y] = color
                    if 0 <= x1 - 1 - t < W:
                        px[x1 - 1 - t, y] = color


def round_rect(px, box, color, radius=4, fill=None):
    x0, y0, x1, y1 = box
    if fill is not None:
        fill_rect(px, box, fill, True)
    # carve corners back to surrounding color is skipped; just draw border
    fill_rect(px, box, color, False, 1)
    # simple rounded look: knock the four corner pixels to fill
    corners = [(x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)]
    for x, y in corners:
        if 0 <= x < W and 0 <= y < H:
            px[x, y] = 1 if fill is None else fill


def draw_menu():
    img = new_canvas()
    px = img.load()

    fill_rect(px, (0, 0, W, HEADER_H), 3)
    fill_rect(px, (0, FOOTER_Y, W, H), 3)
    fill_rect(px, (0, HEADER_H, W, HEADER_H + 1), 4)
    fill_rect(px, (0, FOOTER_Y - 1, W, FOOTER_Y), 4)

    # left / right cards
    fill_rect(px, LEFT_PANEL, 5)
    fill_rect(px, LEFT_PANEL, 6, False, 1)
    fill_rect(px, RIGHT_PANEL, 5)
    fill_rect(px, RIGHT_PANEL, 6, False, 1)
    fill_rect(px, NAME_BAR, 3)

    half = CELL // 2
    for cx, cy in GRID_ORIGINS:
        box = (cx - half, cy - half, cx + half, cy + half)
        fill_rect(px, box, 7)
        fill_rect(px, box, 6, False, 1)

    # tiny pokeball in header
    for y in range(4, 12):
        for x in range(8, 16):
            dx, dy = x - 12, y - 8
            if dx * dx + dy * dy <= 14:
                px[x, y] = 8 if y < 8 else 15
            if abs(dy) <= 0 and dx * dx <= 14:
                px[x, y] = 15
            if dx * dx + dy * dy <= 3:
                px[x, y] = 8

    return img


def extract_tiles(img):
    tiles = []
    lookup = {}
    tilemap = []
    for ty in range(H // 8):
        row = []
        for tx in range(W // 8):
            tile = img.crop((tx * 8, ty * 8, tx * 8 + 8, ty * 8 + 8))
            key = tile.tobytes()
            if key not in lookup:
                lookup[key] = len(tiles)
                tiles.append(tile)
            row.append(lookup[key])
        tilemap.append(row)
    return tiles, tilemap


def write_tileset(tiles, path):
    # Pad to a multiple of 1 row of 16 tiles for a tidy sheet.
    cols = 16
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("P", (cols * 8, rows * 8), 0)
    sheet.putpalette(tiles[0].getpalette())
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 8, (i // cols) * 8))
    sheet.save(path)
    return len(tiles)


def write_tilemap(tilemap, path):
    # 32x32 GBA screen, unused rows are 0.
    data = bytearray(32 * 32 * 2)
    for y, row in enumerate(tilemap):
        for x, tid in enumerate(row):
            off = (y * 32 + x) * 2
            data[off] = tid & 0xFF
            data[off + 1] = (tid >> 8) & 0x03
    path.write_bytes(data)


def draw_cursor():
    img = Image.new("P", (32, 32), 0)
    pal = [(0, 0, 0), (255, 214, 90), (255, 236, 160)] + [(0, 0, 0)] * 13
    img.putpalette([c for rgb in pal for c in rgb] + [0] * (768 - 16 * 3))
    px = img.load()
    for i in range(32):
        for t in range(2):
            px[i, t] = 1
            px[i, 31 - t] = 1
            px[t, i] = 1
            px[31 - t, i] = 1
    # rounded corners
    for x, y in ((0, 0), (1, 0), (0, 1), (31, 0), (30, 0), (31, 1),
                 (0, 31), (1, 31), (0, 30), (31, 31), (30, 31), (31, 30)):
        px[x, y] = 0
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    menu = draw_menu()
    tiles, tilemap = extract_tiles(menu)
    n = write_tileset(tiles, OUT / "menu_tiles.png")
    write_tilemap(tilemap, OUT / "menu.bin")
    draw_cursor().save(OUT / "cursor.png")
    print(f"wrote {n} unique tiles, tilemap 32x32, cursor 32x32")


if __name__ == "__main__":
    main()
