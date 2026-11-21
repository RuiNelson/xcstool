"""Error kinds and their process exit codes."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes. Every error kind has its own member and code.

    ``0`` is success, ``1`` is reserved for ``checkup --strict`` when work
    remains, ``2`` is a command-line usage error (argparse's default) and the
    other errors start at ``3``.
    """

    SUCCESS = 0
    WORK_REMAINING = 1
    USAGE = 2
    PATH_NOT_FOUND = 3
    READ_ERROR = 4
    WRITE_ERROR = 5
    INVALID_JSON = 6
    INVALID_CATALOG = 7
    UNSUPPORTED_VERSION = 8
    NOT_A_DIRECTORY = 9
    NO_SPLIT_FILES = 10
    AMBIGUOUS_SPLIT_FILES = 11
    SOURCE_LANGUAGE_MISMATCH = 12


class XcstoolError(Exception):
    """An error reported to the user with a message and a specific exit code."""

    def __init__(self, code: ExitCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
