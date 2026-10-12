#!/usr/bin/env python3
"""Generates the assets for the HGSS Pokedex "sprites" page.

Outputs (both under graphics/pokedex/hgss/):
  - tileset_menu1.png: extended by 5 tiles (0xd0-0xd4) holding clean box corners
    and a clean box bottom edge. Existing tiles are left untouched.
  - tilemap_sprites_screen.bin: two header boxes (front / back) with the INFO tab
    highlighted and a bottom bar for the button hints.

Run from the repository root:
  python tools/pokedex_sprites_page/generate.py [--preview preview.png]
"""
import argparse
import struct
from pathlib import Path

from PIL import Image

HGSS = Path("graphics/pokedex/hgss")
TILESET = HGSS / "tileset_menu1.png"
PALETTE = HGSS / "palette_default.pal"
TILEMAP_OUT = HGSS / "tilemap_sprites_screen.bin"

TILES_PER_ROW = 16
FIRST_NEW_TILE = 0xD0
WHITE = "11111111"
GRAY = "33333333"

MAP_W = 32
MAP_H = 21
VISIBLE_COLS = 30

# New tile ids
T_BL, T_BOTTOM_LINE, T_BOTTOM_PLAIN, T_BR, T_TR = range(FIRST_NEW_TILE, FIRST_NEW_TILE + 5)

# Layout (tile coordinates)
TOP_ROW = 2
BOTTOM_ROW = 17
BOX_A = (0, 14)
BOX_B = (15, 29)


def read_tile(pixels, tile_id):
    tx, ty = (tile_id % TILES_PER_ROW) * 8, (tile_id // TILES_PER_ROW) * 8
    return [[pixels[tx + x, ty + y] for x in range(8)] for y in range(8)]


def make_rows(*rows):
    return [[int(c, 16) for c in row] for row in rows]


def build_tileset():
    src = Image.open(TILESET)
    width, height = src.size
    assert width == 128 and height in (104, 112), f"unexpected tileset size {src.size}"
    px = src.load()

    # Source tiles (all < 0xd0, so unaffected by the extension)
    bl_src = read_tile(px, 0xAA)    # bottom-left of upper box + top-left of lower box
    line_src = read_tile(px, 0xA6)  # same, with a grid line pixel
    plain_src = read_tile(px, 0xA7)
    br_src = read_tile(px, 0xAB)
    tr_src = read_tile(px, 0x93)    # top-right corner

    new_tiles = [
        bl_src[:3] + make_rows(GRAY, GRAY, WHITE, WHITE, WHITE),
        line_src[:5] + make_rows(WHITE, WHITE, WHITE),
        plain_src[:5] + make_rows(WHITE, WHITE, WHITE),
        br_src[:3] + make_rows(GRAY, GRAY, WHITE, WHITE, WHITE),
        [[1 if v == 4 else v for v in row] for row in tr_src],  # drop the stray grid line pixels
    ]

    dst = Image.new("P", (128, 112), 0)
    dst.putpalette(src.getpalette())
    dst.paste(src.crop((0, 0, 128, 104)), (0, 0))
    dp = dst.load()
    for i, tile in enumerate(new_tiles):
        tid = FIRST_NEW_TILE + i
        for y in range(8):
            for x in range(8):
                dp[(tid % TILES_PER_ROW) * 8 + x, (tid // TILES_PER_ROW) * 8 + y] = tile[y][x]
    dst.save(TILESET, bits=4)

    # Make sure the original tiles are untouched
    check = Image.open(TILESET).load()
    assert all(check[x, y] == px[x, y] for y in range(104) for x in range(128))


def load_tilemap(name):
    data = (HGSS / name).read_bytes()
    return list(struct.unpack(f"<{len(data) // 2}H", data))


def build_tilemap():
    info = load_tilemap("tilemap_info_screen.bin")
    out = [0] * (MAP_W * MAP_H)

    def put(r, c, t):
        out[r * MAP_W + c] = t

    # Rows 0-1: tab bar with INFO highlighted
    for r in range(2):
        for c in range(MAP_W):
            out[r * MAP_W + c] = info[r * MAP_W + c]

    # Background grid (same pattern the info page uses)
    for r in range(2, 20):
        for c in range(VISIBLE_COLS):
            vline = (c - 1) % 3 == 0
            if r == 2:
                t = 0x3C if vline else 0x3B
            elif (r - 4) % 3 == 0:
                t = 0x47 if vline else 0x46
            else:
                t = 0x42 if vline else 0x41
            put(r, c, t)

    def box(c0, c1):
        # Top edge
        put(TOP_ROW, c0, 0x90)
        for c in range(c0 + 1, c1):
            put(TOP_ROW, c, 0x91 if c % 3 == 1 else 0x92)
        put(TOP_ROW, c1, T_TR)
        # Red header band and the pink line below it
        for r, (left, mid, right) in {3: (0x9A, 0x07, 0x9B), 4: (0x9F, 0xA0, 0xA1)}.items():
            put(r, c0, left)
            for c in range(c0 + 1, c1):
                put(r, c, mid)
            put(r, c1, right)
        # White body
        for r in range(5, BOTTOM_ROW):
            put(r, c0, 0x462 if (r - 4) % 3 == 0 else 0x460)
            for c in range(c0 + 1, c1):
                put(r, c, 0x41)
            put(r, c1, 0x99)
        # Bottom edge
        put(BOTTOM_ROW, c0, T_BL)
        for c in range(c0 + 1, c1):
            put(BOTTOM_ROW, c, T_BOTTOM_LINE if c % 3 == 1 else T_BOTTOM_PLAIN)
        put(BOTTOM_ROW, c1, T_BR)

    box(*BOX_A)
    box(*BOX_B)

    # Button hint bar (rows 18-19, 20 tiles wide, matches WIN_NAVIGATION_BUTTONS)
    put(18, 0, 0xC9)
    put(19, 0, 0xCD)
    for i, c in enumerate(range(1, 19)):
        put(18, c, (0xC4, 0xC5, 0xC5)[i % 3])
        put(19, c, (0x8C4, 0x8C5, 0x8C5)[i % 3])
    put(18, 19, 0xCA)
    put(19, 19, 0xCE)

    TILEMAP_OUT.write_bytes(struct.pack(f"<{len(out)}H", *out))


def load_palette():
    parts = PALETTE.read_text().split()
    count = int(parts[2])
    return [tuple(int(v) for v in parts[3 + i * 3:6 + i * 3]) for i in range(count)]


def render_preview(path, scale=3):
    palette = load_palette()
    tileset = Image.open(TILESET)
    px = tileset.load()
    data = TILEMAP_OUT.read_bytes()
    entries = struct.unpack(f"<{len(data) // 2}H", data)
    img = Image.new("RGB", (VISIBLE_COLS * 8, MAP_H * 8))
    for r in range(MAP_H):
        for c in range(VISIBLE_COLS):
            e = entries[r * MAP_W + c]
            tid, hflip, vflip = e & 0x3FF, e & 0x400, e & 0x800
            tx, ty = (tid % TILES_PER_ROW) * 8, (tid // TILES_PER_ROW) * 8
            for y in range(8):
                for x in range(8):
                    sx = 7 - x if hflip else x
                    sy = 7 - y if vflip else y
                    idx = px[tx + sx, ty + sy]
                    img.putpixel((c * 8 + x, r * 8 + y), palette[idx] if idx < len(palette) else (255, 0, 255))
    img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", help="also render a PNG preview of the page layout")
    args = parser.parse_args()

    build_tileset()
    build_tilemap()
    if args.preview:
        render_preview(args.preview)
    print(f"wrote {TILESET} and {TILEMAP_OUT}")


if __name__ == "__main__":
    main()
