# xcstool

Split Xcode String Catalogs (`.xcstrings`) into one file per language and merge them back, so localization work can be divided among several people or LLM agents working at the same time. Also checks how much localization work is left and removes stale keys.

Pure Python (3.9+, the `/usr/bin/python3` that ships with Xcode), standard library only, BSD-2-Clause.

## Installation

```bash
pip install .
```

Or run it without installing, from a clone:

```bash
PYTHONPATH=src /usr/bin/python3 -m xcstool --help
```

## Usage

### split

```bash
xcstool split Localizable.xcstrings l10n/
```

Writes `l10n/Localizable.en.xcstrings`, `l10n/Localizable.es.xcstrings`, … one per language that has at least one localization in the catalog (source language included). Each file keeps all keys, their comments and the source-language values as context; only the target language differs. Existing files are overwritten and the directory is created if needed.

### merge

```bash
xcstool merge l10n/ Localizable.xcstrings
```

Updates the catalog (or creates it) with the translations from the directory:

- each split file contributes only the language in its file name (`Localizable.es.xcstrings` → `es`); the source-language context in other files is ignored;
- each key + language found in the directory overwrites the catalog's entry;
- nothing is ever deleted, and key-level fields (`comment`, `extractionState`, `shouldTranslate`, …) of existing keys never change.

A split followed by a merge with no edits leaves the catalog byte-identical: output follows Xcode's own JSON formatting so git diffs stay clean.

### checkup

```bash
xcstool checkup Localizable.xcstrings
xcstool checkup l10n/
```

Read-only report, per language, of keys that are missing, have a `new`/`needs_review` state, have incomplete plural (CLDR categories) or device variations, or are stale. The source language is a baseline unless `-s`/`--source-lang-is-translated` is given. `--verbose` lists the keys; `--strict` exits with 1 when work remains (for CI).

### rmstale

```bash
xcstool rmstale Localizable.xcstrings
```

Removes, in place, the keys whose `extractionState` is `stale`.

### Common options

`split`, `merge` and `rmstale` accept `--dry-run`; every subcommand accepts `--verbose`.

## Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | Success |
| 1 | `checkup --strict`: localization work remains |
| 2 | Command-line usage error |
| 3 | Path not found |
| 4 | Cannot read a file or directory |
| 5 | Cannot write a file or directory |
| 6 | Invalid JSON |
| 7 | Not a valid string catalog |
| 8 | Unsupported catalog version (only 1.x is supported) |
| 9 | Not a directory |
| 10 | No split files found in the directory |
| 11 | Split files of several catalogs in one directory |
| 12 | Source languages do not match |

## Development

```bash
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests
```

```bash
ruff format
```
