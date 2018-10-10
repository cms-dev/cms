#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from unittest.mock import MagicMock, patch

from cms.server.contest.submission import ReceivedFile, \
    InvalidFilesOrLanguage, match_files_and_language


def make_language(name, source_extensions):
    language = MagicMock()
    language.configure_mock(name=name,
                            source_extensions=source_extensions,
                            source_extension=source_extensions[0])
    return language


C_LANG = make_language("C", [".c"])
# Has many extensions.
CPP_LANG = make_language("C++", [".cpp", ".cxx", ".cc"])
# Has an extension that doesn't begin with a period.
PASCAL_LANG = make_language("Pascal", ["lib.pas"])
# Have the same extensions.
PY2_LANG = make_language("Py2", [".py"])
PY3_LANG = make_language("Py3", [".py"])
# Have extensions that create a weird corner case.
LONG_OVERLAP_LANG = make_language("LongOverlap", [".suf.fix"])
SHORT_OVERLAP_LANG = make_language("ShortOverlap", [".fix"])
# The two in one.
SELF_OVERLAP_LANG = make_language("SelfOverlap", [".suf.fix", ".fix"])

FOO_CONTENT = b"this is the content of a file"
BAR_CONTENT = b"this is the content of another file"
BAZ_CONTENT = b"this is the content of a third file"
SPAM_CONTENT = b"this is the content of a fourth file"
HAM_CONTENT = b"this is the content of a fifth file"
EGGS_CONTENT = b"this is the content of a sixth file"


class TestMatchFilesAndLanguages(unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.languages = set()

        patcher = patch(
            "cms.server.contest.submission.file_matching.LANGUAGES",
            self.languages)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch(
            "cms.server.contest.submission.file_matching.get_language",
            self.mock_get_language)
        patcher.start()
        self.addCleanup(patcher.stop)

    def mock_get_language(self, language_name):
        for language in self.languages:
            if language.name == language_name:
                return language
        raise KeyError()

    # Test success scenarios.

    def test_success_language_required(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Both languageful and languageless files with and without
        # codename and filename are matched correctly against a
        # language-specific submission format.
        # Also check that when the codename matches the "extensionless"
        # filename is irrelevant (the extension matters, however).
        files, language = match_files_and_language(
            [ReceivedFile("foo.%l", "my_name.cpp", FOO_CONTENT),
             ReceivedFile("bar.%l", None, BAR_CONTENT),
             ReceivedFile(None, "baz.cc", BAZ_CONTENT),
             ReceivedFile("spam.txt", "my_other_name", SPAM_CONTENT),
             ReceivedFile("eggs.zip", None, HAM_CONTENT),
             ReceivedFile(None, "ham", EGGS_CONTENT)],
            None,
            {"foo.%l", "bar.%l", "baz.%l",
             "spam.txt", "eggs.zip", "ham",
             "superfluous"},
            None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT,
                                 "bar.%l": BAR_CONTENT,
                                 "baz.%l": BAZ_CONTENT,
                                 "spam.txt": SPAM_CONTENT,
                                 "eggs.zip": HAM_CONTENT,
                                 "ham": EGGS_CONTENT})
        self.assertIs(language, CPP_LANG)

    def test_success_language_agnostic(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Languageless files with and without codename and filename are
        # matched correctly against a language-agnostic submission
        # format.
        files, language = match_files_and_language(
            [ReceivedFile("foo.txt", "my_name", FOO_CONTENT),
             ReceivedFile("bar.zip", None, BAR_CONTENT),
             ReceivedFile(None, "baz", BAZ_CONTENT)],
            None,
            {"foo.txt", "bar.zip", "baz",
             "superfluous"},
            None)
        self.assertEqual(files, {"foo.txt": FOO_CONTENT,
                                 "bar.zip": BAR_CONTENT,
                                 "baz": BAZ_CONTENT})
        self.assertIsNone(language)

    # Test support for language-agnostic formats.

    def test_language_agnostic_always_possible(self):
        self.languages.update({C_LANG, CPP_LANG})

        # In language-agnostic settings, passing a (non-None) language
        # is an error.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.txt", None, FOO_CONTENT)],
                "C", {"foo.txt", "bar.zip"}, None)

        # Even if a set of allowed languages is given, None (when
        # applicable) is always allowed.
        files, language = match_files_and_language(
            [ReceivedFile("foo.txt", None, FOO_CONTENT)],
            None, {"foo.txt", "bar.zip"}, ["C++"])
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)

    # Tests for issues matching files.

    def test_bad_file(self):
        self.languages.update({C_LANG})

        # Different codename.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", None, FOO_CONTENT)],
                "C", {"bar.%l"}, None)

        # Incompatible filename.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"bar.%l"}, None)

        # The same in a language-agnostic setting.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.txt", None, FOO_CONTENT)],
                None, {"bar.txt"}, None)

        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.txt", FOO_CONTENT)],
                None, {"bar.txt"}, None)

    def test_bad_extension(self):
        self.languages.update({C_LANG})

        # Even when the codename (and, here, but not necessarily, the
        # extensionless filename) match, the filename's extension needs
        # to be compatible with the language.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.cpp", FOO_CONTENT)],
                "C", {"foo.%l"}, None)

    def test_extension_without_leading_period(self):
        self.languages.update({PASCAL_LANG})

        # Check that the *whole* trailing `.%l` string is replaced with
        # the extension, not just the `%l` part, and also check that the
        # function doesn't split the extension on the filename.
        files, language = match_files_and_language(
            [ReceivedFile(None, "foolib.pas", FOO_CONTENT)],
            None, {"foo.%l"}, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PASCAL_LANG)

        # The same check, in the negative form.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.lib.pas", FOO_CONTENT)],
                None, {"foo.%l"}, None)

        # This must also hold when the filename isn't matched against
        # the submission format (because the codename is used for that)
        # but just its extension is checked.
        files, language = match_files_and_language(
            [ReceivedFile("foo.%l", "foolib.pas", FOO_CONTENT)],
            None, {"foo.%l"}, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PASCAL_LANG)

    def test_duplicate_files(self):
        self.languages.update({C_LANG})

        # If two files match the same codename (even if through
        # different means) then the match is invalid.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "bar.c", FOO_CONTENT),
                 ReceivedFile(None, "foo.c", BAR_CONTENT)],
                None, {"foo.%l"}, None)

    def test_ambiguous_file(self):
        self.languages.update({C_LANG, CPP_LANG})

        # For an admittedly weird submission format, a single file could
        # successfully match multiple elements.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"foo.%l", "foo.c"}, None)

        # This brings in some weird side-effects: for example, in the
        # following, our attempt at matching the files as C fails (since
        # foo.c is ambiguous) whereas matching them as C++ doesn't (as
        # foo.c isn't compatible with foo.%l anymore); thus we guess
        # that the correct language must be C++. If there were other
        # languages allowed it would become ambiguous and fail (as then
        # all languages would be compatible, except C). Remember that
        # these sort of problems arise only when codenames aren't given.
        files, language = match_files_and_language(
            [ReceivedFile(None, "foo.c", FOO_CONTENT)],
            None, {"foo.%l", "foo.c"}, None)
        self.assertEqual(files, {"foo.c": FOO_CONTENT})
        self.assertIs(language, CPP_LANG)

        # And although in theory it could be disambiguated in some cases
        # if one were smart enough, we aren't.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "bar.c", FOO_CONTENT),
                 ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"foo.%l", "foo.c"}, None)

    def test_ambiguous_file_2(self):
        self.languages.update(
            {SELF_OVERLAP_LANG, LONG_OVERLAP_LANG, SHORT_OVERLAP_LANG})

        # For an even weirder language and submission format, a single
        # file could successfully match two language-specific elements
        # of the submission format.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                "SelfOverlap", {"foo.%l", "foo.suf.%l"}, None)

        # Wow, much overlap, very ambiguous.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                None, {"foo.%l", "foo.suf.%l"}, None)

        # I'm doing this just for the fun.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                None, {"foo.%l"}, None)

    # Tests for language issues and ways to solve them.

    def test_forbidden_language(self):
        self.languages.update({C_LANG, CPP_LANG})

        # The (autoguessed) language that would match is forbidden.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, ["C++", "Py2"])

        # The same if the language is given.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, ["C++", "Py2"])

    def test_missing_extensions(self):
        self.languages.update({C_LANG, CPP_LANG})
        given_files = [ReceivedFile("foo.%l", None, FOO_CONTENT)]
        submission_format = {"foo.%l"}

        # The situation is ambiguous: it matches for every language, as
        # there is no extension to clarify and no language is given.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_language(
            given_files, "C", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_language(
            given_files, None, submission_format, ["C++"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, CPP_LANG)

    def test_ambiguous_extensions(self):
        self.languages.update({PY2_LANG, PY3_LANG})
        given_files = [ReceivedFile("foo.%l", "foo.py", FOO_CONTENT)]
        submission_format = {"foo.%l"}

        # The situation is ambiguous: both languages match the
        # extension.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_language(
            given_files, "Py2", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PY2_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_language(
            given_files, None, submission_format, ["Py3"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PY3_LANG)

    def test_overlapping_extensions(self):
        self.languages.update({LONG_OVERLAP_LANG, SHORT_OVERLAP_LANG})
        given_files = [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)]
        submission_format = {"foo.%l", "foo.suf.%l"}

        # The situation is ambiguous: both languages match, although
        # each does so to a different element of the submission format.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_language(
            given_files, "LongOverlap", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, LONG_OVERLAP_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_language(
            given_files, None, submission_format, ["ShortOverlap"])
        self.assertEqual(files, {"foo.suf.%l": FOO_CONTENT})
        self.assertIs(language, SHORT_OVERLAP_LANG)

    # Test some corner cases.

    def test_neither_codename_nor_filename(self):
        self.languages.update({C_LANG})

        # Without neither codename nor filename, there's nothing to base
        # a match on.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, None, FOO_CONTENT)],
                "C", {"foo.%l"}, None)

        # The same holds in a language-agnostic setting.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile(None, None, FOO_CONTENT)],
                None, {"foo.txt"}, None)

    def test_nonexisting_given_languages(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Passing a language that doesn't exist means the contestant
        # doesn't know what they are doing: we're not following through.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "BadLang", {"foo.%l"}, None)

    def test_nonexisting_allowed_languages(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Non-existing languages among the allowed languages are seen as
        # a configuration error: admins should intervene but contestants
        # shouldn't suffer, and thus these items are simply ignored.
        # Both when used to constitute the candidates (as no candidates
        # were given)...
        files, language = match_files_and_language(
            [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
            None, {"foo.%l"}, ["C", "BadLang"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

        # And when they act as filter for the given candidates.
        files, language = match_files_and_language(
            [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
            "C", {"foo.%l"}, ["C", "BadLang"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

    def test_given_files_empty(self):
        self.languages.update({C_LANG, CPP_LANG})

        # No files vacuously match every submission format for every
        # language, hence this is ambiguous.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                list(), None, {"foo.%l"}, None)

        # For just a single fixed language it could be considered valid,
        # however in the best case it would be rejected later because
        # some (all) files are missing and in the worst case the files
        # from the previous submission would be fetched: no reasonable
        # user could have meant this on purpose, we reject.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                list(), "C", {"foo.%l"}, None)

        # The same holds for a language-agnostic submission format:
        # moreover, in that case there wouldn't be any ambiguity from
        # the start as only one "language" is allowed (i.e., None).
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                list(), None, {"foo.txt"}, None)

    def test_submission_format_empty(self):
        self.languages.update({C_LANG, CPP_LANG})

        # If no files are wanted, any file will cause an invalid match.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", set(), None)

        # Even in language-agnostic settings.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
                None, set(), None)

        # If there are no files this could be made to work. However we
        # decided that this means that the whole thing is very messed up
        # and thus abort instead.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                list(), None, set(), None)

    def test_allowed_languages_empty(self):
        self.languages.update({C_LANG})

        # An empty list of allowed languages means no language allowed:
        # any attempt at matching must necessarily fail.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, list())

        # If all allowed languages are invalid, it's as if there weren't
        # any.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, ["BadLang"])

        # The same holds if no candidates are given (this difference is
        # relevant because now the allowed ones are used as candidates,
        # instead of acting only as a filter).
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, list())

        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_language(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, ["BadLang"])

        # However the "None" language, if applicable (i.e., if the
        # submission format is language-agnostic), is always allowed.
        files, language = match_files_and_language(
            [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
            None, {"foo.txt"}, list())
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)

        files, language = match_files_and_language(
            [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
            None, {"foo.txt"}, ["BadLang"])
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)


if __name__ == "__main__":
    unittest.main()
