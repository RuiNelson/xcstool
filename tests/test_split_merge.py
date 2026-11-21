import os
import unittest

from helpers import TempDirTestCase, sample_catalog, unit
from xcstool import jsonfmt
from xcstool.catalog import merge_order, sort_key
from xcstool.errors import ExitCode


class SplitTests(TempDirTestCase):
    def test_split_writes_one_file_per_language(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        code, out, _ = self.run_cli("split", source, self.path("out", "nested"))
        self.assertEqual(code, 0)
        self.assertEqual(
            sorted(os.listdir(self.path("out", "nested"))),
            ["Localizable.en.xcstrings", "Localizable.es.xcstrings", "Localizable.ru.xcstrings"],
        )
        self.assertIn("languages: en, es, ru", out)

    def test_split_file_content(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        self.run_cli("split", source, self.path("out"))
        es = self.read_json(self.path("out", "Localizable.es.xcstrings"))
        self.assertEqual(es["version"], "1.0")
        self.assertEqual(es["sourceLanguage"], "en")
        self.assertEqual(list(es["strings"]), list(sample_catalog()["strings"]))
        files = es["strings"]["%lld files"]
        self.assertEqual(files["comment"], "File count")
        self.assertEqual(list(files["localizations"]), ["en", "es"])
        self.assertEqual(es["strings"]["Cancel"]["localizations"], {"es": unit("Cancelar")})
        self.assertEqual(es["strings"]["Old"]["extractionState"], "stale")
        en = self.read_json(self.path("out", "Localizable.en.xcstrings"))
        # No empty "localizations" object when nothing is left.
        self.assertEqual(en["strings"]["Cancel"], {})
        self.assertEqual(en["strings"][""], {"shouldTranslate": False})

    def test_split_overwrites_existing_files(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        os.makedirs(self.path("out"))
        with open(self.path("out", "Localizable.es.xcstrings"), "w") as handle:
            handle.write("garbage")
        self.assertEqual(self.run_cli("split", source, self.path("out"))[0], 0)
        self.read_json(self.path("out", "Localizable.es.xcstrings"))

    def test_split_dry_run_writes_nothing(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        code, out, _ = self.run_cli("split", "--dry-run", source, self.path("out"))
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.path("out")))
        self.assertIn("Would write", out)
        self.assertIn("Localizable.ru.xcstrings", out)

    def test_split_output_is_a_file(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        code, _, err = self.run_cli("split", source, source)
        self.assertEqual(code, ExitCode.NOT_A_DIRECTORY)
        self.assertIn("not a directory", err)


class RoundTripTests(TempDirTestCase):
    def test_split_then_merge_is_byte_identical(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        before = self.read_bytes(source)
        self.run_cli("split", source, self.path("out"))
        code, out, _ = self.run_cli("merge", self.path("out"), source)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_bytes(source), before)
        self.assertIn("0 keys added, 0 localizations added, 0 changed", out)

    def test_merge_into_new_file_rebuilds_the_catalog(self):
        source = self.write_catalog("Localizable.xcstrings", sample_catalog())
        self.run_cli("split", source, self.path("out"))
        code, out, _ = self.run_cli("merge", self.path("out"), self.path("New.xcstrings"))
        self.assertEqual(code, 0)
        self.assertIn("(new file)", out)
        self.assertEqual(self.read_bytes(self.path("New.xcstrings")), self.read_bytes(source))

    def test_fixture_round_trip(self):
        source = self.copy_fixture("plural.xcstrings")
        self.run_cli("split", source, self.path("out"))
        self.assertEqual(
            sorted(os.listdir(self.path("out"))), ["plural.de.xcstrings", "plural.en.xcstrings"]
        )
        formatted = jsonfmt.dumps(self.read_json(source))
        self.run_cli("merge", self.path("out"), source)
        # The fixture is not in Xcode's format; merge rewrites it in Xcode's format
        # without changing any content or order.
        with open(source, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), formatted)


class MergeTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.catalog = self.write_catalog("Localizable.xcstrings", sample_catalog())
        self.run_cli("split", self.catalog, self.path("out"))

    def split(self, language):
        return self.path("out", "Localizable.%s.xcstrings" % language)

    def edit(self, language, change):
        with open(self.split(language), encoding="utf-8") as handle:
            data = jsonfmt.loads(handle.read())
        change(data)
        self.write_catalog(os.path.join("out", "Localizable.%s.xcstrings" % language), data)

    def merged(self):
        return self.read_json(self.catalog)["strings"]

    def test_only_the_file_language_is_contributed(self):
        def change(data):
            data["strings"]["%lld files"]["localizations"]["en"] = unit("STALE CONTEXT")
            data["strings"]["Delete"]["localizations"]["ru"] = unit("Удалить")
            data["strings"]["Delete"]["localizations"]["es"] = unit("Borrar")

        self.edit("es", change)
        code, out, _ = self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(code, 0)
        strings = self.merged()
        self.assertEqual(
            strings["%lld files"]["localizations"]["en"],
            sample_catalog()["strings"]["%lld files"]["localizations"]["en"],
        )
        self.assertNotIn("ru", strings["Delete"]["localizations"])
        self.assertEqual(strings["Delete"]["localizations"]["es"], unit("Borrar"))
        self.assertIn("1 changed", out)

    def test_source_language_changes_through_its_own_file(self):
        self.edit(
            "en",
            lambda d: (
                d["strings"]["Delete"].setdefault("localizations", {}).update(en=unit("Remove"))
            ),
        )
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(list(self.merged()["Delete"]["localizations"]), ["en", "es"])
        self.assertEqual(self.merged()["Delete"]["localizations"]["en"], unit("Remove"))

    def test_new_localization_is_added_in_sorted_position(self):
        self.edit(
            "ru",
            lambda d: (
                d["strings"]["Delete"].setdefault("localizations", {}).update(ru=unit("Удалить"))
            ),
        )
        self.edit(
            "en",
            lambda d: (
                d["strings"]["Delete"].setdefault("localizations", {}).update(en=unit("Delete"))
            ),
        )
        code, out, _ = self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(list(self.merged()["Delete"]["localizations"]), ["en", "es", "ru"])
        self.assertIn("2 localizations added", out)

    def test_localizations_field_is_created_in_order(self):
        self.edit(
            "es",
            lambda d: d["strings"]["Untranslated"].update(
                localizations={"es": unit("Sin traducir")}
            ),
        )
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(
            self.merged()["Untranslated"], {"localizations": {"es": unit("Sin traducir")}}
        )

    def test_missing_keys_and_languages_are_left_untouched(self):
        os.remove(self.split("ru"))

        def change(data):
            del data["strings"]["Cancel"]
            del data["strings"]["Delete"]["localizations"]["es"]

        self.edit("es", change)
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(self.merged(), sample_catalog()["strings"])

    def test_key_level_fields_of_existing_keys_never_change(self):
        def change(data):
            data["strings"]["Delete"]["comment"] = "Changed by translator"
            data["strings"]["Delete"]["shouldTranslate"] = False
            del data["strings"]["%lld files"]["comment"]

        self.edit("es", change)
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(self.merged()["Delete"]["comment"], "Delete button")
        self.assertNotIn("shouldTranslate", self.merged()["Delete"])
        self.assertEqual(self.merged()["%lld files"]["comment"], "File count")

    def test_new_key_takes_fields_from_source_language_file(self):
        self.edit(
            "es",
            lambda d: d["strings"].update(
                Added={"comment": "from es", "localizations": {"es": unit("Añadido")}}
            ),
        )
        self.edit("en", lambda d: d["strings"].update(Added={"comment": "from en"}))
        self.edit(
            "ru",
            lambda d: d["strings"].update(
                Added={"comment": "from ru", "localizations": {"ru": unit("Добавлено")}}
            ),
        )
        code, out, _ = self.run_cli("merge", self.path("out"), self.catalog)
        added = self.merged()["Added"]
        self.assertEqual(added["comment"], "from en")
        self.assertEqual(added["localizations"], {"es": unit("Añadido"), "ru": unit("Добавлено")})
        self.assertIn("1 keys added", out)

    def test_new_key_takes_fields_from_first_file_without_source_file(self):
        os.remove(self.split("en"))
        self.edit(
            "ru",
            lambda d: d["strings"].update(
                Added={"comment": "from ru", "localizations": {"ru": unit("Добавлено")}}
            ),
        )
        self.edit("es", lambda d: d["strings"].update(Added={"comment": "from es"}))
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(
            self.merged()["Added"],
            {"comment": "from es", "localizations": {"ru": unit("Добавлено")}},
        )

    def test_new_keys_follow_split_file_order(self):
        self.run_cli("rmstale", self.catalog)
        self.assertNotIn("Old", self.merged())
        self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(list(self.merged()), list(sample_catalog()["strings"]))

    def test_merge_dry_run_writes_nothing(self):
        before = self.read_bytes(self.catalog)
        self.edit("es", lambda d: d["strings"]["Delete"]["localizations"].update(es=unit("Borrar")))
        code, out, _ = self.run_cli("merge", "--dry-run", self.path("out"), self.catalog)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_bytes(self.catalog), before)
        self.assertIn('~ [es] "Delete"', out)
        self.assertIn("Would merge", out)

    def test_catalog_inside_the_split_directory_is_ignored(self):
        catalog = self.write_catalog(os.path.join("out", "Localizable.xcstrings"), sample_catalog())
        code, out, _ = self.run_cli("merge", self.path("out"), catalog)
        self.assertEqual(code, 0)
        self.assertIn("3 split files", out)

    def test_several_catalogs_in_one_directory(self):
        other = self.write_catalog("InfoPlist.xcstrings", sample_catalog())
        self.run_cli("split", other, self.path("out"))
        code, out, _ = self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(code, 0, out)
        code, _, err = self.run_cli("merge", self.path("out"), self.path("Other.xcstrings"))
        self.assertEqual(code, ExitCode.AMBIGUOUS_SPLIT_FILES)
        self.assertIn("InfoPlist, Localizable", err)

    def test_source_language_mismatch(self):
        data = sample_catalog()
        data["sourceLanguage"] = "fr"
        target = self.write_catalog("French.xcstrings", data)
        code, _, err = self.run_cli("merge", self.path("out"), target)
        self.assertEqual(code, ExitCode.SOURCE_LANGUAGE_MISMATCH)
        self.assertIn("sourceLanguage", err)

    def test_split_files_disagree_on_source_language(self):
        self.edit("ru", lambda d: d.update(sourceLanguage="de"))
        code, _, err = self.run_cli("merge", self.path("out"), self.catalog)
        self.assertEqual(code, ExitCode.SOURCE_LANGUAGE_MISMATCH)

    def test_no_split_files(self):
        os.makedirs(self.path("empty"))
        code, _, err = self.run_cli("merge", self.path("empty"), self.catalog)
        self.assertEqual(code, ExitCode.NO_SPLIT_FILES)

    def test_input_is_not_a_directory(self):
        code, _, _ = self.run_cli("merge", self.catalog, self.path("x.xcstrings"))
        self.assertEqual(code, ExitCode.NOT_A_DIRECTORY)
        code, _, _ = self.run_cli("merge", self.path("missing"), self.path("x.xcstrings"))
        self.assertEqual(code, ExitCode.PATH_NOT_FOUND)


class OrderingTests(unittest.TestCase):
    def test_language_codes_sort_like_xcode(self):
        codes = ["zh-HK", "pt-PT", "zh-Hant", "en", "pt", "zh-Hans", "pt-BR", "ar"]
        self.assertEqual(
            sorted(codes, key=sort_key),
            ["ar", "en", "pt", "pt-BR", "pt-PT", "zh-Hans", "zh-Hant", "zh-HK"],
        )

    def test_field_names_sort_like_xcode(self):
        fields = [
            "shouldTranslate",
            "localizations",
            "isCommentAutoGenerated",
            "extractionState",
            "comment",
        ]
        self.assertEqual(
            sorted(fields, key=sort_key),
            [
                "comment",
                "extractionState",
                "isCommentAutoGenerated",
                "localizations",
                "shouldTranslate",
            ],
        )

    def test_merge_order(self):
        self.assertEqual(
            merge_order(["a", "c", "e"], ["b", "c", "d", "f"]), ["a", "b", "c", "d", "f", "e"]
        )
        self.assertEqual(merge_order([], ["x", "y"]), ["x", "y"])
        self.assertEqual(merge_order(["a"], ["z"]), ["a", "z"])


if __name__ == "__main__":
    unittest.main()
