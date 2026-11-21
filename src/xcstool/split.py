"""The ``split`` subcommand: one file per language."""

import os
from typing import Any, Dict, TextIO

from xcstool.catalog import (
    Catalog,
    catalog_stem,
    languages_of,
    read_catalog,
    split_file_name,
    write_catalog,
)
from xcstool.errors import ExitCode, XcstoolError


def split_for_language(data: Catalog, language: str) -> Catalog:
    """The split catalog for one language.

    It keeps the catalog metadata, every key with its key-level fields and the
    source-language localization as context; of the other localizations only
    ``language``'s is kept.
    """
    keep = {data["sourceLanguage"], language}
    result: Catalog = {}
    for field, value in data.items():
        if field != "strings":
            result[field] = value
            continue
        strings: Dict[str, Any] = {}
        for key, entry in value.items():
            new_entry: Dict[str, Any] = {}
            for entry_field, entry_value in entry.items():
                if entry_field == "localizations":
                    kept = {lang: loc for lang, loc in entry_value.items() if lang in keep}
                    if kept:
                        new_entry[entry_field] = kept
                else:
                    new_entry[entry_field] = entry_value
            strings[key] = new_entry
        result[field] = strings
    return result


def run_split(input_path: str, output_dir: str, dry_run: bool, verbose: bool, out: TextIO) -> int:
    data = read_catalog(input_path)
    if os.path.exists(output_dir) and not os.path.isdir(output_dir):
        raise XcstoolError(ExitCode.NOT_A_DIRECTORY, "%s: not a directory" % output_dir)
    stem = catalog_stem(input_path)
    languages = languages_of(data)
    if not dry_run:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            raise XcstoolError(
                ExitCode.WRITE_ERROR,
                "%s: cannot create directory (%s)" % (output_dir, exc.strerror),
            ) from None
    for language in languages:
        path = os.path.join(output_dir, split_file_name(stem, language))
        part = split_for_language(data, language)
        if verbose or dry_run:
            translated = sum(
                1
                for entry in part["strings"].values()
                if language in entry.get("localizations", {})
            )
            action = "Would write" if dry_run else "Writing"
            out.write(
                "%s %s (%d of %d keys localized)\n"
                % (action, path, translated, len(part["strings"]))
            )
        if not dry_run:
            write_catalog(path, part)
    verb = "Would split" if dry_run else "Split"
    out.write(
        "%s %s into %d files in %s (languages: %s; source: %s)\n"
        % (
            verb,
            input_path,
            len(languages),
            output_dir,
            ", ".join(languages),
            data["sourceLanguage"],
        )
    )
    return ExitCode.SUCCESS
