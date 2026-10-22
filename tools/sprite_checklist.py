#!/usr/bin/env python3
"""Generate sprite_checklist.md: every species and form by generation, with its sprite status.

    [x]  replaced with a Moemon sprite (recorded in sprite_import_state.json by
         tools/apply_moemon_sprites.py --apply), or it shares its graphics with a replaced species
    [ ]  still the original sprite; the note says whether a matching sheet exists in the Moemon database

Run:  python tools/sprite_checklist.py
(apply_moemon_sprites.py --apply refreshes it automatically.)
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_moemon_sprites as ams  # noqa: E402

GENS = [  # (gen, first dex, last dex)
    (1, 1, 151), (2, 152, 251), (3, 252, 386), (4, 387, 493), (5, 494, 649),
    (6, 650, 721), (7, 722, 809), (8, 810, 905), (9, 906, 1025),
]
OUT = os.path.join(ams.ROOT, "sprite_checklist.md")

MEGA_SUFFIX = {"M": "_MEGA", "MX": "_MEGA_X", "MY": "_MEGA_Y", "MZ": "_MEGA_Z"}
REGION_SUFFIX = {"Alola": "_ALOLA", "Galar": "_GALAR", "Hisui": "_HISUI", "Paldea": "_PALDEA"}
# database suffix -> alternative species-constant suffixes to try
ALIASES = {"Rock": ["ROCK_STAR"], "ZenG": ["GALAR_ZEN"], "Male": ["M", "MALE"], "A": [""],
           "WhiteM": ["WHITE_STRIPED"], "White": ["WHITE_STRIPED", "WHITE"], "Blue": ["BLUE_STRIPED", "BLUE"],
           "Low": ["LOW_KEY"], "Hangry": ["HANGRY"], "Noice": ["NOICE_FACE"], "Gorging": ["GORGING"],
           "Gulping": ["GULPING"], "Busted": ["BUSTED"], "School": ["SCHOOL"], "Hero": ["HERO"],
           "Three": ["THREE_SEGMENT"], "Four": ["FAMILY_OF_FOUR"], "Rapid": ["RAPID_STRIKE"],
           "Blood": ["BLOODMOON"], "10": ["10_PERCENT"], "Origin": ["ORIGIN"], "Sky": ["SKY"],
           "Autumn": ["AUTUMN"], "AUtumn": ["AUTUMN"], "Resolute": ["RESOLUTE"], "Pirouette": ["PIROUETTE"]}


def gen_of(dex):
    for g, lo, hi in GENS:
        if lo <= dex <= hi:
            return g
    return GENS[-1][0] if dex > GENS[-1][2] else None


def snake(s):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).upper()


def sheet_index(source, base_of, stem_of, all_consts):
    """species constant -> 'Folder/file.png' for every database sheet we can match;
    plus the list of sheets that match nothing."""
    found, unmatched = {}, []
    if not os.path.isdir(source):
        return found, unmatched
    for folder in sorted(os.listdir(source)):
        fdir = os.path.join(source, folder)
        if not os.path.isdir(fdir):
            continue
        for fn in sorted(os.listdir(fdir)):
            stem, ext = os.path.splitext(fn)
            if ext.lower() != ".png":
                continue
            rel = "%s/%s" % (folder, fn)
            m = re.fullmatch(r"(\d{4})A?(?:_(.+))?", stem)
            cands = []
            if m:
                dex = int(m.group(1))
                suffix = m.group(2)
                base = base_of.get(dex)
                sp = stem_of.get(dex)  # e.g. SPECIES_DEOXYS (base constant may be ..._NORMAL)
                if base and not suffix and stem.endswith("A"):
                    cands = [base]
                elif base and suffix:
                    if folder == "Megas" and suffix in MEGA_SUFFIX:
                        cands = [sp + MEGA_SUFFIX[suffix]]
                    elif folder == "Regional Forms" and suffix in REGION_SUFFIX:
                        cands = [sp + REGION_SUFFIX[suffix], sp + REGION_SUFFIX[suffix] + "N",
                                 sp + REGION_SUFFIX[suffix] + "IAN"]
                    elif folder == "Gigantamax":
                        cands = [sp + "_GMAX", sp + "_GIGANTAMAX"]
                    else:
                        words = [snake(suffix), suffix.upper()] + ALIASES.get(suffix, [])
                        cands = [(sp + "_" + w) if w else base for w in words]
                        if suffix == "Male":
                            cands.append(base)
            hit = next((c for c in cands if c in all_consts), None)
            if hit:
                found.setdefault(hit, rel)
            else:
                unmatched.append(rel)
    return found, unmatched


def generate(source=None):
    source = source or ams.DEFAULT_SOURCE
    dex_numbers = ams.load_dex_numbers()
    entries = ams.load_all_species(dex_numbers)
    base_entries = ams.load_species(dex_numbers)
    base_of = {d: e["species"] for d, e in base_entries.items()}
    stem_of = {d: "SPECIES_" + e["dexconst"][len("NATIONAL_DEX_"):] for d, e in base_entries.items()}
    all_consts = {e["species"] for e in entries}
    sheets, unmatched = sheet_index(source, base_of, stem_of, all_consts)
    state = ams.load_state()

    # Species that share a graphics symbol with a replaced species count as replaced.
    done_symbols = {e["front"]: e["species"] for e in entries if e["species"] in state and e["front"]}

    def status(e):
        if e["species"] in state:
            return True, "from `%s`" % state[e["species"]]
        via = done_symbols.get(e["front"])
        if via:
            return True, "shares sprite with `%s`" % via
        return False, ("sheet ready: `%s`" % sheets[e["species"]]) if e["species"] in sheets else "no sheet found yet"

    by_gen = {g: [] for g, *_ in GENS}
    for e in entries:
        g = gen_of(e["dex"])
        if g:
            by_gen[g].append(e)

    lines = ["# Moemon sprite checklist", "",
             "Generated by `tools/sprite_checklist.py` (refreshed by `tools/apply_moemon_sprites.py --apply`).",
             "`[x]` = replaced (or shares a replaced sprite), `[ ]` = original sprite still in use. "
             "Forms are indented under their base Pokémon.", ""]
    total_done = total_all = 0
    body = []
    summary = ["| Generation | Done | Total (incl. forms) | Base species done |", "|---|---|---|---|"]
    for g, lo, hi in GENS:
        es = by_gen[g]
        es.sort(key=lambda e: (e["dex"], e["species"] != base_of.get(e["dex"])))
        done = sum(status(e)[0] for e in es)
        base_es = [e for e in es if e["species"] == base_of.get(e["dex"])]
        base_done = sum(status(e)[0] for e in base_es)
        total_done += done
        total_all += len(es)
        summary.append("| Gen %d (#%d-%d) | %d | %d | %d/%d |" % (g, lo, hi, done, len(es), base_done, len(base_es)))
        body += ["## Gen %d (#%d-%d): %d/%d done" % (g, lo, hi, done, len(es)), ""]
        for e in es:
            ok, note = status(e)
            is_base = e["species"] == base_of.get(e["dex"])
            box = "[x]" if ok else "[ ]"
            if is_base:
                body.append("- %s **#%04d %s** `%s`: %s" % (box, e["dex"], e["name"], e["species"], note))
            else:
                stem = stem_of.get(e["dex"], "SPECIES_")
                label = (e["species"][len(stem):].strip("_") if e["species"].startswith(stem) else "") or e["species"]
                body.append("  - %s %s (`%s`): %s" % (box, label.replace("_", " ").title(), e["species"], note))
        body.append("")

    lines += ["**Overall: %d / %d done**" % (total_done, total_all), ""] + summary + [""] + body

    lines += ["## Database sheets not matched to a species", "",
              "These files exist in the Moemon database but could not be matched to a species constant "
              "automatically, so they need a manual mapping.", ""]
    lines += ["- `%s`" % u for u in unmatched] or ["- none"]
    lines.append("")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    write_todo(by_gen, status, base_of, base_entries, stem_of, sheets)
    return total_done, total_all, len(unmatched)


TODO_OUT = os.path.join(ams.ROOT, "sprite_todo.md")


def write_todo(by_gen, status, base_of, base_entries, stem_of, sheets):
    """sprite_todo.md: only the species that still use an original sprite, split into
    'a Moemon sheet exists' and 'needs new art' (candidates for tools/ai_sprite_to_gba.py)."""
    def label(e):
        base = base_entries[e["dex"]]["name"] if e["dex"] in base_entries else e["name"]
        if e["species"] == base_of.get(e["dex"]):
            return base
        stem = stem_of.get(e["dex"], "SPECIES_")
        form = (e["species"][len(stem):].strip("_") if e["species"].startswith(stem) else "") or e["species"]
        return "%s (%s)" % (base, form.replace("_", " ").title())

    ready, need = {}, {}
    for g, *_ in GENS:
        for e in by_gen[g]:
            if status(e)[0]:
                continue
            (ready if e["species"] in sheets else need).setdefault(g, []).append(e)

    def block(title, groups, note):
        out = ["## %s: %d" % (title, sum(len(v) for v in groups.values())), "", note, ""]
        for g, lo, hi in GENS:
            es = groups.get(g)
            if not es:
                continue
            out.append("### Gen %d (#%d-%d): %d" % (g, lo, hi, len(es)))
            for e in es:
                extra = (" - sheet `%s`" % sheets[e["species"]]) if e["species"] in sheets else ""
                out.append("- [ ] #%04d %s `%s`%s" % (e["dex"], label(e), e["species"], extra))
            out.append("")
        return out

    lines = ["# Sprites still using the original art", "",
             "Generated by `tools/sprite_checklist.py` (refreshed by `apply_moemon_sprites.py --apply` and "
             "`ai_sprite_to_gba.py --apply`).", "",
             "Make a sprite for any entry below with:", "",
             "    python tools/ai_sprite_to_gba.py FRONT.png --back BACK.png --species SPECIES_X [--outline] [--apply]", ""]
    lines += block("Moemon sheet already in the database", ready,
                   "A sheet exists but has not been applied yet (import it instead of generating art).")
    lines += block("Needs new art", need, "No Moemon sheet found - draw or generate these.")
    with open(TODO_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return TODO_OUT


if __name__ == "__main__":
    d, t, u = generate()
    print("checklist written: %d/%d done, %d database sheets unmatched -> %s" % (d, t, u, OUT))
