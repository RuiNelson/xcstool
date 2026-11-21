"""The ``checkup`` subcommand: a read-only report of the localization work left."""

import json
import os
import sys
from collections import Counter
from typing import Any, FrozenSet, List, Optional, TextIO, Tuple

from xcstool.catalog import (
    Catalog,
    find_split_files,
    is_stale,
    languages_of,
    read_catalog,
    should_translate,
    sort_key,
)
from xcstool.errors import ExitCode
from xcstool.plurals import required_categories

REVIEW_STATES = frozenset({"new", "needs_review"})


class LanguageReport:
    def __init__(self, language: str, counted: bool) -> None:
        self.language = language
        self.counted = counted
        self.missing: List[str] = []
        self.review: List[str] = []
        self.variations: List[str] = []
        self.stale: List[str] = []

    @property
    def work(self) -> int:
        return len(self.missing) + len(self.review) + len(self.variations)


def has_review_state(node: Any) -> bool:
    """Whether any string unit in a localization (variations included) is new or needs review."""
    if isinstance(node, dict):
        unit = node.get("stringUnit")
        if isinstance(unit, dict) and unit.get("state") in REVIEW_STATES:
            return True
        return any(has_review_state(value) for value in node.values())
    if isinstance(node, list):
        return any(has_review_state(value) for value in node)
    return False


def has_incomplete_variations(node: Any, source_node: Any, required: FrozenSet[str]) -> bool:
    """Whether a localization has incomplete plural or device variations.

    A plural variation must have every category the language requires; every
    device variation of the source language must exist; substitutions are
    checked by the same rules.
    """
    if not isinstance(node, dict):
        return False
    source_node = source_node if isinstance(source_node, dict) else {}
    variations = node.get("variations")
    variations = variations if isinstance(variations, dict) else {}
    source_variations = source_node.get("variations")
    source_variations = source_variations if isinstance(source_variations, dict) else {}

    source_device = source_variations.get("device")
    source_device = source_device if isinstance(source_device, dict) else {}
    device = variations.get("device")
    if source_device and (not isinstance(device, dict) or set(source_device) - set(device)):
        return True
    if isinstance(device, dict):
        for name, value in device.items():
            if has_incomplete_variations(value, source_device.get(name), required):
                return True

    plural = variations.get("plural")
    if isinstance(plural, dict):
        if required - set(plural):
            return True
        for value in plural.values():
            if has_incomplete_variations(value, None, required):
                return True

    substitutions = node.get("substitutions")
    if isinstance(substitutions, dict):
        source_substitutions = source_node.get("substitutions")
        source_substitutions = (
            source_substitutions if isinstance(source_substitutions, dict) else {}
        )
        for name, value in substitutions.items():
            if has_incomplete_variations(value, source_substitutions.get(name), required):
                return True
    return False


def analyze_language(data: Catalog, language: str, counted: bool) -> LanguageReport:
    report = LanguageReport(language, counted)
    source = data["sourceLanguage"]
    required = required_categories(language)
    for key, entry in data["strings"].items():
        if not should_translate(entry):
            continue
        if is_stale(entry):
            report.stale.append(key)
            continue
        localizations = entry.get("localizations", {})
        localization = localizations.get(language)
        if localization is None:
            if counted:
                report.missing.append(key)
            continue
        if counted and has_review_state(localization):
            report.review.append(key)
        source_localization = None if language == source else localizations.get(source)
        if has_incomplete_variations(localization, source_localization, required):
            report.variations.append(key)
    return report


def _inputs_from_directory(path: str, err: TextIO) -> Tuple[str, List[Tuple[str, Catalog]]]:
    split_files = find_split_files(path)
    inputs = [(split_file.language, read_catalog(split_file.path)) for split_file in split_files]
    names = {split_file.language: os.path.basename(split_file.path) for split_file in split_files}

    sources = Counter(data["sourceLanguage"] for _, data in inputs)
    source = sources.most_common(1)[0][0]
    if len(sources) > 1:
        details = ", ".join(
            "%s (%s)" % (names[language], data["sourceLanguage"]) for language, data in inputs
        )
        err.write("warning: the split files disagree on sourceLanguage: %s\n" % details)

    all_keys = set()
    for _, data in inputs:
        all_keys.update(data["strings"])
    for language, data in inputs:
        missing = len(all_keys - set(data["strings"]))
        if missing:
            err.write(
                "warning: %s lacks %d key%s present in other split files\n"
                % (names[language], missing, "" if missing == 1 else "s")
            )
    return source, inputs


def _table(rows: List[List[str]]) -> List[str]:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = []
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [
            cell.rjust(width) for cell, width in zip(row[1:], widths[1:])
        ]
        lines.append("  ".join(cells).rstrip())
    return lines


def run_checkup(
    path: str,
    source_is_translated: bool,
    strict: bool,
    verbose: bool,
    out: TextIO,
    err: Optional[TextIO] = None,
) -> int:
    err = err if err is not None else sys.stderr
    if os.path.isdir(path):
        source, inputs = _inputs_from_directory(path, err)
        description = "%s (%d split files)" % (path, len(inputs))
    else:
        data = read_catalog(path)
        source = data["sourceLanguage"]
        inputs = [(language, data) for language in languages_of(data)]
        description = path
    inputs.sort(key=lambda item: sort_key(item[0]))

    reports = [
        analyze_language(data, language, language != source or source_is_translated)
        for language, data in inputs
    ]

    key_count = len({key for _, data in inputs for key in data["strings"]})
    ignored = len(
        {key for _, data in inputs for key, e in data["strings"].items() if not should_translate(e)}
    )
    out.write("Catalog: %s\n" % description)
    out.write(
        "Source language: %s; %d keys%s\n\n"
        % (
            source,
            key_count,
            " (%d with shouldTranslate: false, ignored)" % ignored if ignored else "",
        )
    )

    rows = [["Language", "Missing", "New/review", "Variations", "Stale"]]
    totals = [0, 0, 0, 0]
    has_baseline = False
    for report in reports:
        if report.counted:
            counts = [
                len(report.missing),
                len(report.review),
                len(report.variations),
                len(report.stale),
            ]
            totals = [total + count for total, count in zip(totals, counts)]
            name = report.language + (" (source)" if report.language == source else "")
            rows.append([name] + [str(count) for count in counts])
        else:
            has_baseline = True
            rows.append(
                [
                    report.language + " (source)*",
                    "-",
                    "-",
                    str(len(report.variations)),
                    str(len(report.stale)),
                ]
            )
    rows.append(["Total"] + [str(total) for total in totals])
    for line in _table(rows):
        out.write(line + "\n")
    if has_baseline:
        out.write("\n* Source language shown as a baseline; it does not count as work")
        out.write(" (use --source-lang-is-translated to count it).\n")

    if verbose:
        for report in reports:
            sections = [
                ("missing", report.missing if report.counted else []),
                ("new or needs_review", report.review if report.counted else []),
                ("incomplete variations", report.variations),
                ("stale", report.stale),
            ]
            if not any(keys for _, keys in sections):
                continue
            out.write("\n%s:\n" % report.language)
            for title, keys in sections:
                if keys:
                    out.write("  %s (%d):\n" % (title, len(keys)))
                    for key in keys:
                        out.write("    %s\n" % json.dumps(key, ensure_ascii=False))

    work = sum(report.work for report in reports if report.counted)
    stale_keys = {key for report in reports for key in report.stale}
    out.write("\n")
    if work:
        languages = sum(1 for report in reports if report.counted and report.work)
        out.write(
            "Localization work remains: %d item%s in %d language%s.\n"
            % (work, "" if work == 1 else "s", languages, "" if languages == 1 else "s")
        )
    else:
        out.write("No localization work left.\n")
    if stale_keys:
        out.write(
            "%d stale key%s (not found in the source code); remove with `xcstool rmstale`.\n"
            % (len(stale_keys), "" if len(stale_keys) == 1 else "s")
        )
    if strict and work:
        return ExitCode.WORK_REMAINING
    return ExitCode.SUCCESS
