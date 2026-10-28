#!/usr/bin/env python3
"""Build repeating 32x32 type-pattern cells for the starter-choose scrolling BG."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphics" / "starter_choose" / "type_bg"
TYPES_DIR = ROOT / "graphics" / "types"
ASSET_GROUND = Path(
    r"C:\Users\rrk27\.cursor\projects\d-Games-Roms-PokemonRomHacking-decomps-pokeemerald-expansion\assets\quetzal_groundbg-4cf6d84e-cc13-475f-8542-1115f9971cc6.png"
)

# Must match enum Type in include/constants/pokemon.h
TYPE_FILES = [
    "none", "normal", "fight", "flying", "poison", "ground", "rock", "bug",
    "ghost", "steel", "mystery", "fire", "water", "grass", "electric",
    "psychic", "ice", "dragon", "dark", "fairy", "stellar",
]

# fill, mid, highlight. Ground matches the ripped Quetzal cell.
TYPE_COLORS = {
    "none":     ((176, 176, 176), (200, 200, 200), (230, 230, 230)),
    "normal":   ((168, 164, 144), (216, 212, 192), (236, 232, 216)),
    "fight":    ((168, 112, 96),  (216, 152, 136), (236, 188, 172)),
    "flying":   ((128, 160, 192), (176, 200, 232), (216, 232, 248)),
    "poison":   ((144, 104, 168), (192, 152, 216), (220, 188, 236)),
    "ground":   ((198, 173, 90),  (222, 198, 140), (222, 222, 222)),
    "rock":     ((148, 132, 88),  (196, 180, 128), (220, 208, 168)),
    "bug":      ((140, 160, 72),  (188, 208, 112), (216, 228, 160)),
    "ghost":    ((120, 96, 152),  (168, 144, 200), (200, 180, 220)),
    "steel":    ((144, 152, 160), (192, 200, 208), (224, 228, 232)),
    "mystery":  ((176, 176, 176), (200, 200, 200), (230, 230, 230)),
    "fire":     ((184, 120, 72),  (232, 168, 112), (248, 208, 160)),
    "water":    ((96, 136, 184),  (144, 184, 232), (188, 216, 248)),
    "grass":    ((120, 164, 96),  (168, 212, 140), (204, 232, 180)),
    "electric": ((188, 172, 72),  (236, 220, 112), (248, 240, 176)),
    "psychic":  ((184, 104, 128), (232, 152, 176), (248, 196, 208)),
    "ice":      ((120, 176, 176), (168, 224, 224), (208, 240, 240)),
    "dragon":   ((88, 96, 168),   (136, 144, 216), (180, 188, 236)),
    "dark":     ((104, 88, 80),   (152, 136, 128), (188, 176, 168)),
    "fairy":    ((184, 128, 152), (232, 176, 200), (248, 212, 224)),
    "stellar":  ((152, 160, 184), (200, 208, 232), (228, 232, 244)),
}

ICON_WINDOWS = [(16, 0), (0, 16)]  # 16x16 quadrants that hold the type mark


def make_palette(fill, mid, hi):
    colors = [(0, 0, 0), fill, mid, hi] + [(0, 0, 0)] * 12
    pal = [c for rgb in colors for c in rgb]
    pal += [0] * (768 - len(pal))
    return pal


def load_ground_cell():
    src = Image.open(ASSET_GROUND).convert("RGB").crop((0, 0, 32, 32))
    fill, mid, hi = TYPE_COLORS["ground"]
    img = Image.new("P", (32, 32), 0)
    img.putpalette(make_palette(fill, mid, hi))
    px_src = src.load()
    px = img.load()
    remap = {fill: 1, mid: 2, hi: 3}
    for y in range(32):
        for x in range(32):
            px[x, y] = remap.get(px_src[x, y], 1)
    return img


def layout_without_icon(ground_cell):
    """Keep stripes + rounded frames; clear the mountain fill."""
    img = ground_cell.copy()
    px = img.load()
    for ox, oy in ICON_WINDOWS:
        for y in range(16):
            for x in range(16):
                if px[ox + x, oy + y] == 3:
                    px[ox + x, oy + y] = 1
    return img


def extract_type_glyph(name):
    path = TYPES_DIR / f"{name}.png"
    if not path.exists():
        return None
    # Left-side type mark only; skip the letters on the 32x16 badge.
    im = Image.open(path).convert("RGBA").crop((1, 1, 10, 15))
    return im


def stamp_glyph(cell, glyph):
    if glyph is None:
        return cell
    g = glyph.convert("RGBA")
    g.thumbnail((9, 9), Image.NEAREST)
    gw, gh = g.size
    gp = g.load()
    key_bg = gp[0, 0][:3]
    px = cell.load()
    for ox, oy in ICON_WINDOWS:
        sx = ox + (16 - gw) // 2
        sy = oy + (16 - gh) // 2 + 1
        for y in range(gh):
            for x in range(gw):
                r, gch, b, a = gp[x, y]
                if a < 128 or (r, gch, b) == key_bg:
                    continue
                luma = r * 0.3 + gch * 0.59 + b * 0.11
                px[sx + x, sy + y] = 3 if luma > 160 else 2
    return cell


def write_tilemap(path):
    data = bytearray(32 * 32 * 2)
    pal = 1 << 12  # BG palette slot 1
    for y in range(32):
        for x in range(32):
            tid = (x % 4) + (y % 4) * 4
            off = (y * 32 + x) * 2
            entry = tid | pal
            data[off] = entry & 0xFF
            data[off + 1] = (entry >> 8) & 0xFF
    path.write_bytes(data)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ground = load_ground_cell()
    ground.save(OUT / "ground.png")
    layout = layout_without_icon(ground)

    for name in TYPE_FILES:
        fill, mid, hi = TYPE_COLORS[name]
        if name == "ground":
            cell = ground
        else:
            cell = Image.new("P", (32, 32), 0)
            cell.putpalette(make_palette(fill, mid, hi))
            src = layout.load()
            dst = cell.load()
            for y in range(32):
                for x in range(32):
                    dst[x, y] = src[x, y]
            stamp_glyph(cell, extract_type_glyph(name))
            cell.putpalette(make_palette(fill, mid, hi))
        cell.save(OUT / f"{name}.png")

    write_tilemap(ROOT / "graphics" / "starter_choose" / "type_bg.bin")
    print(f"wrote {len(TYPE_FILES)} type BG cells to {OUT}")


if __name__ == "__main__":
    main()
