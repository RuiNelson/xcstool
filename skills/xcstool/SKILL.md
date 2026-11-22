---
name: xcstool
description: Translate and maintain Xcode String Catalogs (.xcstrings) with xcstool. Use when localizing an iOS/macOS app, translating a Localizable.xcstrings (or any .xcstrings) file, adding a new language to a catalog, dividing translation work per language among several agents or people, checking how much localization work is left (missing translations, needs_review, incomplete plural or device variations), or removing stale strings.
---

# xcstool

`xcstool` splits an Xcode String Catalog into one file per language, merges the translated files back, reports the localization work left, and removes stale keys. Its output matches Xcode's own JSON formatting, so git diffs stay clean.

**Never** translate by editing `.xcstrings` catalog in place: split it, work on the per-language files, merge, then check.

## Keep the context window small

A catalog holds every language: reading it puts each string's translations in all languages into the context. That wastes tokens and lets languages bleed into each other (pt-BR or es words showing up in a pt-PT translation). The whole point of the tool is to avoid this:

- **Never read a whole catalog or split file** (`cat`, a file-read tool, `head` of a big file). Use `xcstool checkup` for the state of the work: its summary is a few lines whatever the catalog's size.
- **One language per context.** An agent translating `de` never opens another language's split file, and never the main catalog.
- **Only the keys left to translate.** A split file still has every key, translated or not. Read just the pending ones in compact batches with the bundled script, and write the results back with it (see [Translating a split file](#translating-a-split-file)).
- **Orchestrate without the translations.** When coordinating several languages, run `checkup` and `split`, give each sub-agent only its split file's path and language, and ask it for a short report (keys translated, keys left as `needs_review` and why), not the translations. Then `merge` and run `checkup` again.
- **Quiet output.** Without `-v`, `merge` and `split` print one summary line; `-v` prints a line per change or file. Use `checkup -v` on a single split file (`xcstool checkup -v l10n/Localizable.de.xcstrings`) to list one language's keys instead of all of them.
- To keep terminology consistent with existing translations, search the split file for the term (`grep -n 'Einstellungen'`) instead of reading it.

## Running the tool

Use the first form that works:

1. `xcstool …` if it is on the `PATH` (check with `xcstool --version`). The Claude Code plugin puts it there while it is enabled.
2. From a clone or a git submodule (for example `tools/xcstool`): `tools/xcstool/bin/xcstool …`, or `PYTHONPATH=tools/xcstool/src python3 -m xcstool …`
3. Without installing, with uv: `uvx --from git+https://github.com/RuiNelson/xcstool xcstool …`

If it fails to run, it might be because it needs (only) Python 3.9+ and the standard library. The examples below write `xcstool` for whichever form applies.

## Workflow

```bash
xcstool checkup App/Localizable.xcstrings          # 1. what is left to do?
xcstool split App/Localizable.xcstrings l10n/      # 2. one file per language
# 3. translate l10n/Localizable.LANG.xcstrings (one language per file)
xcstool checkup -v l10n/                            # 4. verify the split files
xcstool merge l10n/ App/Localizable.xcstrings      # 5. write back into the catalog
xcstool checkup --strict App/Localizable.xcstrings # 6. exit 1 if work remains
```

- `split` writes `l10n/Localizable.en.xcstrings`, `l10n/Localizable.es.xcstrings`, … for every language that already has at least one localization (source language included). Each file holds all keys, their `comment`s and the source-language values as context, plus that one language's localizations.
- `split` **overwrites** existing files in the output directory. Never run it again on a directory with unmerged translations; merge first.
- `merge` takes from each file only the language in its file name and overwrites the matching key + language entries in the catalog. It never deletes anything and never changes key-level fields (`comment`, `extractionState`, `shouldTranslate`) of existing keys. The context copies of the source language in other files are ignored.
- All of `split`, `merge` and `rmstale` accept `--dry-run`; every subcommand accepts `-v`/`--verbose`.

### Dividing the work

Give each agent or person exactly one split file (`Localizable.de.xcstrings`, `Localizable.ja.xcstrings`, …). Files never conflict, so they can all be translated at the same time. Nobody edits the main catalog until the single `merge` at the end.

### Adding a new language

`split` creates a file for every language that has at least one localization in the catalog. To add a language (say `fr`), translate a single string into it and let `split` do the rest:

1. Translate one string into `fr`, preferably in Xcode: add the language to the project (Project → Info → Localizations) and translate one entry in the catalog editor. If Xcode is not available, ask the user to do this step. As a fallback, add one `"fr" : { "stringUnit" : { "state" : "translated", "value" : "…" } }` to a single key of the catalog; that is the only edit ever made to the catalog by hand.
2. Run `xcstool split`: it now writes `l10n/Localizable.fr.xcstrings` with every key, ready to translate like any other language.

Do not create a split file for a new language by hand.

## Editing a split file

Edit only the localizations of the file's own language. Do not add, remove or rename keys, and do not change `comment`, `extractionState`, `shouldTranslate` or the source-language values; `merge` ignores those anyway.

The split file's formatting does not matter: `merge` rewrites the catalog in Xcode's format.

### Translating a split file

[`scripts/l10n_slice.py`](scripts/l10n_slice.py) (next to this file; standard library only) reads and writes slices of one split file, taking the language from its name:

```bash
SLICE=path/to/skills/xcstool/scripts/l10n_slice.py
python3 $SLICE show l10n/Localizable.de.xcstrings --limit 50              # first batch of pending keys
python3 $SLICE show l10n/Localizable.de.xcstrings --limit 50 --offset 50  # next batch
python3 $SLICE apply l10n/Localizable.de.xcstrings de-batch1.json         # write translations back
```

- `show` prints one compact JSON line per key, `{"key", "comment", "source", "target"}`, where `source` and `target` are the localization objects of the source and target languages (`target` is `null` when missing). By default it lists keys whose target is missing or has a `stringUnit` not in state `translated`, skipping `shouldTranslate: false` and stale keys. A line on stderr says how many keys are left.
- Keys that `checkup -v` reports as **incomplete variations** may already be `translated`; show them with `--keys KEY …`.
- `apply` takes a JSON object mapping each key to its full target localization object (`{"stringUnit": …}`, or `{"variations": …}`, with `substitutions` if the source has them) and replaces that key's target localization. Unknown keys are an error and nothing is written.
- Write each batch's translations to a JSON file, apply it, then show the next batch. Already-applied keys are no longer pending, so with the default selection you can also keep running `show --limit 50` without `--offset`.

### Simple string

```json
"greeting" : {
  "comment" : "Welcome message on the home screen",
  "localizations" : {
    "en" : { "stringUnit" : { "state" : "translated", "value" : "Hello" } },
    "de" : { "stringUnit" : { "state" : "translated", "value" : "Hallo" } }
  }
}
```

### States

- `translated`: done. Set this for every string you translate with confidence.
- `needs_review`: translated but uncertain (ambiguous source, missing context, length constraints). It is reported as work by `checkup`.
- `new`: not translated yet.

Never copy the source text as a translation just to fill a gap. Leave the key out, or mark it `needs_review` with your best attempt.

### Plural variations

Mirror the source's `variations.plural`, but use the categories that the **target** language needs (CLDR plural rules), not the source's:

| Categories | Examples |
| --- | --- |
| `other` | ja, zh, ko, th, vi, id |
| `one`, `other` | en, de, nl, sv, da, fi, el, tr, hi |
| `one`, `many`, `other` | fr, es, it, ca, pt, pt-PT, pt-BR (`many` is for large round numbers, e.g. 1 000 000) |
| `one`, `two`, `other` | he |
| `one`, `few`, `other` | ro, hr, sr, bs |
| `one`, `few`, `many`, `other` | ru, uk, pl, cs, sk, lt |
| `zero`, `one`, `two`, `few`, `many`, `other` | ar, cy |

Region subtags fall back to the base language (`pt-BR` → `pt`, `zh-Hant` → `zh`).

`checkup` knows the full CLDR table and reports missing categories as "incomplete variations"; trust it over this summary.

```json
"de" : {
  "variations" : {
    "plural" : {
      "one" :   { "stringUnit" : { "state" : "translated", "value" : "%lld Haus" } },
      "other" : { "stringUnit" : { "state" : "translated", "value" : "%lld Häuser" } }
    }
  }
}
```

### Device variations

If the source has `variations.device` (`iphone`, `ipad`, `mac`, `applewatch`, `appletv`, `applevision`, `other`), provide the same device keys in the target language. Device and plural variations can be nested (device first, then plural inside each device).

### Substitutions

A value such as `"%#@files@ in %#@folders@"` refers to entries under the localization's `substitutions`. Each substitution has its own `variations.plural` (with `argNum` and `formatSpecifier`). Translate the main `stringUnit`, keep every `%#@name@` token, and give each substitution the plural categories of the target language.

### Format specifiers and markup

- Keep every format specifier exactly: `%@`, `%lld`, `%d`, `%f`, `%.1f`, `%%`, `%#@name@`.
- To reorder arguments, use positional forms (`%1$@`, `%2$lld`) and keep each argument's type.
- Keep `\n`, Markdown (`**bold**`, `[link](url)`), and leading or trailing spaces and punctuation that the UI depends on.
- Use the key's `comment` as context; it is often the only hint about where the string appears.

## checkup

```bash
xcstool checkup App/Localizable.xcstrings
xcstool checkup -v l10n/
```

Reports per language the keys that are missing, have state `new`/`needs_review`, have incomplete plural or device variations (including inside substitutions), or are stale. `-v` lists the keys. Keys with `shouldTranslate: false` are ignored.

- The source language is a baseline and never counts as work, unless the project uses identifiers as keys (`BTN_DELETE` → "Delete"); then pass `-s`/`--source-lang-is-translated`.
- It exits with `0` whenever it ran; with `--strict` it exits with `1` if work remains (stale keys do not count).
- Given a directory, it warns when the split files disagree (different keys or `sourceLanguage`), which usually means a stale split: merge what is there, then split again.

## rmstale

```bash
xcstool rmstale --dry-run -v App/Localizable.xcstrings
xcstool rmstale App/Localizable.xcstrings
```

Removes, in place, every key with `extractionState: "stale"` (strings Xcode no longer finds in the code). Do not translate stale keys; ask before removing them if the user did not request it, since they may be used in code Xcode does not scan. `merge` never deletes, so stale keys are removed only with `rmstale` on the main catalog.

## Errors

Errors go to stderr with a non-zero exit code: `2` usage error, `3` path not found, `6` invalid JSON, `7` not a string catalog, `8` unsupported catalog version, `10` no split files in the directory, `11` split files of several catalogs in one directory, `12` source languages do not match. Invalid JSON after editing a split file is the most common one: fix the file and run `merge` again; nothing was written.
