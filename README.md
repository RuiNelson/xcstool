# xcstool

Split Xcode String Catalogs (`.xcstrings`) into one file per language and merge them back, so localization work can be divided among several people or LLM agents working at the same time. Also checks how much localization work is left and removes stale keys.

Pure Python (3.9+, the `/usr/bin/python3` that ships with Xcode Command Line Tools), standard library only, BSD-2-Clause.

## Installation

### Claude Code plugin

In a [Claude Code](https://claude.com/claude-code) session:

```text
/plugin marketplace add RuiNelson/xcstool
/plugin install xcstool@xcstool
```

This repository is its own plugin marketplace. The plugin puts an `xcstool` command on the agent's `PATH` and brings a skill that teaches it the whole workflow, with nothing else to install. See [Skill for LLM agents](#skill-for-llm-agents) for sharing it with a team and for other agents.

### Command line

Install it with [uv](https://docs.astral.sh/uv/), straight from GitHub:

```bash
uv tool install git+https://github.com/RuiNelson/xcstool
```

Or from a clone of this repository, at its root:

```bash
uv tool install .
```

This puts an `xcstool` executable in uv's tool directory (`~/.local/bin` by default); run `uv tool update-shell` if it is not on your `PATH`. Without uv, run `pip install .` at the root of a clone instead (not `pip install -e .`, which the pip shipped with `/usr/bin/python3` does not support for this project).

### Without installing

With uv, fetch and run it in one go, leaving nothing on your `PATH`:

```bash
uvx --from git+https://github.com/RuiNelson/xcstool xcstool --help
```

From a clone of this repository, at its root:

```bash
PYTHONPATH=src python3 -m xcstool --help
```

From any other directory, run the clone's `bin/xcstool` wrapper, which sets `PYTHONPATH` itself. It can also be symlinked into a directory on your `PATH`:

```bash
ln -s "$PWD/bin/xcstool" ~/.local/bin/xcstool
```

### As a git submodule

To keep the tool inside an app's repository, for example in `tools/xcstool`, without installing anything:

```bash
git submodule add https://github.com/RuiNelson/xcstool tools/xcstool
```

Then run it through the submodule's `tools/xcstool` wrapper, here from the app's repository root:

```bash
tools/xcstool/bin/xcstool split MyApp/Localizable.xcstrings l10n/
```

```bash
tools/xcstool/bin/xcstool merge l10n/ MyApp/Localizable.xcstrings
```

```bash
tools/xcstool/bin/xcstool checkup MyApp/Localizable.xcstrings
```

After cloning the app's repository, fetch the submodule with `git submodule update --init`.

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

## Skill for LLM agents

[`skills/xcstool/SKILL.md`](skills/xcstool/SKILL.md) is an [Agent Skill](https://agentskills.io) that teaches coding agents (Claude Code and others that support the format) the split → translate → merge → checkup workflow (including adding a language by translating one string and splitting again) and how to edit split files: states, CLDR plural categories, device variations, substitutions and format specifiers. It also keeps their context window small: one language per agent, never reading a whole catalog, and only the keys still to translate, read and written in compact batches with the bundled [`scripts/l10n_slice.py`](skills/xcstool/scripts/l10n_slice.py).

### Claude Code plugin

With the plugin installed (see [Installation](#claude-code-plugin)), the skill loads by itself when you work on `.xcstrings` files, or run it with `/xcstool:xcstool`.

To share it with everyone working on an app, run these in the app's repository; they record the marketplace and the plugin in its `.claude/settings.json`, to be committed. Claude Code then offers to install them to each collaborator who trusts the repository folder:

```bash
claude plugin marketplace add RuiNelson/xcstool --scope project
```

```bash
claude plugin install xcstool@xcstool --scope project
```

Updates from third-party marketplaces are not automatic by default: turn them on in `/plugin` → Marketplaces, or run `/plugin marketplace update xcstool` and then update the plugin from `/plugin` → Installed.

### Skill only

For other agents, or without the plugin, link the skill into your personal skills directory (for Claude Code, `~/.claude/skills/`):

```bash
ln -s "$PWD/skills/xcstool" ~/.claude/skills/xcstool
```

Or, with the tool as a submodule in `bin/xcstool`, link it into the app's repository so everyone working on it gets it:

```bash
mkdir -p .claude/skills && ln -s ../../bin/xcstool/skills/xcstool .claude/skills/xcstool
```

## Development

```bash
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests
```

```bash
ruff format
```
