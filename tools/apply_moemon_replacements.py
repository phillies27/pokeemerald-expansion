#!/usr/bin/env python3
"""Apply replacement sprite sheets from "Moemon Database/Sprite sets/Replacements/Gen N".

Replacement sheets are named NNNNX.png (X = A-Z). Each one replaces the sprite of the base
species with national dex number NNNN (the same species apply_moemon_sprites.py wrote for the
"1 - MAIN" sheet), overwriting its front/back/palette/shiny palette files.

Special cases (see OVERRIDES / SUBFOLDERS below):
    * 0666B.png is the Meadow Vivillon, not the first Vivillon entry the dex lookup would find
    * Gen 6/Vivillon_0666B/0666B-<Pattern>.png are the other Vivillon patterns

Default is a dry run. Use --apply to write.

    python tools/apply_moemon_replacements.py --gen 1
    python tools/apply_moemon_replacements.py --gen 1 --apply
    python tools/apply_moemon_replacements.py --gen 5 --skip-sheet 0547B.png --apply
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_sprite_sheet import SheetError, convert_sheet, write_result  # noqa: E402
import apply_moemon_sprites as base  # noqa: E402

ROOT = base.ROOT
DEFAULT_SOURCE = os.path.join(ROOT, "Moemon Database", "Sprite sets", "Replacements")

# sheet name -> species it replaces (instead of the dex number's base species)
OVERRIDES = {
    "0666B.png": "SPECIES_VIVILLON_MEADOW",
}

# Replacement sheets of the plain "NNNNA" (female) art of the gendered pairs that have a separate
# "_Male" sheet in the database (checked visually against NNNNA / NNNNA_Male):
#   sheet -> (species, role); role "female" = that species' frontPicFemale/... graphics,
#   role "main" = the species entry itself (a separate female species).
FEMALE_OVERRIDES = {
    "0593B.png": ("SPECIES_JELLICENT", "female"),
    "0902B.png": ("SPECIES_BASCULEGION_F", "main"),
}

# (generation, subfolder) -> {file stem: species}; sheets are named "<prefix>-<Pattern>.png"
_VIV = {"Archipelago": "ARCHIPELAGO", "Continental": "CONTINENTAL", "Elegant": "ELEGANT",
        "Fancy": "FANCY", "Garden": "GARDEN", "HighPlains": "HIGH_PLAINS", "IcySnow": "ICY_SNOW",
        "Jungle": "JUNGLE", "Marine": "MARINE", "Modern": "MODERN", "Monsoon": "MONSOON",
        "Ocean": "OCEAN", "PokeBal": "POKEBALL", "Polar": "POLAR", "River": "RIVER",
        "Sandstorm": "SANDSTORM", "Savanna": "SAVANNA", "Sun": "SUN", "Tundra": "TUNDRA"}
SUBFOLDERS = {
    (6, "Vivillon_0666B"): {"0666B-%s" % k: "SPECIES_VIVILLON_" + v for k, v in _VIV.items()},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, required=True, choices=sorted(base.GEN_FOLDERS))
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="'Replacements' folder (default: %(default)s)")
    ap.add_argument("--only", help="comma separated dex numbers to process")
    ap.add_argument("--exclude", help="comma separated dex numbers to skip (logged as skipped)")
    ap.add_argument("--skip-sheet", help="comma separated sheet file names to ignore, e.g. 0547B.png "
                    "(use to pick one of several replacements for the same dex number)")
    ap.add_argument("--apply", action="store_true", help="write files (default is a dry run)")
    ap.add_argument("--report", default=os.path.join(ROOT, "sprite_import_report.md"))
    args = ap.parse_args()

    folder = os.path.join(args.source, "Gen %d" % args.gen)
    if not os.path.isdir(folder):
        sys.exit("source folder not found: %s" % folder)
    only = {int(x) for x in args.only.split(",")} if args.only else None
    exclude = {int(x) for x in args.exclude.split(",")} if args.exclude else set()
    skip_sheets = set(args.skip_sheet.split(",")) if args.skip_sheet else set()

    dex_numbers = base.load_dex_numbers()
    syms = base.load_graphics_symbols()
    species = base.load_species(dex_numbers)
    by_species = {}
    for e in base.iter_entries(dex_numbers):
        by_species.setdefault(e["species"], e)

    ok, failed, skipped = [], [], []

    def run(label, sheet_path, sp):
        """Convert one sheet and write it to the graphics of species entry sp."""
        if not sp or not all(sp[k] for k in ("front", "back", "pal", "shiny")):
            failed.append((label, "no species/graphics symbols found"))
            return
        paths = {k: syms.get(sp[k]) for k in ("front", "back", "pal", "shiny")}
        if not all(paths.values()):
            failed.append((label, "graphics path not found for %s" % sp["species"]))
            return
        missing = [p for p in paths.values() if not os.path.exists(os.path.join(ROOT, p))]
        if missing:
            failed.append((label, "target file missing: %s" % ", ".join(missing)))
            return
        try:
            result = convert_sheet(sheet_path)
        except SheetError as e:
            failed.append((label, str(e)))
            return
        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        ok.append((label, sp["species"], paths, is_anim, result))
        if args.apply:
            write_result(result,
                         os.path.join(ROOT, paths["front"]), os.path.join(ROOT, paths["back"]),
                         os.path.join(ROOT, paths["pal"]), os.path.join(ROOT, paths["shiny"]),
                         anim=is_anim)

    seen = {}
    for name in sorted(os.listdir(folder)):
        sub = SUBFOLDERS.get((args.gen, name))
        if sub and os.path.isdir(os.path.join(folder, name)):
            for fn in sorted(os.listdir(os.path.join(folder, name))):
                stem = os.path.splitext(fn)[0]
                label = "%s/%s" % (name, fn)
                if fn in skip_sheets:
                    skipped.append((label, "skipped by --skip-sheet"))
                elif fn in os.listdir(folder):
                    skipped.append((label, "identical copy of %s (already applied)" % fn))
                elif stem not in sub:
                    skipped.append((label, "not mapped to a species"))
                elif sub[stem] not in by_species:
                    failed.append((label, "species not found: %s" % sub[stem]))
                else:
                    m = re.match(r"(\d{4})", stem)
                    if only and int(m.group(1)) not in only:
                        continue
                    if int(m.group(1)) in exclude:
                        skipped.append((label, "excluded (held back, see notes in report)"))
                        continue
                    run(label, os.path.join(folder, name, fn), by_species[sub[stem]])
            continue
        m = re.fullmatch(r"(\d{4})([A-Z])\.png", name)
        if not m:
            skipped.append((name, "does not match NNNNX.png"))
            continue
        dex = int(m.group(1))
        if name in skip_sheets:
            skipped.append((name, "skipped by --skip-sheet (another replacement for dex %d was chosen)" % dex))
            continue
        if only and dex not in only:
            continue
        if dex in exclude:
            skipped.append((name, "excluded (held back, see notes in report)"))
            continue
        if dex in seen:
            failed.append((name, "dex %d already has a replacement (%s); not applied" % (dex, seen[dex])))
            continue
        seen[dex] = name
        if name in FEMALE_OVERRIDES:
            target, role = FEMALE_OVERRIDES[name]
            sp = by_species.get(target)
            if sp and role == "female":
                sp = dict(sp, front=sp["front_f"], back=sp["back_f"], pal=sp["pal_f"],
                          shiny=sp["shiny_f"], species=sp["species"] + " (female graphics)")
        elif name in OVERRIDES:
            sp = by_species.get(OVERRIDES[name])
        else:
            sp = species.get(dex)
        run(name, os.path.join(folder, name), sp)

    verb = "WROTE" if args.apply else "would write"
    for name, spc, paths, is_anim, result in ok:
        warn = ("  [%s]" % "; ".join(result["warnings"])) if result["warnings"] else ""
        print("%-10s -> %-28s %s %s (%d colours)%s" % (
            name, spc, os.path.dirname(paths["front"]).replace("graphics/pokemon/", ""),
            os.path.basename(paths["front"]), result["colours_used"], warn))
    print()
    for name, why in failed:
        print("FAILED  %s: %s" % (name, why))
    for name, why in skipped:
        print("skipped %s: %s" % (name, why))
    print("\n%s %d species, %d failed, %d skipped%s" % (
        verb, len(ok), len(failed), len(skipped), "" if args.apply else "  (dry run; add --apply to write)"))

    base.write_report(args.report, "Replacements: Gen %d" % args.gen, args.apply, ok, failed, skipped)
    print("report updated: %s" % args.report)
    if args.apply:
        base.record_state([x for x in ok if "(female graphics)" not in x[1]])
        import sprite_checklist
        sprite_checklist.generate()
        print("checklist updated: sprite_checklist.md")


if __name__ == "__main__":
    main()
