#!/usr/bin/env python3
"""Show or apply a slice of one split file, so an agent never reads the whole file.

    l10n_slice.py show  SPLIT_FILE [--keys KEY ...] [--limit N] [--offset N]
    l10n_slice.py apply SPLIT_FILE TRANSLATIONS.json

The language comes from the file name (NAME.LANG.xcstrings).

show prints one compact JSON line per key: {"key", "comment", "source", "target"},
where source and target are the localization objects of the source and target
languages (target is null when missing). Without --keys, it prints the keys still
to translate: target missing, or any stringUnit in it whose state is not
"translated". Keys with shouldTranslate false or extractionState "stale" are skipped.
Pass --keys for the keys that `xcstool checkup -v` reports as incomplete variations.

apply reads a JSON object {key: localization object} and sets each one as the
target-language localization of that key. Unknown keys are an error and nothing
is written. Standard library only, Python 3.9+.
"""

import argparse
import json
import sys
from pathlib import Path


def language_of(path):
    parts = Path(path).name.split(".")
    if len(parts) < 3 or parts[-1] != "xcstrings":
        sys.exit(f"error: {path}: expected a split file named NAME.LANG.xcstrings")
    return parts[-2]


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"error: {path}: {e}")


def untranslated(node):
    """True if any stringUnit under node has a state other than "translated"."""
    if isinstance(node, dict):
        unit = node.get("stringUnit")
        if isinstance(unit, dict) and unit.get("state", "translated") != "translated":
            return True
        return any(untranslated(v) for k, v in node.items() if k != "stringUnit")
    return False


def show(args):
    catalog = load(args.file)
    lang = language_of(args.file)
    source = catalog.get("sourceLanguage")
    strings = catalog.get("strings", {})
    if args.keys:
        missing = [k for k in args.keys if k not in strings]
        if missing:
            sys.exit(f"error: unknown keys: {', '.join(missing)}")
        keys = args.keys
    else:
        keys = []
        for key, entry in strings.items():
            if entry.get("shouldTranslate") is False or entry.get("extractionState") == "stale":
                continue
            target = entry.get("localizations", {}).get(lang)
            if target is None or untranslated(target):
                keys.append(key)
    selected = keys[args.offset :]
    if args.limit is not None:
        selected = selected[: args.limit]
    for key in selected:
        entry = strings[key]
        localizations = entry.get("localizations", {})
        line = {
            "key": key,
            "comment": entry.get("comment"),
            "source": localizations.get(source),
            "target": localizations.get(lang),
        }
        print(json.dumps(line, ensure_ascii=False, separators=(",", ":")))
    shown_to = args.offset + len(selected)
    print(
        f"# {lang}: showed {len(selected)} of {len(keys)} keys ({shown_to} so far)", file=sys.stderr
    )


def apply(args):
    catalog = load(args.file)
    lang = language_of(args.file)
    translations = load(args.translations)
    if not isinstance(translations, dict):
        sys.exit(f"error: {args.translations}: expected a JSON object {{key: localization}}")
    strings = catalog.get("strings", {})
    unknown = [k for k in translations if k not in strings]
    if unknown:
        sys.exit(f"error: unknown keys, nothing written: {', '.join(unknown)}")
    for key, localization in translations.items():
        strings[key].setdefault("localizations", {})[lang] = localization
    with open(args.file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{lang}: set {len(translations)} localizations in {args.file}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("show", help="print the keys to translate, one compact JSON line each")
    p.add_argument("file")
    p.add_argument("--keys", nargs="+", help="show these keys instead of the untranslated ones")
    p.add_argument("--limit", type=int, help="show at most N keys")
    p.add_argument("--offset", type=int, default=0, help="skip the first N keys")
    p.set_defaults(func=show)
    p = sub.add_parser("apply", help="write translations from a JSON file into the split file")
    p.add_argument("file")
    p.add_argument("translations")
    p.set_defaults(func=apply)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
