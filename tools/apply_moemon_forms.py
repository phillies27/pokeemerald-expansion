#!/usr/bin/env python3
"""Apply Moemon form sheets (Gigantamax, ...) to their own species entries in pokeemerald-expansion.

Sheets in the form folders are named "<dex>A_<tag>.png"; <tag> selects the species whose
natDexNum is <dex> and whose constant matches the folder's rule:

    Gigantamax   0012A_G.png  -> SPECIES_BUTTERFREE_GMAX   (the entry ending in _GMAX)

Same conversion rules, report and checklist handling as tools/apply_moemon_sprites.py.
Default is a dry run; add --apply to write.

    python tools/apply_moemon_forms.py --folder Gigantamax
    python tools/apply_moemon_forms.py --folder Gigantamax --apply
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_moemon_sprites as base  # noqa: E402
from split_sprite_sheet import SheetError, convert_sheet, write_result  # noqa: E402

# folder -> (sheet name regex, function(entry, tag) -> bool picking the species)
FOLDERS = {
    "Gigantamax": (r"(\d{4})A_(G)\.png", lambda e, tag: e["species"].endswith("_GMAX")),
    # _M / _MX / _MY / _MZ  (a few sheets omit the 'A': 0678_M, 0970_M)
    "Megas": (r"(\d{4})A?_(M[XYZ]?)\.png",
              lambda e, tag: e["species"].endswith("_MEGA" + ("_" + tag[1] if len(tag) > 1 else ""))),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, choices=sorted(FOLDERS))
    ap.add_argument("--source", default=base.DEFAULT_SOURCE)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--exclude", default="", help="comma separated sheet file names to leave out")
    ap.add_argument("--report", default=os.path.join(base.ROOT, "sprite_import_report.md"))
    args = ap.parse_args()

    folder = os.path.join(args.source, args.folder)
    if not os.path.isdir(folder):
        sys.exit("source folder not found: %s" % folder)
    pattern, picker = FOLDERS[args.folder]

    dex_numbers = base.load_dex_numbers()
    syms = base.load_graphics_symbols()
    entries = list(base.iter_entries(dex_numbers))

    excluded = {x.strip() for x in args.exclude.split(",") if x.strip()}
    ok, failed, skipped = [], [], []
    for name in sorted(os.listdir(folder)):
        m = re.fullmatch(pattern, name)
        if not m:
            skipped.append((name, "does not match the %s naming rule" % args.folder))
            continue
        if name in excluded:
            skipped.append((name, "held back by --exclude (see report notes)"))
            continue
        dex, tag = int(m.group(1)), m.group(2)
        cands = [e for e in entries if e["dex"] == dex and picker(e, tag)]
        # Several species may legitimately share one graphic (e.g. Meowstic M/F mega).
        if len({c["front"] for c in cands}) != 1:
            failed.append((name, "expected one matching graphic for dex %d, found %d species (%s)"
                           % (dex, len(cands), ", ".join(c["species"] for c in cands))))
            continue
        sp = cands[0]
        also = [c["species"] for c in cands[1:]]
        if not all(sp[k] for k in ("front", "back", "pal", "shiny")):
            failed.append((name, "no graphics symbols found for %s" % sp["species"]))
            continue
        paths = {k: syms.get(sp[k]) for k in ("front", "back", "pal", "shiny")}
        missing = [p for p in paths.values() if not p or not os.path.exists(os.path.join(base.ROOT, p))]
        if missing:
            failed.append((name, "target file missing for %s: %s" % (sp["species"], ", ".join(map(str, missing)))))
            continue
        try:
            result = convert_sheet(os.path.join(folder, name))
        except SheetError as e:
            failed.append((name, str(e)))
            continue
        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        ok.append((name, sp["species"], paths, is_anim, result))
        ok.extend((name, s, paths, is_anim, result) for s in also)  # state/checklist only; same files
        if args.apply:
            write_result(result,
                         os.path.join(base.ROOT, paths["front"]), os.path.join(base.ROOT, paths["back"]),
                         os.path.join(base.ROOT, paths["pal"]), os.path.join(base.ROOT, paths["shiny"]),
                         anim=is_anim)

    verb = "WROTE" if args.apply else "would write"
    for name, spc, paths, is_anim, result in ok:
        warn = ("  [%s]" % "; ".join(result["warnings"])) if result["warnings"] else ""
        print("%-14s -> %-30s %s (%d colours)%s" % (name, spc, paths["front"], result["colours_used"], warn))
    print()
    for name, why in failed:
        print("FAILED  %s: %s" % (name, why))
    for name, why in skipped:
        print("skipped %s: %s" % (name, why))
    print("\n%s %d species, %d failed, %d skipped%s" % (
        verb, len(ok), len(failed), len(skipped), "" if args.apply else "  (dry run; add --apply to write)"))

    base.write_report(args.report, args.folder, args.apply, ok, failed, skipped)
    print("report updated: %s" % args.report)
    if args.apply:
        base.record_state(ok)
        import sprite_checklist
        sprite_checklist.generate()
        print("checklist updated: sprite_checklist.md")


if __name__ == "__main__":
    main()
