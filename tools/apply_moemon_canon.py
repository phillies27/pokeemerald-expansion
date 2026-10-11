#!/usr/bin/env python3
"""Apply the Moemon "Other Canon Forms" sheets (and the female "A" sheets of gendered pairs).

Sheet names are "<dex>A_<Tag>.png" with a free-form tag, so the species are listed explicitly in
SHEET_MAP below. Sheets that are not listed are reported as skipped.

Forms in the repo often share graphics with another form, so a plain overwrite would clobber the
base sprite. Each target is therefore handled according to what it shares:

  normal       own front/back/palettes            -> written like the main importer
  repalette    front sprite shared with the base  -> only the palettes are written, laid out to
               (e.g. Flabebe colours, Genesect     match the pixel indices already in the file;
               drives, Deerling seasons)           fails if the art is not the same shapes
  remap        palette shared with other forms    -> sprite indices are remapped onto the shared
               (e.g. Unown letters)                palette; fails if it needs unknown colours

Gender pairs: "NNNNA_Male.png" is the male (default) sprite, the plain "NNNNA.png" sheet from the
generation folder is the female one and is applied to the female graphics.

Default is a dry run; add --apply to write.
"""

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_moemon_sprites as base  # noqa: E402
from PIL import Image  # noqa: E402
from split_sprite_sheet import (MAX_STRAY_PIXELS, TILE, SheetError, convert_sheet,  # noqa: E402
                                pixels, save_indexed, write_pal, write_result)

FOLDER = "Other Canon Forms"
S = "SPECIES_"

# stem -> list of species constants (all species in a list share one set of graphics).
SHEET_MAP = {
    "0025A_Belle": [S + "PIKACHU_BELLE"], "0025A_Libre": [S + "PIKACHU_LIBRE"],
    "0025A_Rock": [S + "PIKACHU_ROCK_STAR"],
    "0172A_Spiky": [S + "PICHU_SPIKY_EARED"],
    "0351A_Rainy": [S + "CASTFORM_RAINY"], "0351A_Snowy": [S + "CASTFORM_SNOWY"],
    "0351A_Sunny": [S + "CASTFORM_SUNNY"],
    "0386A_Attack": [S + "DEOXYS_ATTACK"], "0386A_Defense": [S + "DEOXYS_DEFENSE"],
    "0386A_Speed": [S + "DEOXYS_SPEED"],
    "0412A_Sandy": [S + "BURMY_SANDY"], "0412A_Trash": [S + "BURMY_TRASH"],
    "0413A_Sandy": [S + "WORMADAM_SANDY"], "0413A_Trash": [S + "WORMADAM_TRASH"],
    "0421A_Sun": [S + "CHERRIM_SUNSHINE"],
    "0422A_East": [S + "SHELLOS_EAST"], "0423A_East": [S + "GASTRODON_EAST"],
    "0479A_Fan": [S + "ROTOM_FAN"], "0479A_Heat": [S + "ROTOM_HEAT"], "0479A_Mow": [S + "ROTOM_MOW"],
    "0487A_Origin": [S + "GIRATINA_ORIGIN"], "0492A_Sky": [S + "SHAYMIN_SKY"],
    "0550A_Blue": [S + "BASCULIN_BLUE_STRIPED"], "0550A_White": [S + "BASCULIN_WHITE_STRIPED"],
    "0555A_Zen": [S + "DARMANITAN_ZEN"], "0555A_ZenG": [S + "DARMANITAN_GALAR_ZEN"],
    "0585A_Summer": [S + "DEERLING_SUMMER"], "0585A_Autumn": [S + "DEERLING_AUTUMN"],
    "0585A_Winter": [S + "DEERLING_WINTER"],
    "0586A_Summer": [S + "SAWSBUCK_SUMMER"], "0586A_AUtumn": [S + "SAWSBUCK_AUTUMN"],
    "0586A_Winter": [S + "SAWSBUCK_WINTER"],
    "0646A_Black": [S + "KYUREM_BLACK"], "0646A_White": [S + "KYUREM_WHITE"],
    "0647A_Resolute": [S + "KELDEO_RESOLUTE"], "0648A_Pirouette": [S + "MELOETTA_PIROUETTE"],
    "0649A_Burn": [S + "GENESECT_BURN"], "0649A_Chill": [S + "GENESECT_CHILL"],
    "0649A_Douse": [S + "GENESECT_DOUSE"], "0649A_Shock": [S + "GENESECT_SHOCK"],
    "0658A_Ash": [S + "GRENINJA_ASH"],
    "0669A_Blue": [S + "FLABEBE_BLUE"], "0669A_Orange": [S + "FLABEBE_ORANGE"],
    "0669A_White": [S + "FLABEBE_WHITE"], "0669A_Yellow": [S + "FLABEBE_YELLOW"],
    "0670A_Blue": [S + "FLOETTE_BLUE"], "0670A_Orange": [S + "FLOETTE_ORANGE"],
    "0670A_White": [S + "FLOETTE_WHITE"], "0670A_Yellow": [S + "FLOETTE_YELLOW"],
    "0670A_Eternal": [S + "FLOETTE_ETERNAL"],
    "0671A_Blue": [S + "FLORGES_BLUE"], "0671A_Orange": [S + "FLORGES_ORANGE"],
    "0671A_White": [S + "FLORGES_WHITE"], "0671A_Yellow": [S + "FLORGES_YELLOW"],
    "0676A_Dandy": [S + "FURFROU_DANDY"], "0676A_Debutante": [S + "FURFROU_DEBUTANTE"],
    "0676A_Diamond": [S + "FURFROU_DIAMOND"], "0676A_Heart": [S + "FURFROU_HEART"],
    "0676A_Kabuki": [S + "FURFROU_KABUKI"], "0676A_LaReine": [S + "FURFROU_LA_REINE"],
    "0676A_Matron": [S + "FURFROU_MATRON"], "0676A_Pharaoh": [S + "FURFROU_PHARAOH"],
    "0676A_Star": [S + "FURFROU_STAR"],
    "0681A_Blade": [S + "AEGISLASH_BLADE"],
    "0710A_Jumbo": [S + "PUMPKABOO_SUPER"], "0710A_Large": [S + "PUMPKABOO_LARGE"],
    "0710A_Small": [S + "PUMPKABOO_SMALL"],
    "0711A_Jumbo": [S + "GOURGEIST_SUPER"],
    "0718A_10": [S + "ZYGARDE_10_AURA_BREAK", S + "ZYGARDE_10_POWER_CONSTRUCT"],
    "0718A_Complete": [S + "ZYGARDE_COMPLETE"],
    "0720A_Unbound": [S + "HOOPA_UNBOUND"],
    "0741A_Pau": [S + "ORICORIO_PAU"], "0741A_Pom": [S + "ORICORIO_POM_POM"],
    "0741A_Sensu": [S + "ORICORIO_SENSU"],
    "0745A_Dusk": [S + "LYCANROC_DUSK"], "0745A_Midnight": [S + "LYCANROC_MIDNIGHT"],
    "0746A_School": [S + "WISHIWASHI_SCHOOL"],
    "0778A_Busted": [S + "MIMIKYU_BUSTED", S + "MIMIKYU_BUSTED_TOTEM"],
    "0845A_Gorging": [S + "CRAMORANT_GORGING"], "0845A_Gulping": [S + "CRAMORANT_GULPING"],
    "0849A_Low": [S + "TOXTRICITY_LOW_KEY"],
    "0875A_Noice": [S + "EISCUE_NOICE"], "0877A_Hangry": [S + "MORPEKO_HANGRY"],
    "0892A_Rapid": [S + "URSHIFU_RAPID_STRIKE"],
    "0898A_Shadow": [S + "CALYREX_SHADOW"],
    "0901A_Blood": [S + "URSALUNA_BLOODMOON"],
    "0925A_Four": [S + "MAUSHOLD_FOUR"],
    "0964A_Hero": [S + "PALAFIN_HERO"],
    "0982A_Three": [S + "DUDUNSPARCE_THREE_SEGMENT"],
    "1017A_Cornerstone": [S + "OGERPON_CORNERSTONE"], "1017A_Hearthflame": [S + "OGERPON_HEARTHFLAME"],
    "1017A_Wellspring": [S + "OGERPON_WELLSPRING"],
    # Gender pairs, male sheets -> default (male) graphics
    "0449A_Male": [S + "HIPPOPOTAS"], "0450A_Male": [S + "HIPPOWDON"],
    "0592A_Male": [S + "FRILLISH"], "0593A_Male": [S + "JELLICENT"],
    "0677A_Male": [S + "ESPURR"], "0678A_Male": [S + "MEOWSTIC_M"],
    "0902A_Male": [S + "BASCULEGION_M"],
}
# Unown letters (the A sheet is the plain letter A)
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    SHEET_MAP["0201A_" + _c] = [S + "UNOWN" + ("" if _c == "A" else "_" + _c)]
SHEET_MAP["0201A_Exclamation"] = [S + "UNOWN_EXCLAMATION"]
SHEET_MAP["0201A_Question"] = [S + "UNOWN_QUESTION"]
# Vivillon patterns
for _tag, _sp in {"Archipelago": "ARCHIPELAGO", "Continental": "CONTINENTAL", "Elegant": "ELEGANT",
                  "Fancy": "FANCY", "Garden": "GARDEN", "HighPlains": "HIGH_PLAINS",
                  "IcySnow": "ICY_SNOW", "Jungle": "JUNGLE", "Marine": "MARINE", "Meadow": "MEADOW",
                  "Modern": "MODERN", "Monsoon": "MONSOON", "Ocean": "OCEAN", "Pokeball": "POKEBALL",
                  "Polar": "POLAR", "River": "RIVER", "Sandstorm": "SANDSTORM", "Savanna": "SAVANNA",
                  "Sun": "SUN", "Tundra": "TUNDRA"}.items():
    SHEET_MAP["0666A_" + _tag] = [S + "VIVILLON_" + _sp]

# Female sheets of the gendered pairs: (generation folder, sheet, species, role)
# role "female" = the species' female graphics (falls back to the shared default graphics when the
# species only has a female palette); role "main" = a separate female species entry.
FEMALE_SHEETS = [
    ("4. Generation IV", "0449A", S + "HIPPOPOTAS", "female"),
    ("4. Generation IV", "0450A", S + "HIPPOWDON", "female"),
    ("5. Generation V", "0592A", S + "FRILLISH", "female"),
    ("5. Generation V", "0593A", S + "JELLICENT", "female"),
    ("6. Generation VI", "0678A", S + "MEOWSTIC_F", "main"),
    ("8. Generation VIII", "0902A", S + "BASCULEGION_F", "main"),
]

NOT_APPLIED = {
    "0000A": "Egg sprite: the egg uses a 24x24 picture with its own layout; not handled",
    "0550A_WhiteM": "no separate male White-Striped Basculin graphics in the repo",
    "0550B-_WhiteM": "unclear which species this is (0550B); needs your call",
    "0550B_White": "unclear which species this is (0550B); needs your call",
}


def read_pal(path):
    with open(path) as f:
        lines = f.read().splitlines()[3:]
    return [tuple(int(x) for x in ln.split()) for ln in lines if ln.strip()]


def read_idx(path):
    im = Image.open(path)
    data = pixels(im)
    return data[:TILE * TILE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=base.DEFAULT_SOURCE)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", default=os.path.join(base.ROOT, "sprite_import_report.md"))
    args = ap.parse_args()
    root = base.ROOT

    folder = os.path.join(args.source, FOLDER)
    dex_numbers = base.load_dex_numbers()
    syms = base.load_graphics_symbols()
    entries = {}
    for e in base.iter_entries(dex_numbers):
        entries.setdefault(e["species"], e)

    def path_of(sym):
        return syms.get(sym) if sym else None

    # who uses each file (explicit symbols only)
    users = {}
    for sp, e in entries.items():
        for k in ("front", "back", "pal", "shiny", "front_f", "back_f", "pal_f", "shiny_f"):
            p = path_of(e[k])
            if p:
                users.setdefault(p, set()).add(sp)

    def targets(group, role):
        """-> (paths dict, forced-shared flags) for the first species of the group."""
        e = entries[group[0]]
        main_p = {k: path_of(e[k]) for k in ("front", "back", "pal", "shiny")}
        if role != "female":
            return main_p, set()
        fem = {"front": path_of(e["front_f"]), "back": path_of(e["back_f"]),
               "pal": path_of(e["pal_f"]), "shiny": path_of(e["shiny_f"])}
        forced = {k for k in fem if not fem[k]}
        return {k: fem[k] or main_p[k] for k in fem}, forced

    jobs = []   # (sheet path, stem label, group, role)
    for stem, group in SHEET_MAP.items():
        jobs.append((os.path.join(folder, stem + ".png"), stem + ".png", group, "main"))
    for gen, sheet, sp, role in FEMALE_SHEETS:
        p = os.path.join(args.source, gen, sheet + ".png")
        jobs.append((p, "%s.png (female)" % sheet, [sp], role))

    ok, failed, skipped = [], [], []
    present = set(os.listdir(folder))
    for name in sorted(present):
        stem = os.path.splitext(name)[0]
        if stem in NOT_APPLIED:
            skipped.append((name, NOT_APPLIED[stem]))
        elif stem not in SHEET_MAP:
            skipped.append((name, "not mapped to a species yet"))

    for sheet_path, label, group, role in jobs:
        if not os.path.exists(sheet_path):
            continue
        if any(sp not in entries for sp in group):
            failed.append((label, "species not found in the repo: %s" % ", ".join(group)))
            continue
        paths, forced = targets(group, role)
        if not all(paths.values()):
            failed.append((label, "graphics symbols/paths not found for %s" % group[0]))
            continue
        missing = [p for p in paths.values() if not os.path.exists(os.path.join(root, p))]
        if missing:
            failed.append((label, "target file missing: %s" % ", ".join(missing)))
            continue
        grp = set(group)

        def shared(field):
            return field in forced or bool(users.get(paths[field], set()) - grp)

        fs, bs, ps = shared("front"), shared("back"), shared("pal") or shared("shiny")
        try:
            result = convert_sheet(sheet_path)
        except SheetError as e:
            failed.append((label, str(e)))
            continue
        warnings = [w for w in result["warnings"]]
        details = list(result["details"])
        full = {k: os.path.join(root, v) for k, v in paths.items()}
        is_anim = os.path.basename(paths["front"]).startswith("anim_front")
        writes = []   # callables run on --apply
        mode = "normal"

        if ps:
            mode = "remap (shared palette)"
            existing = read_pal(full["pal"])
            existing_shiny = read_pal(full["shiny"])
            lookup = {}
            for i, c in enumerate(existing):
                if i > 0:
                    lookup.setdefault(c, i)
            remap, bad = {0: 0}, []
            for i, c in enumerate(result["palette"][:16]):
                if i == 0:
                    continue
                if i in set(result["front_idx"]) | set(result["back_idx"]):
                    if c in lookup:
                        remap[i] = lookup[c]
                    else:
                        bad.append(c)
            if bad:
                failed.append((label, "uses colours that are not in the shared palette %s: %s"
                               % (paths["pal"], ", ".join(map(str, bad)))))
                continue
            mism = sum(1 for i in set(result["front_idx"]) | set(result["back_idx"])
                       if i in remap and existing_shiny[remap[i]] != result["shiny_palette"][i])
            if mism:
                warnings.append("%d palette entries: shiny colour differs from the shared shiny palette" % mism)
            nf = [remap[i] for i in result["front_idx"]]
            nb = [remap[i] for i in result["back_idx"]]
            if not fs:
                writes.append(lambda nf=nf: save_indexed(
                    full["front"], (TILE, TILE * 2 if is_anim else TILE), nf + nf if is_anim else nf, existing))
            if not bs:
                writes.append(lambda nb=nb: save_indexed(full["back"], (TILE, TILE), nb, existing))
            else:
                warnings.append("back sprite shared with other forms; not written")
        elif fs:
            mode = "repalette (shared front)"
            e_front = read_idx(full["front"])
            e_back = read_idx(full["back"])
            pal_new, shiny_new = {0: result["bg"]}, {0: result["bg"]}
            votes, svotes = {}, {}
            for ei, fi in zip(e_front, result["front_idx"]):
                votes.setdefault(ei, Counter())[result["palette"][fi]] += 1
                svotes.setdefault(ei, Counter())[result["shiny_palette"][fi]] += 1
            conflict = 0
            for ei, cnt in votes.items():
                if ei == 0:
                    continue
                conflict += sum(cnt.values()) - cnt.most_common(1)[0][1]
                pal_new[ei] = cnt.most_common(1)[0][0]
                shiny_new[ei] = svotes[ei].most_common(1)[0][0]
                if len(svotes[ei]) > 1:
                    conflict += sum(svotes[ei].values()) - svotes[ei].most_common(1)[0][1]
            if conflict > MAX_STRAY_PIXELS and role == "female" and "front" in forced:
                # The female differs from the male only by palette in this repo, and the female art is
                # not a recolour of the male art. Keep the female colours consistent with the new male
                # sprite by reusing the male palettes.
                e0 = entries[group[0]]
                mp = {k: os.path.join(root, path_of(e0[k])) for k in ("pal", "shiny")}
                mode = "female reuses the male palette"
                warnings.append("female art is not a recolour of the male art (%d pixels differ), so the "
                                "female form uses the male sprite and palette" % conflict)
                writes.append(lambda mp=mp: write_pal(full["pal"], read_pal(mp["pal"])))
                writes.append(lambda mp=mp: write_pal(full["shiny"], read_pal(mp["shiny"])))
            elif conflict > MAX_STRAY_PIXELS:
                failed.append((label, "art does not match the shared base sprite: %d pixels need a different "
                               "palette entry than their neighbours (not just a recolour)" % conflict))
                continue
            elif True:
                if conflict:
                    warnings.append("%d pixel(s) did not fit the base sprite's colour layout and were ignored"
                                    % conflict)
                miss = 0
                for ei, bi in zip(e_back, result["back_idx"]):
                    c = result["palette"][bi]
                    if ei not in pal_new:
                        pal_new[ei] = c
                        shiny_new[ei] = result["shiny_palette"][bi]
                    elif pal_new[ei] != c:
                        miss += 1
                if miss:
                    warnings.append("%d back-sprite pixels do not fit the shared palette layout" % miss)
                old_pal = read_pal(full["pal"])
                old_shiny = read_pal(full["shiny"])
                newp = [pal_new.get(i, old_pal[i] if i < len(old_pal) else (0, 0, 0)) for i in range(16)]
                news = [shiny_new.get(i, old_shiny[i] if i < len(old_shiny) else (0, 0, 0)) for i in range(16)]
                writes.append(lambda: write_pal(full["pal"], newp))
                writes.append(lambda: write_pal(full["shiny"], news))
                if not bs:
                    warnings.append("back sprite not rewritten (sprite is shared-layout; only palettes changed)")
        else:
            writes.append(lambda: write_result(result, full["front"], full["back"], full["pal"],
                                               full["shiny"], anim=is_anim))

        res = {"warnings": [w for w in warnings], "details": details,
               "colours_used": result["colours_used"], "mode": mode}
        if mode != "normal":
            res["warnings"].insert(0, "mode: " + mode)
        for k, sp in enumerate(group):
            tag = sp + (" (female graphics)" if role == "female" else "")
            ok.append((label, tag, paths, is_anim, res))
        if args.apply:
            for w in writes:
                w()

    verb = "WROTE" if args.apply else "would write"
    for label, spc, paths, is_anim, res in ok:
        warn = ("  [%s]" % "; ".join(w for w in res["warnings"] if w != "colours snapped to 15-bit")) \
            if [w for w in res["warnings"] if w != "colours snapped to 15-bit"] else ""
        print("%-26s -> %-42s %s%s" % (label, spc, paths["front"].replace("graphics/pokemon/", ""), warn))
    print()
    for label, why in failed:
        print("FAILED  %s: %s" % (label, why))
    for label, why in skipped:
        print("skipped %s: %s" % (label, why))
    print("\n%s %d species entries, %d failed, %d skipped%s" % (
        verb, len(ok), len(failed), len(skipped), "" if args.apply else "  (dry run; add --apply to write)"))

    base.write_report(args.report, FOLDER, args.apply, ok, failed, skipped)
    print("report updated: %s" % args.report)
    if args.apply:
        base.record_state([(n, s, *r) for n, s, *r in ok if "(female graphics)" not in s])
        import sprite_checklist
        sprite_checklist.generate()
        print("checklist updated: sprite_checklist.md")


if __name__ == "__main__":
    main()
