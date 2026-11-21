"""The ``rmstale`` subcommand: remove keys whose extractionState is "stale"."""

import json
from typing import List, TextIO

from xcstool.catalog import Catalog, is_stale, read_catalog, write_catalog
from xcstool.errors import ExitCode


def remove_stale(data: Catalog) -> List[str]:
    """Remove stale keys (with all their localizations) in place; return the removed keys."""
    removed = [key for key, entry in data["strings"].items() if is_stale(entry)]
    if removed:
        data["strings"] = {
            key: entry for key, entry in data["strings"].items() if not is_stale(entry)
        }
    return removed


def run_rmstale(path: str, dry_run: bool, verbose: bool, out: TextIO) -> int:
    data = read_catalog(path)
    removed = remove_stale(data)
    if verbose or dry_run:
        for key in removed:
            out.write("  - %s\n" % json.dumps(key, ensure_ascii=False))
    if removed and not dry_run:
        write_catalog(path, data)
    verb = "Would remove" if dry_run else "Removed"
    out.write(
        "%s %d stale key%s from %s\n" % (verb, len(removed), "" if len(removed) == 1 else "s", path)
    )
    return ExitCode.SUCCESS
