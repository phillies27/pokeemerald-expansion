#!/usr/bin/env python3
"""Apply the sheets of "Moemon Database/Sprite sets/Replacements 2/Gen N".

Sheet names are  NNNN[(Tag)...]-V.png :

    NNNN   national dex number
    (Tag)  optional form tag(s): (M) (MX) (MY) Mega, (RA) Alola, (RG) Galar, (RH) Hisui,
           (GMAX) Gigantamax, (Fem) female graphics, plus named forms (see NAMED_FORMS)
    -V     version of the art; not part of the identity. If several versions of the same
           dex/tag exist in a folder, the highest one is applied and the others are reported.

Each sheet overwrites the front/back/palette/shiny palette files of the species it resolves to
(the base species for untagged sheets, so a palette-only change and a full redraw are handled the
same way). Sheets that do not follow the naming (Alts like "0738-2[Bunny].png", "NNNNA.png", ...)
or whose tag is not mapped yet are listed as skipped, never guessed.

Default is a dry run. Use --apply to write.

    python tools/apply_moemon_replacements2.py --gen 1
    python tools/apply_moemon_replacements2.py --gen 1 --apply
    python tools/apply_moemon_replacements2.py --gen 1 --only 6,25 --exclude 130 --apply
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_sprite_sheet import SheetError, convert_sheet, write_result  # noqa: E402
import apply_moemon_sprites as base  # noqa: E402

ROOT = base.ROOT
DEFAULT_SOURCE = os.path.join(ROOT, "Moemon Database", "Sprite sets", "Replacements 2")

# NNNN[(Tag)...][-V].png; a 3 digit dex number and a missing version (= 0) are tolerated.
NAME_RE = re.compile(r"(\d{3,4})((?:\([^)]*\))*)(?:-(\d+))?((?:\([^)]*\))*)\.png")

# Generic tags -> species constant suffix (the form entry must end with it).
SUFFIX_TAGS = {
    "M": "_MEGA", "Mega": "_MEGA", "MX": "_MEGA_X", "MY": "_MEGA_Y", "MZ": "_MEGA_Z",
    "RA": "_ALOLA", "RG": "_GALAR", "RH": "_HISUI", "RP": "_PALDEA",
    "GMAX": "_GMAX", "Gigantamax": "_GMAX", "G": "_GMAX", "P": "_PRIMAL",
}

# (dex, tag) -> species constant, for forms that do not follow a suffix rule.
NAMED_FORMS = {
    (25, "CosPHD"): "SPECIES_PIKACHU_PHD",
    (550, "Blue"): "SPECIES_BASCULIN_BLUE_STRIPED",
    (666, "Pok"): "SPECIES_VIVILLON_POKEBALL",
    (670, "B"): "SPECIES_FLOETTE_BLUE", (670, "E"): "SPECIES_FLOETTE_ETERNAL", (670, "O"): "SPECIES_FLOETTE_ORANGE",
    (670, "R"): "SPECIES_FLOETTE_RED", (670, "W"): "SPECIES_FLOETTE_WHITE", (670, "Y"): "SPECIES_FLOETTE_YELLOW",
    (671, "B"): "SPECIES_FLORGES_BLUE", (671, "O"): "SPECIES_FLORGES_ORANGE", (671, "R"): "SPECIES_FLORGES_RED",
    (671, "W"): "SPECIES_FLORGES_WHITE", (671, "Y"): "SPECIES_FLORGES_YELLOW",
    (678, "Masc"): "SPECIES_MEOWSTIC_M",
    (745, "Day"): "SPECIES_LYCANROC_MIDDAY", (745, "Night"): "SPECIES_LYCANROC_MIDNIGHT",
    (773, "Fight"): "SPECIES_SILVALLY_FIGHTING", (773, "Fly"): "SPECIES_SILVALLY_FLYING",
    (774, "R"): "SPECIES_MINIOR_CORE_RED", (774, "O"): "SPECIES_MINIOR_CORE_ORANGE",
    (774, "Y"): "SPECIES_MINIOR_CORE_YELLOW", (774, "G"): "SPECIES_MINIOR_CORE_GREEN",
    (774, "B"): "SPECIES_MINIOR_CORE_BLUE", (774, "I"): "SPECIES_MINIOR_CORE_INDIGO",
    (774, "V"): "SPECIES_MINIOR_CORE_VIOLET",
    (801, "O"): "SPECIES_MAGEARNA_ORIGINAL",
    (849, "Amp"): "SPECIES_TOXTRICITY_AMPED", (849, "Low"): "SPECIES_TOXTRICITY_LOW_KEY",
    (889, "Shield"): "SPECIES_ZAMAZENTA_CROWNED",
    (585, "Fall"): "SPECIES_DEERLING_AUTUMN",
    (586, "Fall"): "SPECIES_SAWSBUCK_AUTUMN",
}

FEMALE_TAG = "Fem"


DETAIL_RE = re.compile(r"(\w+) sheet pixel \(x=(\d+), y=(\d+)\): has RGB (\([^)]*\)) but should be RGB (\([^)]*\))")


def summarize_details(details, max_list=40):
    """Group pixel notes by (tile, current RGB, wanted RGB); sheet coordinates, raw RGB values."""
    groups = {}
    for d in details:
        m = DETAIL_RE.match(d)
        if not m:
            groups.setdefault(("?", d, ""), [])
            continue
        groups.setdefault((m.group(1), m.group(4), m.group(5)), []).append((int(m.group(2)), int(m.group(3))))
    parts = []
    for (tile, cur, want), pts in groups.items():
        if tile == "?":
            parts.append(cur)
            continue
        pts.sort(key=lambda p: (p[1], p[0]))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        head = "%s: %d px RGB %s -> %s" % (tile, len(pts), cur, want)
        if len(pts) <= max_list:
            parts.append("%s at sheet (x, y) %s" % (head, ", ".join("(%d, %d)" % p for p in pts)))
        else:
            parts.append("%s; too many to list, they span sheet x %d-%d, y %d-%d (select all RGB %s inside "
                         "that tile)" % (head, min(xs), max(xs), min(ys), max(ys), cur))
    return " | ".join(parts)


def resolve(dex, tags, entries, species):
    """-> (species entry dict or None, female flag, error text or None)."""
    female = FEMALE_TAG in tags
    forms = [t for t in tags if t != FEMALE_TAG]
    if len(forms) > 1:
        return None, female, "more than one form tag %s" % forms
    if not forms:
        return species.get(dex), female, None
    tag = forms[0]
    if (dex, tag) in NAMED_FORMS:
        wanted = NAMED_FORMS[(dex, tag)]
        cands = [e for e in entries if e["species"] == wanted and e["dex"] == dex]
    elif tag in SUFFIX_TAGS:
        suf = SUFFIX_TAGS[tag]
        cands = [e for e in entries if e["dex"] == dex
                 and (e["species"].endswith(suf) or e["species"].endswith(suf + "_STANDARD"))]
    else:
        # unknown tag: a species of that dex number whose constant ends with _<TAG> (East, Wash, Origin, ...)
        suf = "_" + re.sub(r"[^A-Z0-9]+", "_", tag.upper())
        cands = [e for e in entries if e["dex"] == dex and e["species"].endswith(suf)]
        if not cands:
            return None, female, "tag (%s) is not mapped to a species yet" % tag
    if not cands:
        return None, female, "no species found for dex %d tag (%s)" % (dex, tag)
    # several species may legitimately share one graphic (Raticate Alola / Totem, ...)
    if len({c["front"] for c in cands}) != 1:
        return None, female, "dex %d tag (%s) matches several graphics: %s" % (
            dex, tag, ", ".join(c["species"] for c in cands))
    return cands[0], female, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, required=True, choices=sorted(base.GEN_FOLDERS))
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="'Replacements 2' folder (default: %(default)s)")
    ap.add_argument("--only", help="comma separated dex numbers to process")
    ap.add_argument("--exclude", help="comma separated dex numbers to skip (logged as skipped)")
    ap.add_argument("--skip-sheet", help="comma separated sheet file names to ignore")
    ap.add_argument("--use-sheet", help="comma separated sheet file names to prefer over the highest version")
    ap.add_argument("--fem-as-base", help="comma separated dex numbers whose (Fem) sheet replaces the "
                    "species' existing sprite (for species without a female graphics slot)")
    ap.add_argument("--lenient-sheet", help="comma separated sheet file names imported even if the shiny art "
                    "recolours one normal colour several ways (majority shiny colour wins, odd pixels are "
                    "flattened and listed in the report); exempt from --strict")
    ap.add_argument("--all-forms", help="comma separated dex numbers whose sheet is written to every form "
                    "of that species (forms with their own front/back files but one shared palette, e.g. 711)")
    ap.add_argument("--grab-palettes", help="comma separated dex numbers whose forms share one front/back "
                    "image: the best-fitting sheet's art is kept and the other forms only contribute their "
                    "palettes (odd pixels are flattened and reported)")
    ap.add_argument("--strict", action="store_true",
                    help="hold back (do not write) sheets with any pixel mismatch warning; the failure "
                         "entry lists the pixels so the art can be fixed")
    ap.add_argument("--apply", action="store_true", help="write files (default is a dry run)")
    ap.add_argument("--report", default=os.path.join(ROOT, "sprite_import_report.md"))
    args = ap.parse_args()

    section = "Gen %d" % args.gen
    folder = os.path.join(args.source, section)
    if not os.path.isdir(folder):
        sys.exit("source folder not found: %s" % folder)
    only = {int(x) for x in args.only.split(",")} if args.only else None
    exclude = {int(x) for x in args.exclude.split(",")} if args.exclude else set()
    skip_sheets = set(args.skip_sheet.split(",")) if args.skip_sheet else set()
    use_sheets = set(args.use_sheet.split(",")) if args.use_sheet else set()
    lenient_sheets = set(args.lenient_sheet.split(",")) if args.lenient_sheet else set()
    grab_dex = {int(x) for x in args.grab_palettes.split(",")} if args.grab_palettes else set()
    all_forms = {int(x) for x in args.all_forms.split(",")} if args.all_forms else set()
    fem_as_base = {int(x) for x in args.fem_as_base.split(",")} if args.fem_as_base else set()

    dex_numbers = base.load_dex_numbers()
    syms = base.load_graphics_symbols()
    species = base.load_species(dex_numbers)
    entries = list(base.iter_entries(dex_numbers))

    ok, failed, skipped = [], [], []
    jobs = []

    # group sheets by identity (dex + tags) so that older versions can be superseded
    groups = {}
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".png"):
            continue
        m = NAME_RE.fullmatch(name)
        if not m:
            skipped.append((name, "does not match NNNN[(Tag)]-V.png (alt/other naming)"))
            continue
        dex = int(m.group(1))
        tags = tuple(re.findall(r"\(([^)]*)\)", m.group(2) + (m.group(4) or "")))
        groups.setdefault((dex, tags), []).append((int(m.group(3) or 0), name))

    for (dex, tags), versions in sorted(groups.items()):
        versions.sort()
        chosen = next((n for _, n in versions if n in use_sheets), versions[-1][1])
        for _, n in versions:
            if n != chosen:
                skipped.append((n, "superseded by %s (same dex/tag, other version)" % chosen))
        name = chosen
        if only and dex not in only:
            continue
        if name in skip_sheets:
            skipped.append((name, "skipped by --skip-sheet"))
            continue
        if dex in exclude:
            skipped.append((name, "excluded (held back, see notes in report)"))
            continue

        sp, female, err = resolve(dex, tags, entries, species)
        if err:
            (skipped if "not mapped" in err else failed).append((name, err))
            continue
        if not sp:
            failed.append((name, "no species found for dex %d" % dex))
            continue
        if female:
            if dex in fem_as_base:
                pass  # the (Fem) sheet replaces the species' only sprite (no female slot is created)
            elif not sp["front_f"]:
                skipped.append((name, "%s has no separate female graphics to put it in "
                                      "(use --fem-as-base %d to replace its sprite)" % (sp["species"], dex)))
                continue
            else:
                sp = dict(sp, front=sp["front_f"], back=sp["back_f"], pal=sp["pal_f"],
                          shiny=sp["shiny_f"], species=sp["species"] + " (female graphics)")
        if not all(sp[k] for k in ("front", "back", "pal", "shiny")):
            failed.append((name, "no graphics symbols found for %s" % sp["species"]))
            continue
        paths = {k: syms.get(sp[k]) for k in ("front", "back", "pal", "shiny")}
        if not all(paths.values()):
            failed.append((name, "graphics path not found for %s" % sp["species"]))
            continue
        missing = [p for p in paths.values() if not os.path.exists(os.path.join(ROOT, p))]
        if missing:
            failed.append((name, "target file missing: %s" % ", ".join(missing)))
            continue
        try:
            lenient = name in lenient_sheets
            result = convert_sheet(os.path.join(folder, name), lenient=lenient)
        except SheetError as e:
            failed.append((name, str(e)))
            continue

        if args.strict and name not in lenient_sheets:
            bad = [w for w in result["warnings"] if w != "colours snapped to 15-bit"]
            if bad:
                shown = summarize_details(result["details"])
                failed.append((name, "held back (--strict): %s%s" % ("; ".join(bad), (" -- " + shown) if shown else "")))
                continue

        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        if not female:
            # other species that use the same files get the art too; list them (state/checklist only)
            also = [e["species"] for e in entries
                    if e["species"] != sp["species"] and e["front"] == sp["front"]]
        else:
            also = []
        jobs.append({"name": name, "sp": sp, "paths": paths, "is_anim": is_anim, "result": result,
                     "also": also, "female": female})
        if dex in all_forms and not female:
            # the same sheet also goes to every other form of this dex number (own front/back files)
            for e in entries:
                if e["dex"] != dex or e["species"] == sp["species"] or e["front"] == sp["front"]:
                    continue
                if any(t in e["species"] for t in ("_MEGA", "_GMAX", "_PRIMAL")):
                    continue
                p2 = {k: syms.get(e[k]) for k in ("front", "back", "pal", "shiny")}
                if not all(p2.values()):
                    failed.append((name, "graphics path not found for %s" % e["species"]))
                    continue
                jobs.append({"name": name, "sp": e, "paths": p2,
                             "is_anim": os.path.basename(p2["front"]).startswith("anim_front"),
                             "result": result, "also": [], "female": False})

    # Forms that share one front/back file but have their own palettes (Floette colours, ...): the
    # sheets may index their colours differently, so build one common index image (the common
    # refinement of all sheets) and give every form a palette in that index order.
    # two different sheets that end up in the very same front + palette files cannot both be right
    by_target = {}
    for j in jobs:
        by_target.setdefault((j["paths"]["front"], j["paths"]["pal"]), set()).add(j["name"])
    clash = {n for names_ in by_target.values() if len(names_) > 1 for n in names_}
    for n in sorted(clash):
        failed.append((n, "another sheet writes to the very same front/palette files (%s); the game has one "
                          "graphic for these forms, so only one of the sheets can be used (pick one with "
                          "--skip-sheet)" % "; ".join(sorted(
                              x for names_ in by_target.values() if n in names_ for x in names_ if x != n))))
    jobs = [j for j in jobs if j["name"] not in clash]
    by_front = {}
    for j in jobs:
        by_front.setdefault(j["paths"]["front"], []).append(j)
    final = []
    for front, group in by_front.items():
        names = {j["name"] for j in group}
        if len(names) < 2:
            final.extend(group)
            continue
        have_pal = {j["paths"]["pal"] for j in group}
        missing = [s for j in group for s in j["also"]
                   if not any(g["sp"]["species"] == s for g in group)
                   and next(e["pal"] for e in entries if e["species"] == s) is not None
                   and syms.get(next(e["pal"] for e in entries if e["species"] == s)) not in have_pal]
        if missing:
            for n in sorted(names):
                failed.append((n, "shares front/back files with %s, which have their own palettes but no sheet "
                                  "in this folder; they would be left with a palette that no longer matches "
                                  "(add sheets for them)" % ", ".join(sorted(set(missing)))))
            continue
        if group[0]["sp"]["dex"] in grab_dex:
            # "palette grab": keep the index image of the sheet that loses least; every other form only
            # contributes its palette (per base index the form's majority colour); odd pixels are flattened
            best = None
            for bi, bj in enumerate(group):
                total, notes = 0, []
                pals = []
                for j in group:
                    pal, shiny, lost = [None] * 16, [None] * 16, 0
                    cnt = {}
                    for part in ("front_idx", "back_idx"):
                        for a, b in zip(bj["result"][part], j["result"][part]):
                            cnt.setdefault(a, {}).setdefault(b, 0)
                            cnt[a][b] += 1
                    for a, v in cnt.items():
                        top = max(v, key=lambda k: (v[k], -k))
                        pal[a] = j["result"]["palette"][top]
                        shiny[a] = j["result"]["shiny_palette"][top]
                        lost += sum(v.values()) - v[top]
                    pals.append((pal, shiny, lost))
                    total += lost
                if best is None or total < best[0]:
                    best = (total, bi, pals)
            total, bi, pals = best
            bj0 = group[bi]
            for j, (pal, shiny, lost) in zip(group, pals):
                r = dict(j["result"])
                r.update(front_idx=bj0["result"]["front_idx"], back_idx=bj0["result"]["back_idx"],
                         palette=[p or (0, 0, 0) for p in pal], shiny_palette=[p or (0, 0, 0) for p in shiny],
                         colours_used=bj0["result"]["colours_used"])
                r["warnings"] = list(j["result"]["warnings"]) + [
                    "palette grabbed onto the art of %s%s" % (bj0["name"], (
                        "; %d pixel(s) of this form's art flattened to the base art's colour grouping" % lost)
                        if lost else "")]
                final.append(dict(j, result=r))
            continue
        classes, new_front, new_back, bad = {(0,) * len(group): 0}, {}, {}, None
        for part, store in (("front_idx", new_front), ("back_idx", new_back)):
            n_px = len(group[0]["result"][part])
            lists = [j["result"][part] for j in group]
            store["idx"] = []
            for i in range(n_px):
                key = tuple(l[i] for l in lists)
                if any(k == 0 for k in key) and not all(k == 0 for k in key):
                    bad = "transparent in one sheet but not in another at %s pixel %d" % (part, i)
                    break
                if key not in classes:
                    classes[key] = len(classes)
                store["idx"].append(classes[key])
            if bad:
                break
        if bad or len(classes) > 16:
            why = bad or ("the sheets of these forms together need %d palette entries (max 16 incl. "
                          "transparent)" % len(classes))
            for n in sorted(names):
                failed.append((n, "shares front/back files with other forms; %s" % why))
            continue
        for j in group:
            pos = [g["name"] for g in group].index(j["name"])
            r = dict(j["result"])
            pal = [None] * 16
            shiny = [None] * 16
            for key, c in classes.items():
                pal[c] = j["result"]["palette"][key[pos]]
                shiny[c] = j["result"]["shiny_palette"][key[pos]]
            pal = [p or (0, 0, 0) for p in pal]
            shiny = [p or (0, 0, 0) for p in shiny]
            r.update(front_idx=new_front["idx"], back_idx=new_back["idx"], palette=pal, shiny_palette=shiny,
                     colours_used=len(classes))
            r["warnings"] = list(j["result"]["warnings"]) + ["common index image with %d other form sheet(s)"
                                                              % (len(names) - 1)]
            final.append(dict(j, result=r))

    for j in final:
        name, sp, paths, is_anim, result = j["name"], j["sp"], j["paths"], j["is_anim"], j["result"]
        ok.append((name, sp["species"], paths, is_anim, result))
        ok.extend((name, s, paths, is_anim, result) for s in j["also"])
        if args.apply:
            write_result(result,
                         os.path.join(ROOT, paths["front"]), os.path.join(ROOT, paths["back"]),
                         os.path.join(ROOT, paths["pal"]), os.path.join(ROOT, paths["shiny"]),
                         anim=is_anim)

    verb = "WROTE" if args.apply else "would write"
    for name, spc, paths, is_anim, result in ok:
        warn = ("  [%s]" % "; ".join(result["warnings"])) if result["warnings"] else ""
        print("%-22s -> %-34s %s %s (%d colours)%s" % (
            name, spc, os.path.dirname(paths["front"]).replace("graphics/pokemon/", ""),
            os.path.basename(paths["front"]), result["colours_used"], warn))
    print()
    for name, why in failed:
        print("FAILED  %s: %s" % (name, why))
    for name, why in skipped:
        print("skipped %s: %s" % (name, why))
    print("\n%s %d species, %d failed, %d skipped%s" % (
        verb, len(ok), len(failed), len(skipped), "" if args.apply else "  (dry run; add --apply to write)"))

    base.write_report(args.report, "Replacements 2: %s" % section, args.apply, ok, failed, skipped)
    print("report updated: %s" % args.report)
    if args.apply:
        base.record_state([x for x in ok if "(female graphics)" not in x[1]])
        import sprite_checklist
        sprite_checklist.generate()
        print("checklist updated: sprite_checklist.md")


if __name__ == "__main__":
    main()
