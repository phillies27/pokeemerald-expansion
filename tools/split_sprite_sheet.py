#!/usr/bin/env python3
"""Split a 256x64 sprite sheet into pokeemerald-expansion graphics files.

Sheet layout (left to right, each tile 64x64), configurable with --order:
    front, front-shiny, back, back-shiny

Outputs (into the output directory):
    front.png        64x64  indexed, 16 colours, index 0 = transparent
    anim_front.png   64x128 (only with --anim; the same frame twice = no animation)
    back.png         64x64  indexed, same palette as the front sprite
    normal.pal       JASC palette, 16 entries
    shiny.pal        JASC palette, same index order as normal.pal

GBA / Emerald limits that are checked:
    * every tile is 64x64
    * a single front/back palette of at most 16 colours (index 0 = transparent)
    * colours are 15-bit (RGB555); colours are snapped to multiples of 8 and a
      note is printed if that changes anything
    * the shiny front is pixel-aligned with the normal front, so a normal->shiny
      colour mapping can be derived without ambiguity
    * back sprites only use colours that exist in the front sprites' palette

Usage:
    python tools/split_sprite_sheet.py SHEET.png OUTDIR [--anim] [--bg R,G,B]
                                       [--order front,front_shiny,back,back_shiny]

The conversion is also importable (see apply_moemon_sprites.py):
    result = convert_sheet(path)       # raises SheetError on any problem
    write_result(result, front_path, back_path, pal_path, shiny_path, anim=True)
"""

import argparse
import os
import sys
from collections import Counter, defaultdict

from PIL import Image

TILE = 64
MAX_STRAY_PIXELS = 4  # per normal colour: shiny pixels that disagree with the majority recolour
DEFAULT_ORDER = ["front", "front_shiny", "back", "back_shiny"]


class SheetError(Exception):
    pass


def snap555(c):
    # GBA stores 5 bits per channel; the repo's tools expand with <<3.
    return tuple((v >> 3) << 3 for v in c)


def pixels(img):
    return list(img.get_flattened_data()) if hasattr(img, "get_flattened_data") else list(img.getdata())


def write_pal(path, colors):
    with open(path, "w", newline="\n") as f:
        f.write("JASC-PAL\n0100\n16\n")
        for c in colors:
            f.write("%d %d %d\n" % c)


def save_indexed(path, size, idx_data, colors):
    img = Image.new("P", size)
    flat = [v for c in colors for v in c]
    img.putpalette(flat + [0] * (768 - len(flat)))
    img.putdata(idx_data)
    # bits=4 makes Pillow write a 4bpp PNG (what the game graphics use).
    img.save(path, bits=4, optimize=False)


def convert_sheet(sheet_path, order=None, bg=None, lenient=False):
    """Validate a sheet and return its converted data. Raises SheetError.

    lenient=True does not fail when a normal colour is recoloured several ways in the shiny sprite:
    the majority shiny colour is used for the whole colour ("flattening" the odd shiny pixels)."""
    order = order or DEFAULT_ORDER
    if sorted(order) != sorted(DEFAULT_ORDER):
        raise SheetError("order must be a permutation of front,front_shiny,back,back_shiny")

    sheet = Image.open(sheet_path).convert("RGBA")
    if sheet.size != (TILE * 4, TILE):
        raise SheetError("sheet must be %dx%d, got %dx%d" % (TILE * 4, TILE, *sheet.size))

    warnings = []
    details = []  # per-pixel notes for the import report
    tiles = {}
    for i, name in enumerate(order):
        t = sheet.crop((i * TILE, 0, i * TILE + TILE, TILE))
        px = pixels(t)
        if any(a not in (0, 255) for *_, a in px):
            raise SheetError("%s has partially transparent pixels" % name)
        tiles[name] = px  # list of RGBA

    if not bg:
        # Most common opaque colour on the border of the front tile; the sprite can touch a corner,
        # so a single corner pixel is not reliable.
        ft = tiles["front"]
        border = [ft[y * TILE + x] for y in range(TILE) for x in range(TILE)
                  if x in (0, TILE - 1) or y in (0, TILE - 1)]
        bg = Counter(p[:3] for p in border if p[3] != 0).most_common(1)
        bg = bg[0][0] if bg else ft[0][:3]
    bg = snap555(bg)

    # RGBA -> snapped RGB, transparent pixels become the background colour.
    changed = False
    rgb = {}
    for name, px in tiles.items():
        out = []
        for r, g, b, a in px:
            if a == 0:
                out.append(bg)
            else:
                s = snap555((r, g, b))
                changed |= s != (r, g, b)
                out.append(s)
        rgb[name] = out
    if changed:
        warnings.append("colours snapped to 15-bit")

    # Helpers for messages: everything is reported as the RAW colour found in the sheet (what an
    # image editor shows) and as coordinates in the whole 256x64 sheet, not in the 64x64 tile.
    def where(name, i):
        return order.index(name) * TILE + i % TILE, i // TILE

    def raw(name, i):
        return tuple(tiles[name][i][:3])

    def raw_like(names, snapped):
        """Most common raw colour (in the given tiles) that snaps to `snapped`."""
        c = Counter(tuple(p[:3]) for n in names for p in tiles[n] if p[3] and snap555(p[:3]) == snapped)
        return c.most_common(1)[0][0] if c else snapped

    # Build normal palette from the front sprite, background first.
    fn, fs = rgb["front"], rgb["front_shiny"]
    palette = [bg]
    for c in fn:
        if c not in palette:
            palette.append(c)
    # Make sure the back sprite doesn't need extra colours.
    for c in rgb["back"]:
        if c not in palette:
            palette.append(c)
    if len(palette) > 16:
        front_set = set(fn) | {bg}
        back_only = [c for c in dict.fromkeys(rgb["back"]) if c not in front_set]
        lines = []
        for c in back_only:
            near = min(front_set, key=lambda o: sum((p - q) ** 2 for p, q in zip(c, o)))
            dist = sum((p - q) ** 2 for p, q in zip(c, near)) ** 0.5
            lines.append("back-only RGB %s (%d px) ~ front RGB %s (distance %.0f)" % (
                raw_like(["back"], c), rgb["back"].count(c), raw_like(["front"], near), dist))
        # closest colour pairs overall (merging a pair frees one slot); safe when both have the same shiny colour
        shiny_of = defaultdict(set)
        for n_, s_ in (("front", "front_shiny"), ("back", "back_shiny")):
            for a_, b_ in zip(rgb[n_], rgb[s_]):
                shiny_of[a_].add(b_)
        allc = list(palette)
        counts_all = Counter(fn) + Counter(rgb["back"])
        pairs = []
        for ia in range(len(allc)):
            for ib in range(ia + 1, len(allc)):
                d_ = sum((p - q) ** 2 for p, q in zip(allc[ia], allc[ib])) ** 0.5
                pairs.append((d_, allc[ia], allc[ib]))
        pairs.sort(key=lambda t: t[0])
        cand = ["RGB %s (%d px) + RGB %s (%d px), distance %.0f, %s" % (
            raw_like(["front", "back"], a_), counts_all[a_], raw_like(["front", "back"], b_), counts_all[b_], d_,
            "same shiny colour" if shiny_of[a_] == shiny_of[b_] and len(shiny_of[a_]) == 1 else "shiny colours differ")
            for d_, a_, b_ in pairs[:8]]
        raise SheetError("front+back share one palette: %d colours incl. transparent (max 16, need to remove %d); "
                         "the front alone uses %d, %d colours appear only on the back. Merge colours "
                         "(recolour one to the other in the normal AND the shiny tiles where used). "
                         "Back-only colours: %s. Closest colour pairs overall: %s"
                         % (len(palette), len(palette) - 16, len(front_set), len(back_only),
                            "; ".join(lines) or "none", "; ".join(cand)))

    # Derive shiny palette from the pixel-aligned front sprites.
    mapping = defaultdict(Counter)
    for a, b in zip(fn, fs):
        mapping[a][b] += 1
    shiny = {}
    stray = 0
    conflicts = []  # every normal colour that is recoloured inconsistently (all reported at once)
    for a, counts in mapping.items():
        if len(counts) > 1:
            # A palette can only recolour a colour one way. Tolerate a few stray pixels
            # (typos in the shiny art) by using the majority colour.
            ranked = counts.most_common()
            minority = sum(n for _, n in ranked[1:])
            if minority > MAX_STRAY_PIXELS:
                major = ranked[0][0]
                parts = []
                for k, n in ranked[1:]:
                    odd = [i for i, (x, y) in enumerate(zip(fn, fs)) if x == a and y == k]
                    parts.append("%d px that become RGB %s at front_shiny sheet (x, y) %s%s (the normal pixel is "
                                 "%d px further left)" % (
                                     n, raw_like(["front_shiny"], k),
                                     ", ".join("(%d, %d)" % where("front_shiny", i) for i in odd[:40]),
                                     " ... (%d more)" % (len(odd) - 40) if len(odd) > 40 else "", TILE))
                conflicts.append("normal front RGB %s: %d px become shiny RGB %s, but %s" % (
                    raw_like(["front"], a), ranked[0][1], raw_like(["front_shiny"], major), "; and ".join(parts)))
            stray += minority
        shiny[a] = counts.most_common(1)[0][0]
    if conflicts and not lenient:
        raise SheetError(
            "%d normal colour(s) are recoloured two ways in the shiny sprite, but a palette slot can only have one "
            "shiny colour. Fix: make the odd normal pixels a slightly different colour (needs a free palette slot) "
            "or give those front_shiny pixels the colour of the rest. %s" % (len(conflicts), " || ".join(conflicts)))
    if stray:
        warnings.append("%d stray shiny pixel(s) ignored (shiny recolour taken by majority)" % stray)
    if shiny[bg] != bg:
        warnings.append("shiny background differed from normal background; forced to match")
        shiny[bg] = bg
    if stray:
        for i, (a, b) in enumerate(zip(fn, fs)):
            if shiny[a] != b:
                details.append("front_shiny sheet pixel (x=%d, y=%d): has RGB %s but should be RGB %s "
                               "(the other shiny pixels of the same normal colour %s)"
                               % (*where("front_shiny", i), raw("front_shiny", i),
                                  raw_like(["front_shiny"], shiny[a]), raw("front", i)))
    # Colours only the back sprite uses: look them up by comparing back vs back_shiny.
    back_map = defaultdict(Counter)
    for a, b in zip(rgb["back"], rgb["back_shiny"]):
        back_map[a][b] += 1
    shiny_palette = []
    for c in palette:
        if c in shiny:
            shiny_palette.append(shiny[c])
        else:
            counts = back_map.get(c)
            if not counts or len(counts) > 1:
                raise SheetError("cannot determine the shiny colour for %s (only used on the back sprite)" % (c,))
            shiny_palette.append(next(iter(counts)))

    # Validate back shiny against the derived shiny palette.
    index = {c: i for i, c in enumerate(palette)}
    back_idx = [index[c] for c in rgb["back"]]
    mismatch = sum(1 for i, c in zip(back_idx, rgb["back_shiny"]) if shiny_palette[i] != c)
    if mismatch:
        warnings.append("%d back_shiny pixels do not match the shiny palette derived from the front sprite" % mismatch)
        for i, (k, c) in enumerate(zip(back_idx, rgb["back_shiny"])):
            if shiny_palette[k] != c:
                details.append("back_shiny sheet pixel (x=%d, y=%d): has RGB %s but should be RGB %s "
                               "(what the front sprite's shiny uses for this normal colour %s)"
                               % (*where("back_shiny", i), raw("back_shiny", i),
                                  raw_like(["front_shiny", "back_shiny"], shiny_palette[k]),
                                  raw("back", i)))

    used = len({index[c] for c in fn} | set(back_idx))

    # Pad palette to 16 entries so the file is always a full 16-colour palette.
    while len(palette) < 16:
        palette.append((0, 0, 0))
        shiny_palette.append((0, 0, 0))

    return {
        "bg": bg,
        "palette": palette,
        "shiny_palette": shiny_palette,
        "front_idx": [index[c] for c in fn],
        "back_idx": back_idx,
        "colours_used": used,
        "warnings": warnings,
        "details": details,
    }


def write_result(result, front_path, back_path, pal_path, shiny_path, anim=False):
    """Write front/back/palettes to explicit paths.

    With anim=True the front file is 64x128 holding the same frame twice (no sprite animation).
    """
    for p in (front_path, back_path, pal_path, shiny_path):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    pal = result["palette"]
    front = result["front_idx"]
    if anim:
        save_indexed(front_path, (TILE, TILE * 2), front + front, pal)
    else:
        save_indexed(front_path, (TILE, TILE), front, pal)
    save_indexed(back_path, (TILE, TILE), result["back_idx"], pal)
    write_pal(pal_path, pal)
    write_pal(shiny_path, result["shiny_palette"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("outdir")
    ap.add_argument("--anim", action="store_true", help="also write a 64x128 anim_front.png (frame duplicated)")
    ap.add_argument("--bg", help="background/transparent colour as R,G,B (default: top-left pixel of the sheet)")
    ap.add_argument("--order", default=",".join(DEFAULT_ORDER),
                    help="tile order in the sheet (default: %(default)s)")
    args = ap.parse_args()

    bg = tuple(int(x) for x in args.bg.split(",")) if args.bg else None
    try:
        result = convert_sheet(args.sheet, args.order.split(","), bg)
    except SheetError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
    for w in result["warnings"]:
        print("note:", w)

    out = args.outdir
    paths = (os.path.join(out, "back.png"), os.path.join(out, "normal.pal"), os.path.join(out, "shiny.pal"))
    write_result(result, os.path.join(out, "front.png"), *paths, anim=False)
    if args.anim:
        write_result(result, os.path.join(out, "anim_front.png"), *paths, anim=True)
    print("wrote files to %s (%d colours incl. transparent, background index 0 = %s)"
          % (args.outdir, result["colours_used"], result["bg"]))


if __name__ == "__main__":
    main()
