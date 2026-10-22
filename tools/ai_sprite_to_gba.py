#!/usr/bin/env python3
"""Turn an AI-generated (or any hi-res) picture into GBA-ready Pokemon sprite files.

What it does to each picture
    1. removes the background (uses the alpha channel if there is one, otherwise flood-fills the
       colour found on the image border)
    2. crops to the subject, scales it to fit a 64x64 tile (area-averaging, no ringing) and places it
       bottom-centred like the Emerald sprites
    3. optionally adds a 1px dark outline (--outline) - AI art rarely has a clean one
    4. quantises front + back to ONE shared palette: 15 colours + transparent index 0 (4bpp), colours
       snapped to GBA 15-bit
    5. derives a shiny palette (hue shift, same index order, so the shiny needs no extra art)
    6. writes front/anim_front/back PNGs (4bpp indexed) and normal.pal / shiny.pal

Inputs
    FRONT            front-facing picture of the Pokemon
    --back BACK      picture of it seen from behind. Without it the species' existing back sprite is
                     re-coloured to the new palette (with --species), or the front is reused as a
                     placeholder (with --out).

Targets (pick one; --batch implies --species per file)
    --species SPECIES_X   write into graphics/pokemon/... exactly where that species already points
                          (resolved from the repo's own data, same as apply_moemon_sprites.py).
                          Dry run unless --apply is given. On --apply the species is recorded in
                          sprite_import_state.json and sprite_checklist.md / sprite_todo.md refresh.
    --out DIR             write front.png / back.png / normal.pal / shiny.pal (+ anim_front.png with --anim)
    --batch DIR           every DIR/*.png whose name is a species ("SPECIES_VENUSAUR_GMAX.png" or
                          "venusaur_gmax.png"); an optional "<name>_back.png" is its back sprite.

A preview PNG (front, shiny front, back, shiny back, 4x) and an optional 256x64 Moemon-style sheet
are written to <input dir>/gba_preview/ so you can check the result before --apply.

Examples
    python tools/ai_sprite_to_gba.py art/venusaur_gmax.png --back art/venusaur_gmax_back.png --species SPECIES_VENUSAUR_GMAX
    python tools/ai_sprite_to_gba.py art/venusaur_gmax.png --species venusaur_gmax --outline --apply
    python tools/ai_sprite_to_gba.py art/test.png --out build/test --anim --shiny-hue 200
    python tools/ai_sprite_to_gba.py --batch art/ --apply

Prompting tips for the image model (gets the best raw material)
    "Pokemon Emerald / Ruby-Sapphire style front sprite of <name>, clean pixel art, flat colours, no
     gradients, no shading dither, thick dark outline, plain solid white background, single character,
     centred, full body" - and a second prompt with "back view / seen from behind" for the back sprite.
    Plain solid backgrounds and flat colours convert much better than detailed or gradient art.
"""

import argparse
import colorsys
import os
import re
import sys
from collections import Counter

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_sprite_sheet as sss  # noqa: E402

TILE = sss.TILE
OL = "outline"  # sentinel pixel value for generated outline pixels
DEFAULT_BG = (144, 176, 176)  # index 0 colour; never shown in game (transparent)


class SpriteError(Exception):
    pass


# ----------------------------------------------------------------------------- source -> subject

def border_colour(rgb):
    w, h = rgb.size
    px = rgb.load()
    acc = {}
    pts = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    for x, y in pts:
        r, g, b = px[x, y]
        e = acc.setdefault((r >> 3, g >> 3, b >> 3), [0, 0, 0, 0])
        e[0] += 1
        e[1] += r
        e[2] += g
        e[3] += b
    n, r, g, b = max(acc.values(), key=lambda e: e[0])
    return (r // n, g // n, b // n)


def load_subject(path, args):
    """RGBA image whose alpha marks the Pokemon."""
    im = Image.open(path).convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 255:
        return im  # already has transparency
    if args.remove_bg == "none":
        return im
    rgb = im.convert("RGB")
    bg = args.bg_color or border_colour(rgb)
    tol = args.tolerance
    masks = [b.point(lambda v, c=c: 255 if abs(v - c) <= tol else 0) for b, c in zip(rgb.split(), bg)]
    near = ImageChops.darker(ImageChops.darker(masks[0], masks[1]), masks[2])  # 255 = looks like background
    if args.remove_bg == "flood":
        w, h = near.size
        px = near.load()
        seeds = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
        for x, y in seeds:
            if px[x, y] == 255:
                ImageDraw.floodfill(near, (x, y), 128)
        alpha = near.point(lambda v: 0 if v == 128 else 255)
    else:  # global: every pixel near the background colour, also enclosed holes
        alpha = near.point(lambda v: 0 if v == 255 else 255)
    for _ in range(args.erode):
        alpha = alpha.filter(ImageFilter.MinFilter(3))
    im.putalpha(alpha)
    return im


def fit_to_tile(subject, args, warnings, label):
    """-> list of 64*64 items: None (transparent), (r,g,b) or OL."""
    hard = subject.getchannel("A").point(lambda v: 255 if v >= args.alpha_threshold else 0)
    bbox = hard.getbbox()
    if not bbox:
        raise SpriteError("%s: nothing left after background removal (try --remove-bg none, "
                          "--bg-color R,G,B or a smaller --tolerance)" % label)
    crop = subject.crop(bbox)
    box = args.fit - (2 if args.outline else 0)
    scale = min(box / crop.width, box / crop.height)
    nw, nh = max(1, round(crop.width * scale)), max(1, round(crop.height * scale))
    if scale > 1:
        warnings.append("%s: subject is only %dx%d px, upscaled with nearest-neighbour; use a bigger source"
                        % (label, crop.width, crop.height))
        resample = Image.Resampling.NEAREST
    else:
        resample = {"box": Image.Resampling.BOX, "lanczos": Image.Resampling.LANCZOS,
                    "nearest": Image.Resampling.NEAREST}[args.resample]
    small = crop.resize((nw, nh), resample)

    margin = (TILE - args.fit) // 2
    x0 = (TILE - nw) // 2
    if args.align == "bottom":
        y0 = TILE - nh - margin - (1 if args.outline else 0)
    else:
        y0 = (TILE - nh) // 2
    x0, y0 = max(0, x0), max(0, y0)

    px = [None] * (TILE * TILE)
    src = small.load()
    for y in range(nh):
        for x in range(nw):
            r, g, b, a = src[x, y]
            if a >= args.alpha_threshold and x0 + x < TILE and y0 + y < TILE:
                px[(y0 + y) * TILE + x0 + x] = (r, g, b)

    if args.outline:
        add = []
        for y in range(TILE):
            for x in range(TILE):
                if px[y * TILE + x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < TILE and 0 <= ny < TILE and isinstance(px[ny * TILE + nx], tuple):
                        add.append(y * TILE + x)
                        break
        for i in add:
            px[i] = OL
    return px


def load_existing_back(path):
    """Existing indexed back.png -> same pixel format as fit_to_tile (index 0 = transparent)."""
    im = Image.open(path)
    if im.mode != "P" or im.size != (TILE, TILE):
        return None
    pal = im.getpalette()
    return [None if i == 0 else tuple(pal[3 * i:3 * i + 3]) for i in sss.pixels(im)]


# ----------------------------------------------------------------------------- palette

def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def quantize(cols, k):
    """Median-cut a list of RGB tuples down to at most k colours."""
    if not cols or k <= 0:
        return []
    uniq = Counter(cols)
    if len(uniq) <= k:
        return list(uniq)
    strip = Image.new("RGB", (len(cols), 1))
    strip.putdata(cols)
    q = strip.quantize(colors=k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    flat = q.getpalette()
    return [tuple(flat[3 * i:3 * i + 3]) for i in sorted(set(sss.pixels(q)))]


def dist(a, b):
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def make_palette(sources, budget, base=None, extra_k=4, thr=48):
    """-> list of (colour, shiny colour or None), darkest first.

    base = (normal colours, shiny colours) of an existing sprite. With it the palette is SEEDED: the
    base colours that the picture uses most are kept (so skin / hair / fur match the existing sprite and
    the canon shiny colours carry over), and only `extra_k` new colours are quantised for whatever the
    base can't express (a cap, a new accessory...)."""
    cols = [p for s in sources for p in s if isinstance(p, tuple)]
    if not cols:
        raise SpriteError("no opaque pixels to build a palette from")
    if base:
        bn, bs = base
        use = Counter()
        for c, n in Counter(cols).items():
            j = min(range(len(bn)), key=lambda i: dist(c, bn[i]))
            if dist(c, bn[j]) <= thr:
                use[j] += n
        keep = [j for j, _ in use.most_common(max(0, budget - extra_k))]
        kept = [bn[j] for j in keep]
        rest = [c for c in cols if not kept or min(dist(c, k) for k in kept) > thr]
        extra = quantize(rest, budget - len(kept))
        entries = [(bn[j], bs[j]) for j in keep] + [(c, None) for c in extra]
    else:
        entries = [(c, None) for c in quantize(cols, budget)]
    out, seen = [], set()
    for c, sh in sorted(((sss.snap555(c), sh) for c, sh in entries), key=lambda t: luma(t[0])):
        if c not in seen:
            seen.add(c)
            out.append((c, sh))
    return out


def to_indices(px, pal, outline_idx):
    cache = {}

    def nearest(c):
        if c not in cache:
            cache[c] = 1 + min(range(len(pal)), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, pal[i])))
        return cache[c]

    return [0 if p is None else outline_idx if p == OL else nearest(p) for p in px]


def shiny_palette(palette, outline_idx, hue, sat, val, fixed=None):
    fixed = fixed or {}
    out = []
    for i, c in enumerate(palette):
        if i == 0 or i == outline_idx:
            out.append(c)
            continue
        if i in fixed:  # shiny colour taken from the base sprite
            out.append(fixed[i])
            continue
        h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
        if s >= 0.12 and v >= 0.2:  # leave greys / near-black alone so outlines and whites stay put
            h = (h + hue / 360.0) % 1.0
            s = min(1.0, s * sat)
            v = min(1.0, v * val)
        out.append(sss.snap555(tuple(round(x * 255) for x in colorsys.hsv_to_rgb(h, s, v))))
    return out


# ----------------------------------------------------------------------------- preview

def render(idx, pal):
    im = Image.new("RGBA", (TILE, TILE))
    im.putdata([(0, 0, 0, 0) if i == 0 else tuple(pal[i]) + (255,) for i in idx])
    return im


def write_previews(res, directory, stem, write_sheet):
    os.makedirs(directory, exist_ok=True)
    tiles = [render(res["front_idx"], res["palette"]), render(res["front_idx"], res["shiny_palette"]),
             render(res["back_idx"], res["palette"]), render(res["back_idx"], res["shiny_palette"])]
    sheet = Image.new("RGBA", (TILE * 4, TILE), (0, 0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * TILE, 0))
    big = Image.new("RGBA", sheet.size, (96, 96, 112, 255))
    big.alpha_composite(sheet)
    big = big.resize((sheet.width * 4, sheet.height * 4), Image.Resampling.NEAREST)
    big.save(os.path.join(directory, stem + "_preview.png"))
    if write_sheet:
        sheet.save(os.path.join(directory, stem + "_sheet.png"))


# ----------------------------------------------------------------------------- conversion

def convert(front_path, back_path, existing_back, args, base=None):
    warnings = []
    front_px = fit_to_tile(load_subject(front_path, args), args, warnings, os.path.basename(front_path))
    quant_sources = [front_px]
    if back_path:
        back_px = fit_to_tile(load_subject(back_path, args), args, warnings, os.path.basename(back_path))
        quant_sources.append(back_px)
    elif existing_back:
        back_px = existing_back
        warnings.append("no --back given: the existing back sprite was re-coloured to the new palette "
                        "(shapes are still the old ones)")
    else:
        back_px = list(front_px)
        warnings.append("no --back given: the front sprite is used as a placeholder back sprite")

    budget = max(1, min(args.colors, 15)) - (1 if args.outline else 0)
    entries = make_palette(quant_sources, budget, base, args.extra_colors, args.base_threshold)
    pal = [c for c, _ in entries]
    outline_idx = len(pal) + 1 if args.outline else None
    palette = [sss.snap555(args.bg_index_color)] + pal
    if args.outline:
        palette.append(sss.snap555(args.outline_color))
    fixed = {i + 1: sh for i, (_, sh) in enumerate(entries) if sh is not None}
    shiny = shiny_palette(palette, outline_idx, args.shiny_hue, args.shiny_sat, args.shiny_val, fixed)
    if base:
        warnings.append("palette seeded from the base sprite: %d base colours kept (canon shiny colours carried "
                        "over), %d new colours" % (len(fixed), len(pal) - len(fixed)))
    front_idx = to_indices(front_px, pal, outline_idx)
    back_idx = to_indices(back_px, pal, outline_idx)
    used = len(set(front_idx) | set(back_idx))
    while len(palette) < 16:
        palette.append((0, 0, 0))
        shiny.append((0, 0, 0))
    return {"palette": palette, "shiny_palette": shiny, "front_idx": front_idx, "back_idx": back_idx,
            "colours_used": used, "warnings": warnings}


def read_pal(path):
    with open(path) as f:
        tok = f.read().split()
    n = int(tok[2])
    v = [int(x) for x in tok[3:3 + 3 * n]]
    return [tuple(v[3 * i:3 * i + 3]) for i in range(n)]


def load_base(spec, repo):
    """--base-palette: a normal.pal path or a species constant -> (normal, shiny) colour lists without index 0
    (unused all-black padding entries are dropped)."""
    if os.path.exists(spec):
        normal, shiny = spec, os.path.join(os.path.dirname(spec), "shiny.pal")
    else:
        paths = repo.paths(repo.resolve(spec))
        normal = os.path.join(repo.ams.ROOT, paths["pal"])
        shiny = os.path.join(repo.ams.ROOT, paths["shiny"])
    bn = read_pal(normal)[1:]
    bs = read_pal(shiny)[1:] if os.path.exists(shiny) else bn
    keep = [i for i, c in enumerate(bn) if c != (0, 0, 0)]
    return [bn[i] for i in keep], [bs[i] for i in keep]


# ----------------------------------------------------------------------------- repo targets

class Repo:
    def __init__(self):
        import apply_moemon_sprites as ams
        self.ams = ams
        dex = ams.load_dex_numbers()
        self.syms = ams.load_graphics_symbols()
        self.entries = ams.load_all_species(dex)
        self.by_species = {e["species"]: e for e in self.entries}

    def resolve(self, name):
        n = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).upper()
        if not n.startswith("SPECIES_"):
            n = "SPECIES_" + n
        if n not in self.by_species:
            close = [s for s in self.by_species if n[8:] in s][:8]
            raise SpriteError("unknown species %s%s" % (n, (" (similar: %s)" % ", ".join(close)) if close else ""))
        return self.by_species[n]

    def paths(self, entry):
        out = {}
        for k in ("front", "back", "pal", "shiny"):
            sym = entry.get(k)
            p = self.syms.get(sym) if sym else None
            if not p:
                raise SpriteError("%s has no graphics path for %s" % (entry["species"], k))
            out[k] = p
        return out

    def sharing(self, entry):
        return [e["species"] for e in self.entries
                if e["species"] != entry["species"] and e["front"] == entry["front"]]


def run_job(front, back, species, out_dir, stem, args, repo):
    existing_back = None
    paths = None
    entry = None
    if species:
        entry = repo.resolve(species)
        paths = repo.paths(entry)
        for p in paths.values():
            if not os.path.exists(os.path.join(repo.ams.ROOT, p)):
                raise SpriteError("target file missing: %s" % p)
        if not back:
            existing_back = load_existing_back(os.path.join(repo.ams.ROOT, paths["back"]))

    base = load_base(args.base_palette, repo) if args.base_palette else None
    res = convert(front, back, existing_back, args, base)
    pv_dir = args.preview_dir or os.path.join(os.path.dirname(os.path.abspath(front)), "gba_preview")
    write_previews(res, pv_dir, stem, args.write_sheet)

    print("%s: %d palette entries used incl. transparent%s" % (stem, res["colours_used"],
                                                                 "" if not entry else " -> " + entry["species"]))
    for w in res["warnings"]:
        print("  note:", w)
    print("  preview: %s" % os.path.join(pv_dir, stem + "_preview.png"))

    if entry:
        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        root = repo.ams.ROOT
        for k in ("front", "back", "pal", "shiny"):
            print("  %s %s%s" % ("WRITE" if args.apply else "would write", paths[k],
                                 " (64x128, frame duplicated)" if k == "front" and is_anim else ""))
        shared = repo.sharing(entry)
        if shared:
            print("  warning: the front sprite is shared with %s" % ", ".join(shared))
        if args.apply:
            sss.write_result(res, os.path.join(root, paths["front"]), os.path.join(root, paths["back"]),
                             os.path.join(root, paths["pal"]), os.path.join(root, paths["shiny"]), anim=is_anim)
    if out_dir:
        o = out_dir
        # --out is a scratch location, so it is written even during a dry run
        sss.write_result(res, os.path.join(o, "anim_front.png" if args.anim else "front.png"),
                         os.path.join(o, "back.png"), os.path.join(o, "normal.pal"),
                         os.path.join(o, "shiny.pal"), anim=args.anim)
        print("  wrote %s" % o)
    return entry


def collect_batch(folder):
    jobs = []
    for fn in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(fn)
        if ext.lower() != ".png" or stem.lower().endswith(("_back", "_preview", "_sheet")):
            continue
        back = os.path.join(folder, stem + "_back.png")
        jobs.append((os.path.join(folder, fn), back if os.path.exists(back) else None, stem, stem))
    return jobs


def parse_rgb(s):
    try:
        v = tuple(int(x) for x in s.split(","))
        assert len(v) == 3 and all(0 <= x <= 255 for x in v)
        return v
    except Exception:
        raise argparse.ArgumentTypeError("expected R,G,B (0-255)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("front", nargs="?", help="front-facing picture")
    ap.add_argument("--back", help="back-view picture")
    ap.add_argument("--species", help="species constant (SPECIES_X, or just x) to write into graphics/pokemon/")
    ap.add_argument("--out", help="write the files into this folder instead")
    ap.add_argument("--batch", help="folder of <species>.png (+ optional <species>_back.png)")
    ap.add_argument("--apply", action="store_true", help="write into the repo (default is a dry run)")
    ap.add_argument("--anim", action="store_true", help="--out: also name the front anim_front.png (64x128)")

    g = ap.add_argument_group("source / background")
    g.add_argument("--remove-bg", choices=["flood", "global", "none"], default="flood",
                   help="flood: remove background connected to the border (default); global: every pixel "
                        "near the background colour; none: use the picture as is. Ignored when the image "
                        "already has transparency.")
    g.add_argument("--bg-color", type=parse_rgb, help="source background colour R,G,B (default: border colour)")
    g.add_argument("--tolerance", type=int, default=36, help="per-channel background tolerance (default 36)")
    g.add_argument("--erode", type=int, default=0, help="shrink the subject mask N px at source size to kill halos")

    g = ap.add_argument_group("sprite")
    g.add_argument("--fit", type=int, default=60, help="max sprite size inside the 64x64 tile (default 60)")
    g.add_argument("--align", choices=["bottom", "center"], default="bottom")
    g.add_argument("--resample", choices=["box", "lanczos", "nearest"], default="box")
    g.add_argument("--alpha-threshold", type=int, default=128)
    g.add_argument("--colors", type=int, default=15, help="opaque colours incl. outline, max 15 (default 15)")
    g.add_argument("--base-palette", help="seed the palette from an existing sprite: a normal.pal path or a species "
                   "constant (e.g. SPECIES_PIKACHU). Keeps its skin/hair/fur colours and canon shiny, and only "
                   "quantises --extra-colors new ones. Best for variants of an existing Pokemon.")
    g.add_argument("--extra-colors", type=int, default=4, help="new colours allowed with --base-palette (default 4)")
    g.add_argument("--base-threshold", type=float, default=48.0, help="RGB distance within which a picture colour "
                   "counts as a base colour (default 48)")
    g.add_argument("--outline", action="store_true", help="add a 1px dark outline around the silhouette")
    g.add_argument("--outline-color", type=parse_rgb, default=(16, 16, 16))
    g.add_argument("--bg-index-color", type=parse_rgb, default=DEFAULT_BG,
                   help="colour stored in palette slot 0 (transparent in game; default %s)" % (DEFAULT_BG,))

    g = ap.add_argument_group("shiny")
    g.add_argument("--shiny-hue", type=float, default=120.0, help="hue shift in degrees (default 120)")
    g.add_argument("--shiny-sat", type=float, default=1.0, help="saturation multiplier")
    g.add_argument("--shiny-val", type=float, default=1.0, help="brightness multiplier")

    g = ap.add_argument_group("preview")
    g.add_argument("--preview-dir", help="default: <input dir>/gba_preview")
    g.add_argument("--write-sheet", action="store_true", help="also write a 256x64 Moemon-style sheet there")
    args = ap.parse_args()

    if not (args.front or args.batch):
        ap.error("give a FRONT picture or --batch DIR")
    if args.front and args.batch:
        ap.error("FRONT and --batch are mutually exclusive")
    if args.batch and (args.species or args.out or args.back):
        ap.error("--batch takes names from the files; do not combine it with --species/--out/--back")
    if args.front and not (args.species or args.out):
        ap.error("pick a target: --species SPECIES_X or --out DIR")

    if args.batch:
        jobs = [(f, b, s, st) for f, b, s, st in collect_batch(args.batch)]
        jobs = [(f, b, s, None, st) for f, b, s, st in jobs]
    else:
        stem = os.path.splitext(os.path.basename(args.front))[0]
        jobs = [(args.front, args.back, args.species, args.out, stem)]

    need_repo = any(j[2] for j in jobs) or (args.base_palette and not os.path.exists(args.base_palette))
    repo = Repo() if need_repo else None
    done, failed = [], []
    for front, back, species, out_dir, stem in jobs:
        try:
            entry = run_job(front, back, species, out_dir, stem, args, repo)
            if entry:
                done.append((os.path.basename(front), entry["species"]))
        except (SpriteError, OSError, sss.SheetError) as e:
            failed.append((stem, str(e)))
            print("FAILED  %s: %s" % (stem, e))

    if done and args.apply:
        repo.ams.record_state([("AI: " + name, spc) for name, spc in done])
        import sprite_checklist
        sprite_checklist.generate()
        print("\nrecorded %d species in sprite_import_state.json; sprite_checklist.md and sprite_todo.md refreshed"
              % len(done))
    elif done:
        print("\ndry run: nothing written to the repo; add --apply to write")
    if failed:
        print("%d failed" % len(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
