"""Command-line interface."""

import argparse
import os
import sys
from typing import List, Optional

from xcstool import __version__
from xcstool.errors import XcstoolError

DESCRIPTION = (
    "Split Xcode String Catalogs (.xcstrings) into one file per language, merge them back, "
    "check the localization work left and remove stale keys."
)


def _add_common(parser: argparse.ArgumentParser, dry_run: bool) -> None:
    if dry_run:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="report what would change without writing anything",
        )
    parser.add_argument("-v", "--verbose", action="store_true", help="print more details")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xcstool", description=DESCRIPTION)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    split = commands.add_parser(
        "split",
        help="split a catalog into one file per language",
        description="Write CATALOG.LANG.xcstrings files to OUTPUT_DIR, one per language of the catalog "
        "(source language included). Existing files are overwritten.",
    )
    split.add_argument("input", metavar="INPUT_FILE", help="the .xcstrings file to split")
    split.add_argument(
        "output_dir", metavar="OUTPUT_DIR", help="directory for the split files (created if needed)"
    )
    _add_common(split, dry_run=True)

    merge = commands.add_parser(
        "merge",
        help="update a catalog with the translations of split files",
        description="Update OUTPUT_FILE with the translations of the split files in INPUT_DIR. Each split "
        "file contributes only the language in its name; nothing is ever deleted. OUTPUT_FILE is "
        "created if it does not exist.",
    )
    merge.add_argument("input_dir", metavar="INPUT_DIR", help="directory with the split files")
    merge.add_argument("output", metavar="OUTPUT_FILE", help="the .xcstrings file to update")
    _add_common(merge, dry_run=True)

    checkup = commands.add_parser(
        "checkup",
        help="report the localization work left (read-only)",
        description="Report, per language, the keys with missing translations, new or needs_review "
        "states, incomplete plural or device variations, and stale keys. Never writes anything.",
    )
    checkup.add_argument(
        "path", metavar="PATH", help="a .xcstrings file or a directory of split files"
    )
    checkup.add_argument(
        "-s",
        "--source-lang-is-translated",
        action="store_true",
        help="count the source language like any other language",
    )
    checkup.add_argument("--strict", action="store_true", help="exit with 1 if any work remains")
    _add_common(checkup, dry_run=False)

    rmstale = commands.add_parser(
        "rmstale",
        help='remove keys whose extractionState is "stale"',
        description='Remove, in place, every key whose extractionState is "stale", with all its '
        "localizations. Nothing else in the file changes.",
    )
    rmstale.add_argument("path", metavar="FILE", help="the .xcstrings file to clean up")
    _add_common(rmstale, dry_run=True)
    rmstale.set_defaults(subparser=rmstale)
    return parser


def run(args: argparse.Namespace) -> int:
    out = sys.stdout
    if args.command == "split":
        from xcstool.split import run_split

        return run_split(args.input, args.output_dir, args.dry_run, args.verbose, out)
    if args.command == "merge":
        from xcstool.merge import run_merge

        return run_merge(args.input_dir, args.output, args.dry_run, args.verbose, out)
    if args.command == "checkup":
        from xcstool.checkup import run_checkup

        return run_checkup(
            args.path, args.source_lang_is_translated, args.strict, args.verbose, out, sys.stderr
        )
    if args.command == "rmstale":
        from xcstool.rmstale import run_rmstale

        if os.path.isdir(args.path):
            args.subparser.error("%s is a directory; a .xcstrings file is expected" % args.path)
        return run_rmstale(args.path, args.dry_run, args.verbose, out)
    raise AssertionError(args.command)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(run(args))
    except XcstoolError as exc:
        sys.stderr.write("xcstool: error: %s\n" % exc.message)
        return int(exc.code)
    except KeyboardInterrupt:
        sys.stderr.write("xcstool: interrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
