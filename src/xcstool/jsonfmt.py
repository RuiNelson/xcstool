"""Reading and writing JSON exactly the way Xcode formats String Catalogs.

Xcode writes ``.xcstrings`` files with a 2-space indent, ``"key" : value``
spacing, non-ASCII characters left unescaped, forward slashes left unescaped,
empty objects as ``{`` + blank line + ``}`` and no trailing newline. Key order
is kept as read so that untouched parts of a file never move.
"""

import json
import re
from typing import Any

_INDENT = "  "
_SURROGATE = re.compile("[\ud800-\udfff]")


class RawNumber(str):
    """A JSON number kept as its original text, so it is written back unchanged."""


def loads(text: str) -> Any:
    """Parse JSON text, keeping object key order and the original number text."""
    return json.loads(text, parse_int=RawNumber, parse_float=RawNumber, parse_constant=RawNumber)


def dumps(value: Any) -> str:
    """Serialize a value with Xcode's String Catalog formatting."""
    parts = []
    _write(value, 0, parts)
    return "".join(parts)


def _string(value: str) -> str:
    text = json.dumps(value, ensure_ascii=False)
    # Lone surrogates cannot be encoded as UTF-8; keep them as escapes.
    return _SURROGATE.sub(lambda m: "\\u%04x" % ord(m.group()), text)


def _write(value: Any, level: int, parts: list) -> None:
    if isinstance(value, RawNumber):
        parts.append(str(value))
    elif isinstance(value, str):
        parts.append(_string(value))
    elif value is True:
        parts.append("true")
    elif value is False:
        parts.append("false")
    elif value is None:
        parts.append("null")
    elif isinstance(value, (int, float)):
        parts.append(json.dumps(value))
    elif isinstance(value, dict):
        _write_container(
            "{",
            "}",
            list(value.items()),
            level,
            parts,
            lambda item: _write_member(item, level + 1, parts),
        )
    elif isinstance(value, (list, tuple)):
        _write_container(
            "[", "]", list(value), level, parts, lambda item: _write(item, level + 1, parts)
        )
    else:
        raise TypeError("cannot serialize %r" % type(value).__name__)


def _write_member(item: tuple, level: int, parts: list) -> None:
    key, member = item
    parts.append(_string(str(key)))
    parts.append(" : ")
    _write(member, level, parts)


def _write_container(
    open_: str, close: str, items: list, level: int, parts: list, write_item
) -> None:
    inner = _INDENT * (level + 1)
    parts.append(open_)
    parts.append("\n")
    if not items:
        parts.append("\n")
    for index, item in enumerate(items):
        parts.append(inner)
        write_item(item)
        if index < len(items) - 1:
            parts.append(",")
        parts.append("\n")
    parts.append(_INDENT * level)
    parts.append(close)
