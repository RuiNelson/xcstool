# CLAUDE.md / AGENTS.md

This repository contains a tool to manipulate Xcode Apple String Catalog files (`.xcstrings`), which are JSON files.

The tool is free and open-source (BSD-2-Clause license), written in Python (minimum version 3.9.6, see [Python version](#python-version)) and has no external dependencies (users can run it without a venv or installing any libraries). Use only the standard library.

## Functionality

The tool splits an `.xcstrings` file into several files, one per localization language, and merges them back into a single file.

The goal is to make it easier to divide localization work among several humans or several LLM agents working simultaneously.

### Command line

Use the `split` subcommand:

```bash
xcstool split input-file.xcstrings output-directory/
```

Files named `input-file.pt-PT.xcstrings`, `input-file.en.xcstrings`, `input-file.es.xcstrings`, etc. are written to the output directory, according to the localizations present in the input file (including the source language). A language gets its own file as soon as at least one key has a localization in that language. Languages that exist only in the Xcode project, with no localization in the catalog yet, cannot be detected; translating a single string in Xcode is enough to make them appear.

Existing files in that directory are silently overwritten (the tool is meant for environments with version control, such as git). The output directory is created if it does not exist.

Each split file keeps the catalog metadata (`version`, `sourceLanguage`), all keys, their comments and the source-language values as context for translators; only the target language's localizations differ between files.

Or use the `merge` subcommand:

```bash
xcstool merge input-directory/ output-file.xcstrings
```

This **updates** the output file with the translations found in the directory, adding and/or changing localizations. Rules:

- Each split file contributes only the language in its file name (`input-file.es.xcstrings` → `es`); any other localization in it, including the source-language values kept as context, is ignored. Source-language values therefore change only through the source-language split file, so a stale context copy in another file can never revert a source text edited in Xcode after the split.
- Per-key overwrite: each key + language entry contributed by the directory overwrites the matching entry in the output file.
- Keys or languages that are missing from the directory are left untouched; nothing is ever deleted.
- Key-level fields (`comment`, `extractionState`, `shouldTranslate`, etc.) are never changed for a key that already exists in the output file; if the split files have different values, they are ignored. When the merge creates a new key, these fields are copied from the source-language split file if present, otherwise from the first split file in alphabetical order.
- If the output file does not exist, it is created.

Or use the `checkup` subcommand, a quick read-only check of whether there is localization work left to do:

```bash
xcstool checkup catalog.xcstrings
xcstool checkup split-directory/
```

The argument is either a single `.xcstrings` file or a directory of split files. It prints a summary per language (including totals) with the number of keys that:

- are missing a translation entirely;
- have a translation whose state is `new` or `needs_review`;
- have incomplete variations (see below);
- are marked stale (`extractionState: "stale"`), reported separately since they usually need removing rather than translating.

A key has incomplete variations for a language when:

- a plural variation lacks a category that the language requires under the CLDR plural rules (for example, Russian needs `one`, `few`, `many` and `other`; Japanese only `other`). Since there are no external dependencies, the tool embeds a table of the CLDR plural categories per language;
- a device variation that exists in the source language is missing in that language;
- any of the localization's `substitutions` has incomplete variations by the same two rules.

Keys with `shouldTranslate: false` are ignored. By default the source language is reported as a baseline and never counts as work. Some projects use identifiers as keys (for example `BTN_DELETE`) and translate the source language too (e.g. `en` → "Delete"); for those, `--source-lang-is-translated` (short form `-s`) makes the source language count like any other language, so missing or `new`/`needs_review` source entries are reported as work. With `--verbose`, the affected keys are listed per language.

`checkup` never writes anything. It exits with 0 whenever it ran successfully, whether or not work remains; with `--strict` it exits with 1 if any work remains (so it can be used in CI). Real errors use the error exit codes described under [Common behavior](#common-behavior).

When given a directory, the languages are taken from the file names, and any inconsistency between the files (different keys or different `sourceLanguage`) is reported as a warning.

Or use the `rmstale` subcommand, to remove stale entries (keys Xcode no longer finds in the source code):

```bash
xcstool rmstale catalog.xcstrings
```

The argument is a single `.xcstrings` file, modified in place (the tool is meant for environments with version control). A key is removed, with all its localizations, when its `extractionState` is `"stale"`. Keys in any other state, or with no `extractionState`, are never touched, and nothing else in the file changes. This matches what `checkup` reports as stale. With `--verbose`, the removed keys are listed; with `--dry-run`, they are listed without writing anything. The number of removed keys is always printed.

Passing a directory is a command-line usage error (exit code `2`, with a message on stderr saying a file is expected).

Note that `merge` never deletes anything, so stale keys are removed from the main catalog by running `rmstale` on it directly.

### Common behavior

- Output JSON must match Xcode's own formatting (2-space indent, `"key" : value` spacing, key order) so git diffs stay clean. A split followed by a merge with no edits must leave the file byte-identical.
- Errors (invalid JSON, missing paths, unsupported catalog version, etc.) produce a clear message on stderr and a non-zero exit code.
- Error kinds are defined in a single `IntEnum`, with one member per error; the member's value is the process exit code, so each error has its own code. `0` is success, `1` is reserved for `checkup --strict` when work remains, `2` is a command-line usage error (argparse's default), and the other errors start at `3`.
- `split`, `merge` and `rmstale` accept `--dry-run` (report what would change without writing anything); all four subcommands accept `--verbose`.

## Python version

The minimum supported version is Python 3.9.6, the `/usr/bin/python3` that ships with Xcode. The `python3` found first on the `PATH` may be a much newer one (for example, from Homebrew) that accepts code 3.9 rejects, so:

- Always run the tool and the tests with `/usr/bin/python3`, never with a bare `python3`.
- Do not use syntax, modules or parameters newer than 3.9, such as `match` statements, `X | Y` type unions (use `Optional`/`Union`), parenthesized context managers, `zip(strict=...)`, `dataclass(slots=..., kw_only=...)`, `tomllib`, `ExceptionGroup`/`except*` or `typing.Self`.
- The pip shipped with it (21.2.4) does not support editable installs of a `pyproject.toml`-only project (PEP 660), so `pip install -e .` fails; a regular `pip install .` works.

## Code organization and git hygiene

Use the common Python project layout: `pyproject.toml` with a `src/` layout and an `xcstool` console script. The tool must also run without installation via `python -m xcstool` (with `src` on `PYTHONPATH`, see the commands below).

Tests use `unittest` from the standard library (no pytest dependency), under `tests/`.

Commands, from the repository root:

```bash
PYTHONPATH=src /usr/bin/python3 -m xcstool --help
```

```bash
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests
```

```bash
ruff format
```

Run the formatter (`ruff format`) before every commit. Ruff is configured in `pyproject.toml` with `target-version = "py39"`; it is a development tool only and never a dependency of xcstool itself.

All code and documentation in English.

Use Conventional Commits 1.0.0 for commit messages.
