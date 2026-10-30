from pathlib import Path
from PIL import Image
import struct

ROOT = Path(__file__).resolve().parents[1]
SHEET = Image.open(ROOT / "graphics" / "starter_choose" / "menu_tiles.png")
CROP = Image.open(
    Path(r"C:\Users\rrk27\.cursor\projects\d-Games-Roms-PokemonRomHacking-decomps-pokeemerald-expansion\assets\crop_a.png")
).convert("RGB")
OUT_BIN = ROOT / "graphics" / "starter_choose" / "menu.bin"
PREVIEW = Path(
    r"C:\Users\rrk27\.cursor\projects\d-Games-Roms-PokemonRomHacking-decomps-pokeemerald-expansion\assets\matched_preview.png"
)

TW = SHEET.size[0] // 8
tiles = []
for i in range(TW * (SHEET.size[1] // 8)):
    x, y = (i % TW) * 8, (i // TW) * 8
    tiles.append(SHEET.crop((x, y, x + 8, y + 8)).convert("RGB"))


def variants(im):
    yield 0, im
    yield 1, im.transpose(Image.FLIP_LEFT_RIGHT)
    yield 2, im.transpose(Image.FLIP_TOP_BOTTOM)
    yield 3, im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)


# Compare only the inner 6x6 so TMC's dotted grid does not dominate.
def inner(data):
    out = []
    for y in range(1, 7):
        for x in range(1, 7):
            out.append(data[y * 8 + x])
    return out


varlist = []
for i, t in enumerate(tiles):
    for fl, v in variants(t):
        varlist.append((i, fl, inner(list(v.getdata()))))

SCALE = 12
OX, OY = 0, 0
COLS, ROWS = 32, 20


def match_cell(cx, cy):
    x0 = OX + cx * SCALE
    y0 = OY + cy * SCALE
    block = CROP.crop((x0, y0, x0 + SCALE, y0 + SCALE)).resize((8, 8), Image.BILINEAR)
    data = inner(list(block.getdata()))
    best = (10**18, 0, 0)
    for i, fl, td in varlist:
        dist = 0
        for a, b in zip(data, td):
            dist += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
            if dist >= best[0]:
                break
        else:
            # Prefer no-flip on ties so the bin stays simple.
            score = dist * 4 + fl
            if score < best[0]:
                best = (score, i, fl)
    return best[1], best[2], best[0]


map_entries = [0] * (32 * 32)
preview = Image.new("RGB", (256, 160))
for y in range(ROWS):
    ids = []
    for x in range(COLS):
        idx, fl, score = match_cell(x, y)
        entry = idx & 0x3FF
        if fl & 1:
            entry |= 1 << 10
        if fl & 2:
            entry |= 1 << 11
        map_entries[y * 32 + x] = entry
        tile = tiles[idx]
        if fl & 1:
            tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
        if fl & 2:
            tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
        if x < 30:
            preview.paste(tile, (x * 8, y * 8))
        flag = ""
        if fl & 1:
            flag += "H"
        if fl & 2:
            flag += "V"
        ids.append(f"{idx:02d}{flag}")
    print(f"{y:02d}", " ".join(ids[:30]))

preview.save(PREVIEW)
OUT_BIN.write_bytes(struct.pack("<1024H", *map_entries))
print("wrote", OUT_BIN)
