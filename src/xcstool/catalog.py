"""Loading, validating and saving String Catalogs, and locating split files."""

import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple

from xcstool import jsonfmt
from xcstool.errors import ExitCode, XcstoolError

EXTENSION = ".xcstrings"

_SUPPORTED_VERSION = re.compile(r"^1\.\d+$")
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{1,8})*$")

Catalog = Dict[str, Any]


def read_catalog(path: str) -> Catalog:
    """Read and validate a String Catalog file."""
    if not os.path.exists(path):
        raise XcstoolError(ExitCode.PATH_NOT_FOUND, "%s: no such file" % path)
    if os.path.isdir(path):
        raise XcstoolError(ExitCode.READ_ERROR, "%s: is a directory, a file was expected" % path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        raise XcstoolError(
            ExitCode.READ_ERROR, "%s: not valid UTF-8 (%s)" % (path, exc.reason)
        ) from None
    except OSError as exc:
        raise XcstoolError(
            ExitCode.READ_ERROR, "%s: cannot read file (%s)" % (path, exc.strerror)
        ) from None
    try:
        data = jsonfmt.loads(text)
    except ValueError as exc:
        raise XcstoolError(ExitCode.INVALID_JSON, "%s: invalid JSON (%s)" % (path, exc)) from None
    validate_catalog(data, path)
    return data


def validate_catalog(data: Any, path: str) -> None:
    """Check the structure of a String Catalog, raising a clear error if it is wrong."""

    def invalid(reason: str) -> XcstoolError:
        return XcstoolError(
            ExitCode.INVALID_CATALOG, "%s: not a valid string catalog (%s)" % (path, reason)
        )

    if not isinstance(data, dict):
        raise invalid("the top level is not a JSON object")
    version = data.get("version")
    if version is None:
        raise invalid('missing "version"')
    if not isinstance(version, str) or isinstance(version, jsonfmt.RawNumber):
        raise invalid('"version" is not a string')
    if not _SUPPORTED_VERSION.match(version):
        raise XcstoolError(
            ExitCode.UNSUPPORTED_VERSION,
            "%s: unsupported string catalog version %r (supported: 1.x)" % (path, version),
        )
    source = data.get("sourceLanguage")
    if not isinstance(source, str) or isinstance(source, jsonfmt.RawNumber) or not source:
        raise invalid('missing or invalid "sourceLanguage"')
    strings = data.get("strings")
    if not isinstance(strings, dict):
        raise invalid('missing or invalid "strings"')
    for key, entry in strings.items():
        if not isinstance(entry, dict):
            raise invalid("the entry for key %r is not an object" % key)
        localizations = entry.get("localizations")
        if localizations is None:
            continue
        if not isinstance(localizations, dict):
            raise invalid('"localizations" of key %r is not an object' % key)
        for language, localization in localizations.items():
            if not isinstance(localization, dict):
                raise invalid("localization %r of key %r is not an object" % (language, key))


def write_catalog(path: str, data: Catalog) -> None:
    """Write a String Catalog with Xcode's formatting."""
    text = jsonfmt.dumps(data)
    try:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    except OSError as exc:
        raise XcstoolError(
            ExitCode.WRITE_ERROR, "%s: cannot write file (%s)" % (path, exc.strerror)
        ) from None


def languages_of(data: Catalog) -> List[str]:
    """All languages of a catalog: the source language plus every localized language."""
    found = {data["sourceLanguage"]}
    for entry in data["strings"].values():
        found.update(entry.get("localizations", {}))
    return sorted(found, key=sort_key)


def is_stale(entry: Dict[str, Any]) -> bool:
    return entry.get("extractionState") == "stale"


def should_translate(entry: Dict[str, Any]) -> bool:
    return entry.get("shouldTranslate") is not False


# --- Split files ------------------------------------------------------------


class SplitFile(NamedTuple):
    stem: str
    language: str
    path: str


def split_file_name(stem: str, language: str) -> str:
    return "%s.%s%s" % (stem, language, EXTENSION)


def parse_split_file_name(name: str) -> Optional[Tuple[str, str]]:
    """Return ``(stem, language)`` for ``stem.language.xcstrings``, or None."""
    if not name.endswith(EXTENSION):
        return None
    base = name[: -len(EXTENSION)]
    stem, dot, language = base.rpartition(".")
    if not dot or not stem or not _LANGUAGE.match(language):
        return None
    return stem, language


def find_split_files(
    directory: str, prefer_stem: Optional[str] = None, exclude: Iterable[str] = ()
) -> List[SplitFile]:
    """Find the split files of a single catalog in a directory, sorted by file name.

    If the directory holds split files of several catalogs (different stems),
    ``prefer_stem`` picks one; otherwise it is an error.
    """
    if not os.path.exists(directory):
        raise XcstoolError(ExitCode.PATH_NOT_FOUND, "%s: no such directory" % directory)
    if not os.path.isdir(directory):
        raise XcstoolError(ExitCode.NOT_A_DIRECTORY, "%s: not a directory" % directory)
    excluded = {os.path.realpath(path) for path in exclude}
    try:
        names = sorted(os.listdir(directory))
    except OSError as exc:
        raise XcstoolError(
            ExitCode.READ_ERROR, "%s: cannot list directory (%s)" % (directory, exc.strerror)
        ) from None
    by_stem: Dict[str, List[SplitFile]] = {}
    for name in names:
        parsed = parse_split_file_name(name)
        path = os.path.join(directory, name)
        if parsed is None or not os.path.isfile(path) or os.path.realpath(path) in excluded:
            continue
        stem, language = parsed
        by_stem.setdefault(stem, []).append(SplitFile(stem, language, path))
    if not by_stem:
        raise XcstoolError(
            ExitCode.NO_SPLIT_FILES,
            "%s: no split files found (expected names like Catalog.LANGUAGE%s)"
            % (directory, EXTENSION),
        )
    if len(by_stem) == 1:
        return next(iter(by_stem.values()))
    if prefer_stem in by_stem:
        return by_stem[prefer_stem]
    raise XcstoolError(
        ExitCode.AMBIGUOUS_SPLIT_FILES,
        "%s: split files of several catalogs found (%s); use a separate directory per catalog"
        % (directory, ", ".join(sorted(by_stem))),
    )


def catalog_stem(path: str) -> str:
    name = os.path.basename(path)
    return name[: -len(EXTENSION)] if name.endswith(EXTENSION) else os.path.splitext(name)[0]


# --- Ordering ---------------------------------------------------------------

# Xcode sorts object keys with a case-insensitive, numeric, Unicode-collation
# comparison. Existing key order is always preserved; this approximation is
# only used to place new language codes and new key-level fields.
_PUNCTUATION_ORDER = "_-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$"


def sort_key(text: str) -> tuple:
    primary = []
    secondary = []
    tertiary = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isdigit() and char.isascii():
            end = index
            while end < len(text) and text[end].isdigit() and text[end].isascii():
                end += 1
            primary.append((3, int(text[index:end]), ""))
            index = end
            continue
        decomposed = unicodedata.normalize("NFD", char)
        base = decomposed[0]
        category = unicodedata.category(base)
        if category.startswith("Z") or char.isspace():
            primary.append((0, ord(char), ""))
        elif base in _PUNCTUATION_ORDER:
            primary.append((1, _PUNCTUATION_ORDER.index(base), ""))
        elif category[0] in "PS":
            primary.append((2, ord(base), ""))
        elif category[0] == "N":
            primary.append((3, ord(base), ""))
        else:
            primary.append((4, 0, base.casefold()))
        secondary.append(decomposed[1:])
        tertiary.append(base.isupper())
        index += 1
    return (primary, secondary, tertiary, text)


def insert_sorted(mapping: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    """Set ``key`` in ``mapping`` and return the resulting mapping (use the return value).

    An existing key is updated in place. A new key goes before the first
    existing key that sorts after it, in a new mapping; existing keys keep
    their order.
    """
    if key in mapping:
        mapping[key] = value
        return mapping
    new_key = sort_key(key)
    result: Dict[str, Any] = {}
    placed = False
    for existing, existing_value in mapping.items():
        if not placed and new_key < sort_key(existing):
            result[key] = value
            placed = True
        result[existing] = existing_value
    if not placed:
        result[key] = value
    return result


def merge_order(existing: List[str], incoming: Iterable[str]) -> List[str]:
    """Combine two key orders, keeping ``existing`` intact.

    Each key of ``incoming`` that is not in ``existing`` is placed right after
    the nearest key that precedes it in ``incoming`` and exists in
    ``existing``; keys with no such predecessor go right before the first
    following one. Keys with no anchor at all go at the end.
    """
    known = set(existing)
    after: Dict[Optional[str], List[str]] = {}
    before: Dict[str, List[str]] = {}
    pending: List[str] = []
    anchor: Optional[str] = None
    seen = set()
    for key in incoming:
        if key in seen:
            continue
        seen.add(key)
        if key in known:
            anchor = key
            if pending:
                before[key] = pending
                pending = []
        elif anchor is None:
            pending.append(key)
        else:
            after.setdefault(anchor, []).append(key)
    result: List[str] = []
    for key in existing:
        result.extend(before.get(key, ()))
        result.append(key)
        result.extend(after.get(key, ()))
    result.extend(pending)
    return result
