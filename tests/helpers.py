import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from xcstool import jsonfmt
from xcstool.cli import main

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def unit(value, state="translated"):
    return {"stringUnit": {"state": state, "value": value}}


def plural(state="translated", **forms):
    return {"variations": {"plural": {name: unit(text, state) for name, text in forms.items()}}}


def sample_catalog():
    """A catalog in Xcode's key order with the usual kinds of entries."""
    return {
        "sourceLanguage": "en",
        "strings": {
            "": {"shouldTranslate": False},
            "%lld files": {
                "comment": "File count",
                "localizations": {
                    "en": plural(one="%lld file", other="%lld files"),
                    "es": plural(one="%lld archivo", many="%lld archivos", other="%lld archivos"),
                    "ru": plural(one="%lld файл", other="%lld файлов"),
                },
            },
            "Cancel": {
                "localizations": {
                    "es": unit("Cancelar"),
                    "ru": unit("Отмена", "needs_review"),
                }
            },
            "Delete": {
                "comment": "Delete button",
                "localizations": {"es": unit("Eliminar")},
            },
            "Old": {
                "extractionState": "stale",
                "localizations": {"es": unit("Viejo"), "ru": unit("Старый")},
            },
            "Untranslated": {},
        },
        "version": "1.0",
    }


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="xcstool-test-")
        self.addCleanup(shutil.rmtree, self.tmp)

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write_catalog(self, name, data):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(jsonfmt.dumps(data))
        return path

    def copy_fixture(self, name, dest=None):
        path = self.path(dest or name)
        shutil.copy(os.path.join(FIXTURES, name), path)
        return path

    def read_json(self, path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def run_cli(self, *argv):
        """Run the CLI; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()
