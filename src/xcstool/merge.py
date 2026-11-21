"""The ``merge`` subcommand: update a catalog with the translations of split files."""

import json
import os
from typing import Any, Dict, List, Tuple

from xcstool.catalog import (
    Catalog,
    SplitFile,
    catalog_stem,
    find_split_files,
    insert_sorted,
    merge_order,
    read_catalog,
    write_catalog,
)
from xcstool.errors import ExitCode, XcstoolError


class MergeResult:
    def __init__(self) -> None:
        self.added_keys: List[str] = []
        self.added: List[Tuple[str, str]] = []
        self.changed: List[Tuple[str, str]] = []
        self.unchanged = 0


def _source_language(parts: List[Tuple[SplitFile, Catalog]]) -> str:
    found: Dict[str, List[str]] = {}
    for split_file, data in parts:
        found.setdefault(data["sourceLanguage"], []).append(os.path.basename(split_file.path))
    if len(found) > 1:
        details = "; ".join(
            "%s in %s" % (lang, ", ".join(names)) for lang, names in sorted(found.items())
        )
        raise XcstoolError(
            ExitCode.SOURCE_LANGUAGE_MISMATCH,
            "the split files disagree on sourceLanguage (%s)" % details,
        )
    return next(iter(found))


def merge_catalog(target: Catalog, parts: List[Tuple[SplitFile, Catalog]]) -> MergeResult:
    """Merge split catalogs into ``target`` (modified in place).

    Each split file contributes only the localization of the language in its
    file name. Key-level fields of existing keys never change; new keys take
    them from the source-language split file if present, otherwise from the
    first split file in alphabetical order. Nothing is ever deleted.
    """
    result = MergeResult()
    source = target["sourceLanguage"]
    # Source-language file first, then the others in file-name order.
    ordered = [p for p in parts if p[0].language == source] + [
        p for p in parts if p[0].language != source
    ]

    templates: Dict[str, Dict[str, Any]] = {}
    incoming_order: List[str] = []
    for _, data in ordered:
        incoming_order = merge_order(incoming_order, data["strings"])
        for key, entry in data["strings"].items():
            templates.setdefault(key, entry)

    strings = target["strings"]
    new_strings: Dict[str, Any] = {}
    created = set()
    for key in merge_order(list(strings), incoming_order):
        if key in strings:
            new_strings[key] = strings[key]
            continue
        template = templates[key]
        new_strings[key] = {
            field: ({} if field == "localizations" else value) for field, value in template.items()
        }
        created.add(key)
        result.added_keys.append(key)

    for split_file, data in parts:
        language = split_file.language
        for key, entry in data["strings"].items():
            localization = entry.get("localizations", {}).get(language)
            if localization is None:
                continue
            target_entry = new_strings[key]
            localizations = target_entry.get("localizations")
            if localizations is None:
                new_strings[key] = insert_sorted(
                    target_entry, "localizations", {language: localization}
                )
                result.added.append((key, language))
                continue
            previous = localizations.get(language)
            if previous is None:
                result.added.append((key, language))
            elif previous == localization:
                result.unchanged += 1
            else:
                result.changed.append((key, language))
            target_entry["localizations"] = insert_sorted(localizations, language, localization)

    for key in created:
        if new_strings[key].get("localizations") == {}:
            del new_strings[key]["localizations"]

    target["strings"] = new_strings
    return result


def _new_catalog(parts: List[Tuple[SplitFile, Catalog]], source: str) -> Catalog:
    base = next((data for split_file, data in parts if split_file.language == source), parts[0][1])
    return {field: ({} if field == "strings" else value) for field, value in base.items()}


def _quote(key: str) -> str:
    return json.dumps(key, ensure_ascii=False)


def run_merge(input_dir: str, output_path: str, dry_run: bool, verbose: bool, out) -> int:
    split_files = find_split_files(
        input_dir, prefer_stem=catalog_stem(output_path), exclude=[output_path]
    )
    parts = [(split_file, read_catalog(split_file.path)) for split_file in split_files]
    source = _source_language(parts)

    exists = os.path.exists(output_path)
    if exists:
        target = read_catalog(output_path)
        if target["sourceLanguage"] != source:
            raise XcstoolError(
                ExitCode.SOURCE_LANGUAGE_MISMATCH,
                "%s has sourceLanguage %r but the split files have %r"
                % (output_path, target["sourceLanguage"], source),
            )
    else:
        target = _new_catalog(parts, source)

    result = merge_catalog(target, parts)

    if verbose or dry_run:
        for key in result.added_keys:
            out.write("  new key %s\n" % _quote(key))
        for key, language in result.added:
            out.write("  + [%s] %s\n" % (language, _quote(key)))
        for key, language in result.changed:
            out.write("  ~ [%s] %s\n" % (language, _quote(key)))

    if not dry_run:
        write_catalog(output_path, target)

    languages = ", ".join(split_file.language for split_file in split_files)
    verb = "Would merge" if dry_run else "Merged"
    created = " (new file)" if not exists else ""
    out.write(
        "%s %d split files (%s) into %s%s: %d keys added, %d localizations added, "
        "%d changed, %d unchanged\n"
        % (
            verb,
            len(split_files),
            languages,
            output_path,
            created,
            len(result.added_keys),
            len(result.added),
            len(result.changed),
            result.unchanged,
        )
    )
    return ExitCode.SUCCESS
