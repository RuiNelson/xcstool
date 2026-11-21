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

```text
xcstool [-h] [--version] COMMAND ...
```

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help and exit. Also works after a subcommand (`xcstool split --help`). |
| `--version` | Show the version and exit. |

### split

```text
xcstool split [-h] [--dry-run] [-v] INPUT_FILE OUTPUT_DIR
```

```bash
xcstool split Localizable.xcstrings l10n/
```

Writes `l10n/Localizable.en.xcstrings`, `l10n/Localizable.es.xcstrings`, … one per language that has at least one localization in the catalog (source language included). Each file keeps all keys, their comments and the source-language values as context; only the target language differs. Existing files are overwritten and the directory is created if needed.

| Argument / option | Description |
| --- | --- |
| `INPUT_FILE` | The `.xcstrings` file to split. |
| `OUTPUT_DIR` | Directory for the split files; created if it does not exist. |
| `--dry-run` | List the files that would be written, without creating the directory or writing anything. |
| `-v`, `--verbose` | List each file written, with how many keys are localized in it. |

### merge

```text
xcstool merge [-h] [--dry-run] [-v] INPUT_DIR OUTPUT_FILE
```

```bash
xcstool merge l10n/ Localizable.xcstrings
```

Updates the catalog (or creates it) with the translations from the directory:

- each split file contributes only the language in its file name (`Localizable.es.xcstrings` → `es`); the source-language context in other files is ignored;
- each key + language found in the directory overwrites the catalog's entry;
- nothing is ever deleted, and key-level fields (`comment`, `extractionState`, `shouldTranslate`, …) of existing keys never change.

A split followed by a merge with no edits leaves the catalog byte-identical: output follows Xcode's own JSON formatting so git diffs stay clean.

| Argument / option | Description |
| --- | --- |
| `INPUT_DIR` | Directory with the split files (`NAME.LANG.xcstrings`). If it holds split files of several catalogs, those whose `NAME` matches `OUTPUT_FILE` are used. |
| `OUTPUT_FILE` | The `.xcstrings` file to update; created if it does not exist. |
| `--dry-run` | List the changes (new keys, added and changed localizations) without writing anything. |
| `-v`, `--verbose` | List the changes made: `new key` for keys created, `+ [lang]` for added localizations, `~ [lang]` for changed ones. |

### checkup

```text
xcstool checkup [-h] [-s] [--strict] [-v] PATH
```

```bash
xcstool checkup Localizable.xcstrings
xcstool checkup l10n/
```

Read-only report, per language, of keys that are missing, have a `new`/`needs_review` state, have incomplete plural (CLDR categories) or device variations, or are stale. Keys with `shouldTranslate: false` are ignored.

| Argument / option | Description |
| --- | --- |
| `PATH` | A `.xcstrings` file, or a directory of split files (languages are taken from the file names; inconsistencies between files are reported as warnings). |
| `-s`, `--source-lang-is-translated` | Count the source language like any other language, for projects that use identifiers as keys (e.g. `BTN_DELETE` → "Delete"). Without it, the source language is only shown as a baseline. |
| `--strict` | Exit with code `1` if any work remains (stale keys do not count), for CI. Without it, the exit code is `0` whenever the check ran. |
| `-v`, `--verbose` | List the affected keys per language and category. |

### rmstale

```text
xcstool rmstale [-h] [--dry-run] [-v] FILE
```

```bash
xcstool rmstale Localizable.xcstrings
```

Removes, in place, the keys whose `extractionState` is `stale`, with all their localizations. Nothing else in the file changes. The number of removed keys is always printed.

| Argument / option | Description |
| --- | --- |
| `FILE` | The `.xcstrings` file to clean up. A directory is a usage error (exit code `2`). |
| `--dry-run` | List the keys that would be removed, without writing anything. |
| `-v`, `--verbose` | List the removed keys. |

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
