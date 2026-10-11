#!/usr/bin/env python3
"""Batch-apply Moemon 256x64 sprite sheets to pokeemerald-expansion species graphics.

For every sheet "NNNNA.png" in a generation folder, the species is located through
the repo's own data (so folder names always match this version of the expansion):

    include/constants/pokedex.h          NATIONAL_DEX_* order  -> dex number
    src/data/pokemon/species_info/*.h    [SPECIES_X] natDexNum, frontPic/backPic/palette symbols
    src/data/graphics/pokemon.h          symbol -> graphics file path

and the front/back/palette files that the species already uses are overwritten
(anim_front.png gets the same frame twice, i.e. no sprite animation).

Default is a dry run that only validates and prints the plan. Use --apply to write.

Examples:
    python tools/apply_moemon_sprites.py --gen 1
    python tools/apply_moemon_sprites.py --gen 1 --apply
    python tools/apply_moemon_sprites.py --gen 1 --only 1,4,6 --apply
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_sprite_sheet import SheetError, convert_sheet, write_result  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = os.path.join(ROOT, "Moemon Database", "Sprite sets", "1 - MAIN")

GEN_FOLDERS = {
    1: "1. Generation I", 2: "2. Generation II", 3: "3. Generation III",
    4: "4. Generation IV", 5: "5. Generation V", 6: "6. Generation VI",
    7: "7. Generation VII", 8: "8. Generation VIII", 9: "9. Generation IX",
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_dex_numbers():
    t = read(os.path.join(ROOT, "include", "constants", "pokedex.h"))
    i = t.index("enum NationalDexOrder")
    body = t[i:t.index("};", i)]
    names = re.findall(r"^\s*(NATIONAL_DEX_[A-Z0-9_]+),", body, re.M)
    if names[0] != "NATIONAL_DEX_NONE":
        raise RuntimeError("unexpected pokedex.h layout")
    return {n: k for k, n in enumerate(names)}  # NONE=0, BULBASAUR=1, ...


def load_graphics_symbols():
    """symbol -> first INCGFX path (the non-GBA-style branch is listed first in the file)."""
    t = read(os.path.join(ROOT, "src", "data", "graphics", "pokemon.h"))
    syms = {}
    for m in re.finditer(r"\b(gMon(?:FrontPic|BackPic|Palette|ShinyPalette)\w*)\[\]\s*=\s*INCGFX_U\d+\(\"([^\"]+)\"", t):
        syms.setdefault(m.group(1), m.group(2))
    return syms


SPECIES_INFO_FILES = os.path.join(ROOT, "src", "data", "pokemon", "species_info", "gen_*_families.h")


def split_args(s):
    """Split a macro argument list on top-level commas."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


_FIELDS = (".natDexNum", ".frontPic", ".speciesName", ".palette", ".backPic")


def collect_macros(texts):
    """Macros that (partly) define a species: name -> (params or None, body).
    params is None for object-like macros (e.g. MOTHIM_SPECIES_INFO)."""
    macros = {}
    pat = re.compile(r"^#define\s+(\w+)(\([^)]*\))?((?:[^\n]*\\\n)*[^\n]*)", re.M)
    for t in texts:
        for m in pat.finditer(t):
            body = m.group(3).replace("\\\n", "\n")
            if any(f in body for f in _FIELDS):
                params = [p.strip() for p in m.group(2)[1:-1].split(",")] if m.group(2) else None
                macros[m.group(1)] = (params, body)
    return macros


def expand_macros(text, macros, depth=0):
    """Expand known macro uses (nested ones too) so that .natDexNum/.frontPic/... become visible."""
    if depth > 4 or not macros:
        return text
    names = re.compile(r"\b(%s)\b" % "|".join(sorted(map(re.escape, macros), key=len, reverse=True)))
    out, pos = [], 0
    for m in names.finditer(text):
        if m.start() < pos:
            continue
        params, body = macros[m.group(1)]
        end = m.end()
        if params is not None:
            if not text[end:].lstrip().startswith("("):
                continue
            start = text.index("(", end)
            level, i = 0, start
            while i < len(text):
                level += text[i] == "("
                level -= text[i] == ")"
                if level == 0:
                    break
                i += 1
            args = split_args(text[start + 1:i])
            end = i + 1
            for p, a in zip(params, args):
                body = re.sub(r"\b%s\b" % re.escape(p), a.replace("\\", "\\\\"), body)
        body = re.sub(r"\s*##\s*", "", body)
        out.append(text[pos:m.start()])
        out.append(expand_macros(body, macros, depth + 1))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def iter_entries(dex_numbers):
    """Yield every species entry that has a national dex number, including entries
    generated by macros (Unown, Vivillon patterns, Alcremie, Silvally, Ogerpon, ...).

    Each item: dict(species, dexconst, dex, name, front, back, pal, shiny)."""
    texts = [read(p) for p in sorted(glob.glob(SPECIES_INFO_FILES))]
    macros = collect_macros(texts)
    pat = re.compile(r"^\s{4}\[(SPECIES_[A-Z0-9_]+)\]\s*=", re.M)
    for t in texts:
        ms = list(pat.finditer(t))
        for k, m in enumerate(ms):
            block = t[m.end(): ms[k + 1].start() if k + 1 < len(ms) else len(t)]
            if ".natDexNum" not in block or "gMonFrontPic" not in block or "##" in block:
                block = expand_macros(block, macros)
            nd = re.search(r"\.natDexNum\s*=\s*(NATIONAL_DEX_[A-Z0-9_]+)", block)
            if not nd or nd.group(1) not in dex_numbers:
                continue

            def sym(field):
                f = re.search(r"\.%s\s*=\s*(gMon\w+)" % field, block)
                return f.group(1) if f else None

            name = re.search(r'\.speciesName\s*=\s*_\("([^"]*)"\)', block)
            yield {
                "species": m.group(1), "dexconst": nd.group(1), "dex": dex_numbers[nd.group(1)],
                "name": name.group(1) if name else m.group(1)[8:].title(),
                "front": sym("frontPic"), "back": sym("backPic"),
                "pal": sym("palette"), "shiny": sym("shinyPalette"),
            }


def load_species(dex_numbers):
    """dex number -> entry of the base form (SPECIES_X for NATIONAL_DEX_X, else the first one seen)."""
    by_dex = {}
    for e in iter_entries(dex_numbers):
        is_base = e["species"][len("SPECIES_"):] == e["dexconst"][len("NATIONAL_DEX_"):]
        if is_base or e["dex"] not in by_dex:
            by_dex[e["dex"]] = e
    return by_dex


STATE_PATH = os.path.join(ROOT, "sprite_import_state.json")


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def record_state(ok):
    """Remember which species received a Moemon sprite (species constant -> source sheet)."""
    state = load_state()
    for name, spc, *_ in ok:
        state[spc] = name
    with open(STATE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(state.items())), f, indent=1)
        f.write("\n")


def load_all_species(dex_numbers):
    """Every species entry with a national dex number, in file order."""
    return list(iter_entries(dex_numbers))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, required=True, choices=sorted(GEN_FOLDERS))
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="'1 - MAIN' folder (default: %(default)s)")
    ap.add_argument("--only", help="comma separated dex numbers to process")
    ap.add_argument("--apply", action="store_true", help="write files (default is a dry run)")
    ap.add_argument("--report", default=os.path.join(ROOT, "sprite_import_report.md"),
                    help="markdown report of warnings/failures (default: %(default)s)")
    args = ap.parse_args()

    folder = os.path.join(args.source, GEN_FOLDERS[args.gen])
    if not os.path.isdir(folder):
        sys.exit("source folder not found: %s" % folder)
    only = {int(x) for x in args.only.split(",")} if args.only else None

    dex_numbers = load_dex_numbers()
    syms = load_graphics_symbols()
    species = load_species(dex_numbers)

    ok, failed, skipped = [], [], []
    for name in sorted(os.listdir(folder)):
        m = re.fullmatch(r"(\d{4})A\.png", name)
        if not m:
            skipped.append((name, "not a plain NNNNA.png sheet (handled in a later pass)"))
            continue
        dex = int(m.group(1))
        if only and dex not in only:
            continue
        sp = species.get(dex)
        if not sp or not all(sp[k] for k in ("front", "back", "pal", "shiny")):
            failed.append((name, "no species/graphics symbols found for dex %d" % dex))
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
            result = convert_sheet(os.path.join(folder, name))
        except SheetError as e:
            failed.append((name, str(e)))
            continue
        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        ok.append((name, sp["species"], paths, is_anim, result))
        if args.apply:
            write_result(result,
                         os.path.join(ROOT, paths["front"]), os.path.join(ROOT, paths["back"]),
                         os.path.join(ROOT, paths["pal"]), os.path.join(ROOT, paths["shiny"]),
                         anim=is_anim)

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

    write_report(args.report, GEN_FOLDERS[args.gen], args.apply, ok, failed, skipped)
    print("report updated: %s" % args.report)
    if args.apply:
        record_state(ok)
        import sprite_checklist
        sprite_checklist.generate()
        print("checklist updated: sprite_checklist.md")


REPORT_HEADER = ("# Moemon sprite import report\n\n"
                 "Generated by `tools/apply_moemon_sprites.py`. Each run replaces the section of the folder it processed.\n"
                 "Entries here are things worth a look in the source art; none of them stop the import "
                 "unless listed under Failures.\n")


def write_report(path, folder_name, applied, ok, failed, skipped):
    snapped = sum(1 for *_, r in ok if "colours snapped to 15-bit" in r["warnings"])
    lines = ["## %s" % folder_name, "",
             "- Mode: %s" % ("applied" if applied else "dry run"),
             "- Imported: %d, failed: %d, skipped: %d" % (len(ok), len(failed), len(skipped)),
             "- Sheets whose colours were snapped to GBA 15-bit (informational): %d" % snapped, ""]

    lines.append("### Failures (not imported)")
    lines += ["- `%s`: %s" % f for f in failed] or ["- none"]
    lines.append("")

    lines.append("### Warnings (imported, but the result differs slightly from the sheet)")
    n = 0
    for name, spc, paths, is_anim, r in ok:
        warns = [w for w in r["warnings"] if w != "colours snapped to 15-bit"]
        if not warns:
            continue
        n += 1
        lines.append("- `%s` (%s, `%s`)" % (name, spc, os.path.dirname(paths["front"]).replace("graphics/pokemon/", "")))
        lines += ["  - %s" % w for w in warns]
        lines += ["    - %s" % d for d in r["details"]]
    if not n:
        lines.append("- none")
    lines.append("")

    lines.append("### Skipped sheets")
    lines += ["- `%s`: %s" % s for s in skipped] or ["- none"]
    lines.append("")
    section = "\n".join(lines)

    # Keep sections of other folders, replace this one, keep folders in sorted order.
    sections = {}
    if os.path.exists(path):
        for part in re.split(r"(?m)^(?=## )", read(path)):
            if part.startswith("## "):
                sections[part.split("\n", 1)[0][3:].strip()] = part.rstrip() + "\n"
    sections[folder_name] = section.rstrip() + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(REPORT_HEADER)
        for key in sorted(sections):
            f.write("\n" + sections[key])


if __name__ == "__main__":
    main()
