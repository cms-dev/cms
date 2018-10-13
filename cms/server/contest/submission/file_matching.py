#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Functions to match files with partial information to a given format.

Provide functions that take a set of files in CWS's own format, in all
generality (there could be duplicate of missing files, omitted fields,
etc.) and try to match them against the desired format for a submission.

"""

import os.path

from cms.grading.languagemanager import get_language, LANGUAGES


class InvalidFiles(Exception):
    """Raised when the submitted files can't be matched to the format."""

    pass


def _match_filename(filename, language, element):
    """Ensure the filename is entirely compatible with the element.

    Return whether the filename matches the element, including having an
    appropriate value for the language-specific extension (if present)
    for the given language.

    filename (str): the filename.
    language (Language|None): the language.
    element (str): the element of the submission format.

    return (bool): whether there's a match.

    """
    if not element.endswith(".%l"):
        return filename == element
    if language is None:
        raise ValueError("language not given but submission format requires it")
    base = os.path.splitext(element)[0]
    return any(filename == base + ext for ext in language.source_extensions)


def _match_extension(filename, language, element):
    """Ensure filename is compatible with element w.r.t. the extension.

    Return whether the filename (if given) matches the language-specific
    extension of the element (if present) for the given language.

    filename (str|None): the filename.
    language (Language|None): the language.
    element (str): the element of the submission format.

    return (bool): whether there's a match.

    """
    if filename is None or not element.endswith(".%l"):
        return True
    if language is None:
        raise ValueError("language not given but submission format requires it")
    return any(filename.endswith(ext) for ext in language.source_extensions)


def _match_file(codename, filename, language, submission_format):
    """Figure out what element of the submission format a file is for.

    Return our best guess for which element of the submission format
    the submitted file was meant for. A match occurs when:
    - the codename isn't given and the filename matches an element of
      the submission format when we replace the latter's trailing ".%l"
      (if any) with one of the source extensions of the language;
    - the codename matches exactly and if it ends in ".%l" the filename
      (if given) ends in any of the extensions of the language.

    codename (str|None): the filename-with-%l, if provided.
    filename (str|None): the name the contestant gave to the file, if
        provided.
    language (Language|None): the language to match against.
    submission_format ({str}): the task's submission format.

    return (str): the element of the submission format matched by the
        file.

    raise (InvalidFiles): if there's the slightest uncertainty or
        ambiguity.

    """
    if codename is None and filename is None:
        raise InvalidFiles("need at least one of codename and filename")

    # If no codename is given we guess it, by attempting a match of the
    # filename against all codenames. We claim victory if there is only
    # one hit.
    if codename is None:
        candidate_elements = {element for element in submission_format
                              if _match_filename(filename, language, element)}
        if len(candidate_elements) == 1:
            return candidate_elements.pop()

    # If, on the other hand, the codename is given then it needs to
    # exactly match an element of the format and, as a safety measure,
    # the filename needs to match too at least with respect to the
    # extension.
    elif codename in submission_format \
            and _match_extension(filename, language, codename):
        return codename

    raise InvalidFiles(
        "file %r/%r doesn't unambiguously match the submission format"
        % (codename, filename))


def _match_files(given_files, language, submission_format):
    """Fit the given files into the given submission format.

    Figure out, for all of the given files, which element of the
    submission format they are for.

    given_files ([ReceivedFile]): the files, as received from the user.
    language (Language|None): the language to match against.
    submission_format ({str}): the set of filenames-with-%l that the
        contestants are required to submit.

    return ({str: bytes}): the mapping from filenames-with-%l to
        contents.

    raise (InvalidFiles): if there's the slightest uncertainty or
        ambiguity.

    """
    files = dict()

    for codename, filename, content in given_files:
        codename = _match_file(codename, filename, language, submission_format)
        if codename in files:
            raise InvalidFiles(
                "two files match the same element %r of the submission format"
                % codename)
        files[codename] = content

    return files


class InvalidFilesOrLanguage(Exception):
    """Raised when the submitted files or given languages don't make sense."""

    pass


def match_files_and_language(given_files, given_language_name,
                             submission_format, allowed_language_names):
    """Figure out what the given files are and which language they're in.

    Take a set of files and a set of languages that these files are
    claimed to be in and try to make sense of it. That is, the provided
    information may come from sloppy, untrusted or adversarial sources
    and this function's duty is to parse and validate it to ensure it
    conforms to the expected format for a submission. Such a format is
    given as a set of desired codenames (i.e., filenames with language
    specific extensions replaced by %l) and a set of allowed languages
    (if such a limitation is in place). The function tries to be lenient
    as long as it believes the contestant's intentions are clear.

    The function first figures out which set of candidate languages the
    submission could be in, then tries to match the data against all of
    them. If exactly one matches then that match is returned. The
    languages that are considered are the ones provided by the user (if
    they exist and are allowed) or, if not provided, all languages
    (restricted to the allowed ones). If the submission format contains
    no element ending in ".%l" then the None language is always used
    (the rest of the arguments still needs to make sense though).
    Matching a language is done using the match_files function.

    given_files ([ReceivedFile]): the submitted files.
    given_language_name (str|None): the language, usually provided by
        the contestant, which the submitted files are in (None means
        this information isn't available and we should guess it).
    submission_format ({str}): the codenames that the submitted files
        should be matched to.
    allowed_language_names ([str]|None): the languages that the result
        is allowed to have (None means no limitation).

    return ({str: bytes}, Language|None): the mapping from codenames to
        content, and the language of the submission (with None meaning
        that no language is needed as the format was language-agnostic).

    raise (InvalidFilesOrLanguages): if issues arise when finding a
        match.

    """
    if not given_files:
        raise InvalidFilesOrLanguage("no files given")

    # If the submission format is language-agnostic the only "language"
    # that makes sense is None, and if the caller thought differently we
    # let them know.
    if not any(element.endswith(".%l") for element in submission_format):
        if given_language_name is not None:
            raise InvalidFilesOrLanguage(
                "a language %r is given when not needed" % given_language_name)
        candidate_languages = {None}

    # If a language is required and the caller told us which one to use
    # we follow their indication, provided it exists and is allowed.
    elif given_language_name is not None:
        try:
            language = get_language(given_language_name)
        except KeyError:
            raise InvalidFilesOrLanguage(
                "the given language %r isn't a language" % given_language_name)

        if allowed_language_names is not None \
                and language.name not in allowed_language_names:
            raise InvalidFilesOrLanguage(
                "the given language %r isn't allowed" % given_language_name)

        candidate_languages = {language}

    # If a language is needed but the caller didn't provide any we try
    # to auto-detect it by guessing among all allowed languages.
    else:
        if allowed_language_names is None:
            candidate_languages = set(LANGUAGES)
        else:
            candidate_languages = set()
            for language_name in allowed_language_names:
                try:
                    language = get_language(language_name)
                except KeyError:
                    pass
                else:
                    candidate_languages.add(language)

    matched_files_by_language = dict()
    invalidity_reasons = list()
    for language in candidate_languages:
        try:
            matched_files_by_language[language] = \
                _match_files(given_files, language, submission_format)
        except InvalidFiles as err:
            invalidity_reasons.append("%r: %s" % (
                language.name if language is not None else None, err))

    if not matched_files_by_language:
        raise InvalidFilesOrLanguage(
            "there isn't any language that matches all the files:\n%s"
            % (";\n".join(invalidity_reasons)))
    elif len(matched_files_by_language) > 1:
        raise InvalidFilesOrLanguage(
            "there is more than one language that matches all the files: %r"
            % set(matched_files_by_language.keys()))

    language, files = matched_files_by_language.popitem()

    return files, language
