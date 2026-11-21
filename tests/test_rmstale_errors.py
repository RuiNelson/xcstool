import os
import subprocess
import sys
import unittest

from helpers import TempDirTestCase, sample_catalog
from xcstool.errors import ExitCode

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


class RmstaleTests(TempDirTestCase):
    def test_removes_only_stale_keys(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        code, out, _ = self.run_cli("rmstale", "--verbose", path)
        self.assertEqual(code, 0)
        expected = sample_catalog()
        del expected["strings"]["Old"]
        self.assertEqual(self.read_json(path), expected)
        self.assertIn('- "Old"', out)
        self.assertIn("Removed 1 stale key from", out)

    def test_nothing_else_changes(self):
        data = sample_catalog()
        del data["strings"]["Old"]
        path = self.write_catalog("Localizable.xcstrings", data)
        before = self.read_bytes(path)
        code, out, _ = self.run_cli("rmstale", path)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_bytes(path), before)
        self.assertIn("Removed 0 stale keys", out)

    def test_dry_run(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        before = self.read_bytes(path)
        code, out, _ = self.run_cli("rmstale", "--dry-run", path)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_bytes(path), before)
        self.assertIn('- "Old"', out)
        self.assertIn("Would remove 1 stale key", out)

    def test_directory_is_a_usage_error(self):
        code, _, err = self.run_cli("rmstale", self.tmp)
        self.assertEqual(code, ExitCode.USAGE)
        self.assertIn("a .xcstrings file is expected", err)


class ErrorTests(TempDirTestCase):
    def write_text(self, name, text):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_exit_codes_are_unique(self):
        values = [member.value for member in ExitCode]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual((ExitCode.SUCCESS, ExitCode.WORK_REMAINING, ExitCode.USAGE), (0, 1, 2))
        self.assertTrue(
            all(
                member >= 3
                for member in ExitCode
                if member.name not in ("SUCCESS", "WORK_REMAINING", "USAGE")
            )
        )

    def test_missing_file(self):
        for command in ("checkup", "rmstale"):
            code, _, err = self.run_cli(command, self.path("missing.xcstrings"))
            self.assertEqual(code, ExitCode.PATH_NOT_FOUND)
            self.assertIn("xcstool: error:", err)
        code, _, _ = self.run_cli("split", self.path("missing.xcstrings"), self.path("out"))
        self.assertEqual(code, ExitCode.PATH_NOT_FOUND)

    def test_invalid_json(self):
        path = self.write_text("bad.xcstrings", "{ not json")
        code, _, err = self.run_cli("checkup", path)
        self.assertEqual(code, ExitCode.INVALID_JSON)
        self.assertIn("invalid JSON", err)

    def test_invalid_catalog(self):
        for text in (
            "[]",
            '{"version" : "1.0", "sourceLanguage" : "en"}',
            '{"strings" : {}, "sourceLanguage" : "en"}',
        ):
            path = self.write_text("bad.xcstrings", text)
            code, _, err = self.run_cli("rmstale", path)
            self.assertEqual(code, ExitCode.INVALID_CATALOG, text)
            self.assertIn("not a valid string catalog", err)

    def test_unsupported_version(self):
        path = self.write_text(
            "v2.xcstrings", '{"sourceLanguage" : "en", "strings" : {}, "version" : "2.0"}'
        )
        code, _, err = self.run_cli("split", path, self.path("out"))
        self.assertEqual(code, ExitCode.UNSUPPORTED_VERSION)
        self.assertIn("unsupported string catalog version", err)

    def test_usage_error(self):
        self.assertEqual(self.run_cli()[0], ExitCode.USAGE)
        self.assertEqual(self.run_cli("split", "only-one-arg")[0], ExitCode.USAGE)

    def test_runs_as_module(self):
        env = dict(os.environ, PYTHONPATH=SRC)
        result = subprocess.run(
            [sys.executable, "-m", "xcstool", "--help"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        for command in ("split", "merge", "checkup", "rmstale"):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
