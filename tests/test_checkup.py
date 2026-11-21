import os
import re
import unittest

from helpers import TempDirTestCase, plural, sample_catalog, unit
from xcstool.checkup import has_incomplete_variations
from xcstool.errors import ExitCode
from xcstool.plurals import required_categories


def row(output, language):
    """The numbers of a language's row in the checkup table."""
    for line in output.splitlines():
        if line.startswith(language + " ") or line == language:
            return [cell for cell in re.split(r"\s{2,}", line.strip())[1:]]
    raise AssertionError("no row for %s in:\n%s" % (language, output))


class CheckupTests(TempDirTestCase):
    def test_counts_per_language(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        code, out, _ = self.run_cli("checkup", path)
        self.assertEqual(code, 0)
        # Missing, New/review, Variations, Stale.
        self.assertEqual(row(out, "es"), ["1", "0", "0", "1"])
        # ru: Delete and Untranslated missing; Cancel needs review; plural lacks few/many.
        self.assertEqual(row(out, "ru"), ["2", "1", "1", "1"])
        self.assertEqual(row(out, "en (source)*"), ["-", "-", "0", "1"])
        self.assertEqual(row(out, "Total"), ["3", "1", "1", "2"])
        self.assertIn("Localization work remains: 5 items in 2 languages.", out)
        self.assertIn("1 stale key", out)
        self.assertIn("(1 with shouldTranslate: false, ignored)", out)

    def test_strict_exit_code(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        self.assertEqual(self.run_cli("checkup", "--strict", path)[0], ExitCode.WORK_REMAINING)
        done = self.copy_fixture("plural.xcstrings")
        code, out, _ = self.run_cli("checkup", "--strict", done)
        self.assertEqual(code, 0)
        self.assertIn("No localization work left.", out)

    def test_stale_keys_do_not_count_as_work(self):
        data = {
            "sourceLanguage": "en",
            "strings": {"Old": {"extractionState": "stale"}},
            "version": "1.0",
        }
        path = self.write_catalog("C.xcstrings", data)
        code, out, _ = self.run_cli("checkup", "--strict", path)
        self.assertEqual(code, 0)
        self.assertIn("1 stale key", out)

    def test_source_language_is_translated(self):
        data = sample_catalog()
        data["strings"]["Delete"]["localizations"]["en"] = unit("Delete", "new")
        path = self.write_catalog("Localizable.xcstrings", data)
        _, out, _ = self.run_cli("checkup", "-s", path)
        # Missing: Cancel, Untranslated. New: Delete.
        self.assertEqual(row(out, "en (source)"), ["2", "1", "0", "1"])
        self.assertNotIn("baseline", out)
        _, out, _ = self.run_cli("checkup", "--source-lang-is-translated", path)
        self.assertEqual(row(out, "Total"), ["5", "2", "1", "3"])

    def test_verbose_lists_keys(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        _, out, _ = self.run_cli("checkup", "--verbose", path)
        ru = out[out.index("\nru:\n") :]
        self.assertIn('missing (2):\n    "Delete"\n    "Untranslated"', ru)
        self.assertIn('new or needs_review (1):\n    "Cancel"', ru)
        self.assertIn('incomplete variations (1):\n    "%lld files"', ru)
        self.assertIn('stale (1):\n    "Old"', ru)

    def test_directory_of_split_files(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        self.run_cli("split", source, self.path("out"))
        _, from_file, _ = self.run_cli("checkup", source)
        code, from_dir, err = self.run_cli("checkup", self.path("out"))
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

        def table(text):
            return text[text.index("Language") :]

        self.assertEqual(table(from_dir), table(from_file))

    def test_directory_inconsistencies_are_warnings(self):
        data = sample_catalog()
        self.write_catalog(os.path.join("out", "L.en.xcstrings"), data)
        del data["strings"]["Delete"]
        data["sourceLanguage"] = "es"
        self.write_catalog(os.path.join("out", "L.es.xcstrings"), data)
        code, _, err = self.run_cli("checkup", self.path("out"))
        self.assertEqual(code, 0)
        self.assertIn("warning: the split files disagree on sourceLanguage", err)
        self.assertIn("warning: L.es.xcstrings lacks 1 key present in other split files", err)

    def test_checkup_never_writes(self):
        path = self.write_catalog("Localizable.xcstrings", sample_catalog())
        before = self.read_bytes(path)
        self.run_cli("checkup", "-v", "--strict", path)
        self.assertEqual(self.read_bytes(path), before)
        self.assertEqual(os.listdir(self.tmp), ["Localizable.xcstrings"])


class VariationTests(unittest.TestCase):
    def test_plural_categories(self):
        ru = required_categories("ru")
        self.assertFalse(
            has_incomplete_variations(plural(one="", few="", many="", other=""), None, ru)
        )
        self.assertTrue(has_incomplete_variations(plural(one="", other=""), None, ru))
        self.assertFalse(
            has_incomplete_variations(plural(other=""), None, required_categories("ja"))
        )
        # Extra categories (zero) are fine.
        self.assertFalse(
            has_incomplete_variations(
                plural(zero="", one="", other=""), None, required_categories("de")
            )
        )

    def test_plain_string_is_not_an_incomplete_plural(self):
        self.assertFalse(
            has_incomplete_variations(
                unit("x"), plural(one="", other=""), required_categories("ru")
            )
        )

    def test_device_variations(self):
        source = {
            "variations": {
                "device": {"iphone": unit("Tap"), "mac": unit("Click"), "other": unit("Tap")}
            }
        }
        complete = {
            "variations": {"device": {"iphone": unit("a"), "mac": unit("b"), "other": unit("c")}}
        }
        partial = {"variations": {"device": {"iphone": unit("a"), "other": unit("c")}}}
        other = required_categories("de")
        self.assertFalse(has_incomplete_variations(complete, source, other))
        self.assertTrue(has_incomplete_variations(partial, source, other))
        self.assertTrue(has_incomplete_variations(unit("a"), source, other))

    def test_plural_nested_in_device(self):
        node = {"variations": {"device": {"other": plural(one="", other="")}}}
        self.assertTrue(has_incomplete_variations(node, None, required_categories("pl")))
        self.assertFalse(has_incomplete_variations(node, None, required_categories("en")))

    def test_substitutions(self):
        def with_substitution(variations):
            return {
                "stringUnit": {"state": "translated", "value": "%#@files@"},
                "substitutions": {"files": dict(argNum=1, formatSpecifier="lld", **variations)},
            }

        ru = required_categories("ru")
        self.assertTrue(
            has_incomplete_variations(with_substitution(plural(one="", other="")), None, ru)
        )
        self.assertFalse(
            has_incomplete_variations(
                with_substitution(plural(one="", few="", many="", other="")), None, ru
            )
        )
        source = with_substitution({"variations": {"device": {"mac": unit(""), "other": unit("")}}})
        target = with_substitution({"variations": {"device": {"other": unit("")}}})
        self.assertTrue(has_incomplete_variations(target, source, required_categories("de")))

    def test_required_categories_lookup(self):
        self.assertEqual(required_categories("ru"), {"one", "few", "many", "other"})
        self.assertEqual(required_categories("pt-BR"), {"one", "many", "other"})
        self.assertEqual(required_categories("zh-Hant"), {"other"})
        self.assertEqual(required_categories("sr-Latn"), {"one", "few", "other"})
        self.assertEqual(required_categories("ar"), {"zero", "one", "two", "few", "many", "other"})
        self.assertEqual(required_categories("xx"), {"other"})


if __name__ == "__main__":
    unittest.main()
