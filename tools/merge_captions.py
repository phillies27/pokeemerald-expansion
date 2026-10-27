#!/usr/bin/env python3
"""Merge WD14 tags (kohya Utilities -> Captioning -> WD14, extension ".wd14.txt") into the LoRA captions
written by make_lora_dataset.py.

For every image the new caption is

    <trigger>, pixel art, <front view | back view[, battle back sprite]>, <species name>, <WD14 tags>, white background

What changes compared with the generated captions
    * the generated "full body" / "close-up" words are removed; the WD14 tagger decides the framing
      ("full body", "upper body", "portrait", "cowboy shot", ...), because the old words were wrong for most fronts
    * the unreliable "red and brown colors" guess is removed (WD14 names hair / eye / outfit colours properly)
    * junk tags are dropped: character names (the tagger sees Touhou / Vocaloid people in pixel art),
      rating tags, and tags that describe the pixel-art style itself (monochrome, greyscale, comic, ...)

The first run copies each caption to "<name>.orig.txt" and always rebuilds from that copy, so the merge can be
repeated with different options. kohya ignores .orig.txt and .wd14.txt (it only reads "<name>.txt").
Default is a dry run; add --apply to write.

Examples
    python tools/merge_captions.py build/lora_dataset/1_moemon
    python tools/merge_captions.py build/lora_dataset/1_moemon --apply
    python tools/merge_captions.py build/lora_dataset/1_moemon --apply --exclude-closeups
    python tools/merge_captions.py build/lora_dataset/1_moemon --apply --drop "breasts,cleavage"
"""

import argparse
import csv
import glob
import os
import shutil
import sys
from collections import Counter

DEFAULT_DROP = ["monochrome", "greyscale", "comic", "simple background", "transparent background", "white background",
                "pov", "straight-on", "virtual youtuber", "sketch", "lineart", "limited palette", "traditional media"]
KNOWN = {"pixel art", "front view", "back view", "full body", "battle back sprite", "close-up", "white background"}
CLOSEUP_TAGS = {"upper body", "portrait", "close-up", "face", "bust"}
FRAMING_TAGS = CLOSEUP_TAGS | {"full body", "cowboy shot", "lower body"}


def find_tag_csv(explicit):
    if explicit:
        return explicit
    for root in (r"D:\AI\kohya_ss\wd14_tagger_model", os.path.expanduser("~/kohya_ss/wd14_tagger_model")):
        hits = glob.glob(os.path.join(root, "*", "selected_tags.csv"))
        if hits:
            return hits[0]
    return None


def load_blocked(csv_path):
    """WD14 categories 4 (character names) and 9 (ratings) are never useful as captions here."""
    blocked = set()
    if csv_path and os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["category"] in ("4", "9"):
                    blocked.add(row["name"].replace("_", " "))
    return blocked


def parse_original(text):
    tokens = [t.strip() for t in text.strip().split(",") if t.strip()]
    trigger = tokens[0] if tokens else "moemon sprite"
    view = "back" if "back view" in tokens else "front"
    title = next((t for t in tokens if t not in KNOWN and t != trigger and not t.endswith(" colors")), "")
    return trigger, view, title


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder that contains the images, e.g. build/lora_dataset/1_moemon")
    ap.add_argument("--tags-ext", default=".wd14.txt", help="extension of the WD14 files (default .wd14.txt)")
    ap.add_argument("--tags-csv", help="selected_tags.csv of the tagger model (found automatically for kohya_ss in D:\\AI)")
    ap.add_argument("--drop", default="", help="extra tags to drop, comma separated")
    ap.add_argument("--keep-only-drop", action="store_true", help="use only --drop instead of adding it to the default list")
    ap.add_argument("--no-species", action="store_true", help="leave the species name out of the captions")
    ap.add_argument("--exclude-closeups", action="store_true",
                    help="move FRONT images tagged upper body / portrait / close-up (and not full body) out of the "
                         "dataset into a sibling '<dataset>_excluded' folder (only with --apply)")
    ap.add_argument("--full-body-fronts", action="store_true",
                    help="add 'full body' (right after the species name) to every FRONT caption that is not tagged "
                         "upper body / portrait / close-up / bust / cowboy shot / lower body")
    ap.add_argument("--apply", action="store_true", help="write the captions (default is a dry run)")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    images = sorted(glob.glob(os.path.join(folder, "*.png")))
    if not images:
        sys.exit("no .png images in %s (point it at the folder that contains the images)" % folder)

    csv_path = find_tag_csv(args.tags_csv)
    blocked = load_blocked(csv_path)
    if not blocked:
        print("note: selected_tags.csv not found (use --tags-csv) - character-name tags will NOT be filtered")
    drop = set([] if args.keep_only_drop else DEFAULT_DROP) | {t.strip() for t in args.drop.split(",") if t.strip()}

    out_dir = os.path.join(os.path.dirname(os.path.dirname(folder)),
                           os.path.basename(os.path.dirname(folder)) + "_excluded")
    results, missing, moved, added_full = [], 0, 0, 0
    tag_count, framing = Counter(), {"front": Counter(), "back": Counter()}
    for img in images:
        stem = img[:-4]
        cap_path, orig_path, wd_path = stem + ".txt", stem + ".orig.txt", stem + args.tags_ext
        if not os.path.exists(wd_path):
            missing += 1
            continue
        if not os.path.exists(orig_path):
            if not os.path.exists(cap_path):
                missing += 1
                continue
            if args.apply:
                shutil.copyfile(cap_path, orig_path)
            src = cap_path
        else:
            src = orig_path
        with open(src, encoding="utf-8") as f:
            trigger, view, title = parse_original(f.read())
        with open(wd_path, encoding="utf-8") as f:
            raw = [t.strip() for t in f.read().replace("\n", ",").split(",") if t.strip()]
        tags = [t for t in dict.fromkeys(raw) if t not in drop and t not in blocked]
        tag_count.update(tags)
        fr = [t for t in tags if t in FRAMING_TAGS]
        framing[view][fr[0] if fr else "(none)"] += 1

        head = [trigger, "pixel art", "%s view" % view]
        if view == "back":
            head.append("battle back sprite")
        if title and not args.no_species:
            head.append(title)
        if args.full_body_fronts and view == "front" and not (set(tags) & (CLOSEUP_TAGS | {"cowboy shot", "lower body"})):
            head.append("full body")
            tags = [t for t in tags if t != "full body"]
            added_full += 1
        caption = ", ".join(head + tags + ["white background"])
        closeup = view == "front" and (set(tags) & CLOSEUP_TAGS) and "full body" not in tags
        results.append((img, caption, closeup))

    print("%d images, %d without a %s file (skipped)" % (len(results), missing, args.tags_ext))
    for v in ("front", "back"):
        n = sum(framing[v].values())
        if n:
            print("  %s framing tags: %s" % (v, ", ".join("%s %d" % (k, c) for k, c in framing[v].most_common())))
    print("  most common remaining tags:", ", ".join("%s (%d)" % kv for kv in tag_count.most_common(25)))
    if args.full_body_fronts:
        print("  'full body' added to %d front captions" % added_full)
    n_close = sum(1 for _, _, c in results if c)
    print("  front images that look like close-ups / upper-body only: %d" % n_close)
    print("\nexamples:")
    for img, cap, _ in results[:3] + results[len(results) // 2:len(results) // 2 + 2]:
        print("  %s\n    %s" % (os.path.basename(img), cap))

    if not args.apply:
        print("\ndry run: nothing written. Add --apply to write (originals are kept as .orig.txt).")
        return

    for img, cap, closeup in results:
        stem = img[:-4]
        with open(stem + ".txt", "w", encoding="utf-8", newline="\n") as f:
            f.write(cap + "\n")
        if args.exclude_closeups and closeup:
            os.makedirs(out_dir, exist_ok=True)
            for ext in (".png", ".txt", ".orig.txt", args.tags_ext):
                p = stem + ext
                if os.path.exists(p):
                    shutil.move(p, os.path.join(out_dir, os.path.basename(p)))
            moved += 1
    print("\nwrote %d captions%s" % (len(results), "; moved %d close-up fronts to %s" % (moved, out_dir) if moved else ""))
    print("kohya: image folder = the parent that contains the N_moemon folder, as before.")


if __name__ == "__main__":
    main()
