#!/usr/bin/env python3
"""Build a LoRA training set (kohya_ss layout) from the Moemon sprites already in this repo.

Only species recorded in sprite_import_state.json as imported from a Moemon sheet are used (AI-made
sprites are skipped, so the LoRA never learns from its own output). Normal colours only - shinies are
never exported. Every picture is the 64x64 sprite upscaled with nearest-neighbour onto a plain white
background (default 512x512, SD 1.5's native size), with a caption .txt next to it.

Selection
    --gen 1                 primary generation(s): comma separated, e.g. 1 or 1,2
    --count 100             how many base species to take from the primary generation(s)
    --forms 10              plus this many forms (Megas, regional forms, Gmax, ...) from the same generations
    --extra-gens 3,5,8,9    fill-ins from other generations for variety (base species and forms mixed)
    --extra-count 15        how many fill-ins in total (spread over --extra-gens)
    --back-ratio 0.3        share of the images that are back views (back sprites are the hard part)
    --seed 1                the pick is random but repeatable
    --only 25,26,6          instead of sampling, use exactly these national dex numbers (primary gens ignored)
    --exclude 150,151       never use these dex numbers

Output (default build/lora_dataset/)
    <repeats>_moemon/NAME_front.png + .txt, NAME_back.png + .txt   <- point kohya's "train data dir" at build/lora_dataset
    manifest.csv            what was selected, with source files
    contact_sheet.png       everything on one page for a quick visual check (drop sprites you dislike by
                            deleting their .png and .txt)

Captions are generated from the species name, view and the sprite's dominant colours. They are a starting
point: hand-editing them (hair colour, clothes, accessories) is the biggest quality gain.

Examples
    python tools/make_lora_dataset.py --gen 1 --dry-run
    python tools/make_lora_dataset.py --gen 1 --count 100 --forms 10 --extra-gens 3,5,8,9 --extra-count 15
    python tools/make_lora_dataset.py --only 25,26,133 --back-ratio 0.4 --out build/pikachu_set
"""

import argparse
import colorsys
import csv
import os
import random
import re
import sys
from collections import Counter

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_moemon_sprites as ams  # noqa: E402
import sprite_checklist as chk  # noqa: E402

TILE = 64


def colour_name(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
    h *= 360
    if v < 0.22:
        return "black"
    if s < 0.14:
        return "white" if v > 0.82 else "gray"
    if h >= 345 or h < 15:
        return "red" if v > 0.45 else "dark red"
    if h < 45:
        return "orange" if v > 0.6 else "brown"
    if h < 70:
        return "yellow" if v > 0.6 else "brown"
    if h < 165:
        return "green"
    if h < 195:
        return "teal"
    if h < 255:
        return "blue"
    if h < 290:
        return "purple"
    return "pink"


def load_sprite(path, top_only=True):
    """Indexed sprite png -> (RGB image 64x64 with white background, list of opaque RGB pixels)."""
    im = Image.open(path)
    if im.mode != "P":
        raise ValueError("not an indexed png: %s" % path)
    if top_only and im.size[1] > TILE:
        im = im.crop((0, 0, TILE, TILE))
    pal = im.getpalette()
    idx = list(im.tobytes())
    out = Image.new("RGB", im.size, (255, 255, 255))
    px = [(255, 255, 255) if i == 0 else tuple(pal[3 * i:3 * i + 3]) for i in idx]
    out.putdata(px)
    return out, [p for i, p in zip(idx, px) if i != 0]


def dominant_colours(pixels, n=3):
    counts = Counter(colour_name(p) for p in pixels)
    for skip in ("black", "gray"):
        counts.pop(skip, None)
    total = sum(counts.values()) or 1
    return [c for c, k in counts.most_common(n) if k / total >= 0.08]


def form_label(e, base_species, stem):
    if e["species"] == base_species:
        return ""
    form = e["species"][len(stem):].strip("_") if e["species"].startswith(stem) else e["species"]
    return form.replace("_", " ").lower()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gen", default="1", help="primary generation(s), comma separated (default 1)")
    ap.add_argument("--count", type=int, default=100, help="base species from the primary generation(s) (default 100)")
    ap.add_argument("--forms", type=int, default=10, help="additional forms from the primary generation(s) (default 10)")
    ap.add_argument("--extra-gens", default="", help="generations for variety fill-ins, e.g. 3,5,8,9")
    ap.add_argument("--extra-count", type=int, default=15, help="total fill-ins (default 15)")
    ap.add_argument("--back-ratio", type=float, default=0.3, help="share of back-view images (default 0.3)")
    ap.add_argument("--only", help="exact national dex numbers instead of sampling, e.g. 25,26,133")
    ap.add_argument("--exclude", default="", help="dex numbers never to use")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--size", type=int, default=512, help="output size, multiple of 64 (default 512)")
    ap.add_argument("--trigger", default="moemon sprite", help="caption prefix / trigger words (default: moemon sprite)")
    ap.add_argument("--repeats", type=int, default=1, help="kohya repeats, the N in the N_moemon folder (default 1)")
    ap.add_argument("--out", default=os.path.join(ams.ROOT, "build", "lora_dataset"))
    ap.add_argument("--append", action="store_true",
                    help="grow an existing export: keep its files, never re-pick species already in it, "
                         "and add the newly selected ones (use a different --count for the NEW images)")
    ap.add_argument("--dry-run", action="store_true", help="print the selection only; write nothing")
    args = ap.parse_args()
    if args.size % TILE:
        ap.error("--size must be a multiple of 64")

    ints = lambda s: [int(x) for x in s.split(",") if x.strip()]  # noqa: E731
    gens, extra_gens, exclude = ints(args.gen), ints(args.extra_gens), set(ints(args.exclude))
    rng = random.Random(args.seed)

    dex_numbers = ams.load_dex_numbers()
    syms = ams.load_graphics_symbols()
    entries = ams.load_all_species(dex_numbers)
    base_entries = ams.load_species(dex_numbers)
    base_of = {d: e["species"] for d, e in base_entries.items()}
    stem_of = {d: "SPECIES_" + e["dexconst"][len("NATIONAL_DEX_"):] for d, e in base_entries.items()}
    state = ams.load_state()

    def paths(e):
        f, b = syms.get(e["front"] or ""), syms.get(e["back"] or "")
        if not f or not b:
            return None
        f, b = os.path.join(ams.ROOT, f), os.path.join(ams.ROOT, b)
        return (f, b) if os.path.exists(f) and os.path.exists(b) else None

    folder = os.path.join(args.out, "%d_moemon" % args.repeats)
    manifest_path = os.path.join(args.out, "manifest.csv")
    old_rows, already = [], set()
    if args.append and os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8", newline="") as f:
            old_rows = list(csv.reader(f))[1:]
        already = {r[1] for r in old_rows}
        print("append mode: %d images from %d species already in %s" % (len(old_rows), len(already), args.out))

    # Moemon-sourced entries only (state value = source sheet name; AI sprites are tagged "AI: ...").
    pool = []
    seen_front = set()
    for e in entries:
        src = state.get(e["species"])
        if not src or src.startswith("AI:") or e["dex"] in exclude or not paths(e) or e["front"] in seen_front:
            continue
        if e["species"] in already:
            continue
        seen_front.add(e["front"])
        pool.append(e)

    def is_base(e):
        return e["species"] == base_of.get(e["dex"])

    gen_of = chk.gen_of
    chosen = []
    if args.only:
        wanted = set(ints(args.only))
        chosen = [e for e in pool if e["dex"] in wanted and is_base(e)]
        missing = wanted - {e["dex"] for e in chosen}
        if missing:
            print("note: no Moemon base sprite for dex %s" % ", ".join(map(str, sorted(missing))))
    else:
        main_pool = [e for e in pool if gen_of(e["dex"]) in gens]
        bases = [e for e in main_pool if is_base(e)]
        forms = [e for e in main_pool if not is_base(e)]
        chosen += rng.sample(bases, min(args.count, len(bases)))
        chosen += rng.sample(forms, min(args.forms, len(forms)))
        if extra_gens and args.extra_count > 0:
            per = max(1, args.extra_count // len(extra_gens))
            for g in extra_gens:
                gp = [e for e in pool if gen_of(e["dex"]) == g and e not in chosen]
                chosen += rng.sample(gp, min(per, len(gp)))
    if not chosen:
        sys.exit("nothing selected (is sprite_import_state.json present, and do the generations have Moemon sprites?)")
    chosen.sort(key=lambda e: (e["dex"], not is_base(e)))

    n_front = len(chosen)
    n_back = min(n_front, round(n_front * args.back_ratio / max(1e-6, 1 - args.back_ratio)))
    back_set = {e["species"] for e in rng.sample(chosen, n_back)}
    n_images = n_front + n_back

    print("selected %d species -> %d images (%d front, %d back)" % (n_front, n_images, n_front, n_back))
    by_gen = Counter(gen_of(e["dex"]) for e in chosen)
    print("  by generation:", ", ".join("gen %s: %d" % (g, by_gen[g]) for g in sorted(by_gen)))
    print("  forms included: %d" % sum(not is_base(e) for e in chosen))
    if args.dry_run:
        for e in chosen:
            print("  #%04d %-28s%s" % (e["dex"], e["species"], "  +back" if e["species"] in back_set else ""))
    total_images = n_images + len(old_rows)
    spe = total_images * args.repeats
    epochs = max(1, round(2000 / spe))
    print("training plan: %d images%s x %d repeats = %d image-steps per epoch; ~%d epochs gives ~2000 image-steps"
          % (total_images, " (incl. %d existing)" % len(old_rows) if old_rows else "", args.repeats, spe, epochs))
    if args.dry_run:
        print("\ndry run: nothing written")
        return

    os.makedirs(folder, exist_ok=True)
    if not args.append:
        for fn in os.listdir(folder):  # keep the set reproducible: remove an older export
            if fn.endswith((".png", ".txt")):
                os.remove(os.path.join(folder, fn))

    rows = []
    for e in chosen:
        fpath, bpath = paths(e)
        base_name = e["name"] or e["species"][8:].title()
        label = form_label(e, base_of.get(e["dex"]), stem_of.get(e["dex"], "SPECIES_"))
        title = ("%s %s" % (base_name, label)).strip()
        views = [("front", fpath, "front view, full body")]
        if e["species"] in back_set:
            views.append(("back", bpath, "back view, battle back sprite, close-up"))
        for view, p, view_text in views:
            img, opaque = load_sprite(p, top_only=True)
            cols = dominant_colours(opaque)
            caption = ", ".join([args.trigger, "pixel art", view_text, title]
                                + (["%s colors" % " and ".join(cols)] if cols else [])
                                + ["white background"])
            name = "%04d_%s_%s" % (e["dex"], re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_"), view)
            big = img.resize((args.size, args.size), Image.Resampling.NEAREST)
            big.save(os.path.join(folder, name + ".png"))
            with open(os.path.join(folder, name + ".txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(caption + "\n")
            rows.append([name, e["species"], view, os.path.relpath(p, ams.ROOT).replace("\\", "/"), caption])

    all_rows = old_rows + rows
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "species", "view", "source", "caption"])
        w.writerows(all_rows)

    # contact sheet of everything currently in the folder (so hand-deleted images disappear from it)
    files = sorted(fn for fn in os.listdir(folder) if fn.endswith(".png"))
    cols_n = 12
    rows_n = (len(files) + cols_n - 1) // cols_n
    sheet = Image.new("RGB", (cols_n * 130, max(1, rows_n) * 130), (255, 255, 255))
    for i, fn in enumerate(files):
        t = Image.open(os.path.join(folder, fn)).convert("RGB")
        sheet.paste(t.resize((128, 128), Image.Resampling.NEAREST), ((i % cols_n) * 130, (i // cols_n) * 130))
    sheet.save(os.path.join(args.out, "contact_sheet.png"))

    print("\nwrote %d new images + captions to %s (%d in the folder now)" % (len(rows), folder, len(files)))
    print("manifest: %s" % os.path.join(args.out, "manifest.csv"))
    print("contact sheet: %s" % os.path.join(args.out, "contact_sheet.png"))
    print("In kohya_ss set 'Image folder' to %s (the folder that CONTAINS %d_moemon)." % (args.out, args.repeats))


if __name__ == "__main__":
    main()
