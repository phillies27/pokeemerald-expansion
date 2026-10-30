"""Build graphics/starter_choose/menu.bin from menu_tiles.png using 9-slice frames."""
from pathlib import Path
from PIL import Image
import struct

ROOT = Path(__file__).resolve().parents[1]
SHEET = Image.open(ROOT / "graphics" / "starter_choose" / "menu_tiles.png")
OUT_BIN = ROOT / "graphics" / "starter_choose" / "menu.bin"
PREVIEW = Path(
    r"C:\Users\rrk27\.cursor\projects\d-Games-Roms-PokemonRomHacking-decomps-pokeemerald-expansion\assets\matched_preview.png"
)

HFLIP = 1 << 10
VFLIP = 1 << 11
BLANK = 53

TW = SHEET.size[0] // 8
tiles_rgb = []
for i in range(TW * (SHEET.size[1] // 8)):
    x, y = (i % TW) * 8, (i // TW) * 8
    tiles_rgb.append(SHEET.crop((x, y, x + 8, y + 8)).convert("RGB"))

tm = [BLANK] * (32 * 32)


def put(x, y, tile):
    if 0 <= x < 32 and 0 <= y < 32:
        tm[y * 32 + x] = tile


def fill_row(y, x0, x1, tile):
    for x in range(x0, x1):
        put(x, y, tile)


def stamp_box(x, y, w, h, tl, top, left, fill):
    """9-slice. Right/bottom/corners are H/V flips of left/top/tl."""
    for ty in range(h):
        for tx in range(w):
            if ty == 0 and tx == 0:
                t = tl
            elif ty == 0 and tx == w - 1:
                t = tl | HFLIP
            elif ty == h - 1 and tx == 0:
                t = tl | VFLIP
            elif ty == h - 1 and tx == w - 1:
                t = tl | HFLIP | VFLIP
            elif ty == 0:
                t = top
            elif ty == h - 1:
                t = top | VFLIP
            elif tx == 0:
                t = left
            elif tx == w - 1:
                t = left | HFLIP
            else:
                t = fill
            put(x + tx, y + ty, t)


# Header / footer are 2 tiles tall with a 1-tile gap, matching the TMC layout.
fill_row(0, 0, 30, 1)
put(0, 0, 0)
fill_row(1, 0, 30, 3)
put(0, 1, 2)

fill_row(18, 0, 30, 3)
put(0, 18, 2 | VFLIP)
fill_row(19, 0, 30, 1)
put(0, 19, 0 | VFLIP)

# 3x3 icon cells: 5x5 with shared 1-tile borders -> 13x13 at (2,3)
CELL = 5
GRID_X, GRID_Y = 2, 3
for row in range(3):
    for col in range(3):
        stamp_box(GRID_X + col * (CELL - 1), GRID_Y + row * (CELL - 1), CELL, CELL, 6, 7, 12, 13)

# Shared interior borders: vertical 31, horizontal 26, crosses 25.
for row in range(3):
    for col in (1, 2):
        bx = GRID_X + col * (CELL - 1)
        by = GRID_Y + row * (CELL - 1)
        for ty in range(1, CELL - 1):
            put(bx, by + ty, 31)
        put(bx, by, 25)
        put(bx, by + CELL - 1, 25 | VFLIP)
for col in range(3):
    for row in (1, 2):
        bx = GRID_X + col * (CELL - 1)
        by = GRID_Y + row * (CELL - 1)
        for tx in range(1, CELL - 1):
            put(bx + tx, by, 26)
        put(bx, by, 25)
        put(bx + CELL - 1, by, 25 | HFLIP)
# four inner crosses
for row in (1, 2):
    for col in (1, 2):
        put(GRID_X + col * (CELL - 1), GRID_Y + row * (CELL - 1), 27)

# Preview panel
PX, PY, PW, PH = 17, 3, 11, 14
stamp_box(PX, PY, PW, PH, 10, 11, 14, 17)

# Pokeball watermark, inset from the frame. Preview fill is already tile 17.
ball = [
    [20, 21, 22, 23, 21 | HFLIP],
    [36, 37, 38, 37 | HFLIP, 36 | HFLIP],
    [39, 40, 41, 40 | HFLIP, 39 | HFLIP],
    [38 | VFLIP, 42, 42, 42 | HFLIP, 38 | HFLIP | VFLIP],
]
for by, row in enumerate(ball):
    for bx, t in enumerate(row):
        put(PX + 3 + bx, PY + 2 + by, t)

# Name bar (2 rows) and type bar (2 rows) at the bottom of the preview.
fill_row(PY + PH - 4, PX + 1, PX + PW - 1, 49)
put(PX + 1, PY + PH - 4, 48)
put(PX + PW - 2, PY + PH - 4, 48 | HFLIP)
fill_row(PY + PH - 3, PX + 1, PX + PW - 1, 3)
put(PX + 1, PY + PH - 3, 2)
put(PX + PW - 2, PY + PH - 3, 2 | HFLIP)
fill_row(PY + PH - 2, PX + 1, PX + PW - 1, 51)
put(PX + 1, PY + PH - 2, 50)
put(PX + PW - 2, PY + PH - 2, 50 | HFLIP)

preview = Image.new("RGB", (256, 160))
for i, entry in enumerate(tm[: 32 * 20]):
    idx = entry & 0x3FF
    tile = tiles_rgb[idx]
    if entry & HFLIP:
        tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
    if entry & VFLIP:
        tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
    x, y = (i % 32) * 8, (i // 32) * 8
    if x < 240:
        preview.paste(tile, (x, y))
preview.save(PREVIEW)
OUT_BIN.write_bytes(struct.pack("<1024H", *tm))
print("wrote", OUT_BIN)
print("preview", PREVIEW)
