#!/usr/bin/env python3

import pathlib
import shutil
import sys

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <onesky-downloaded-folder> <cms-repository-root>")
    sys.exit(0)

onesky_folder = pathlib.Path(sys.argv[1])
cms_folder = pathlib.Path(sys.argv[2])

locale_map = {
    "bg-BG": "bg",
    "bs-BA": "bs",
    "cs": "cs",
    "de-DE": "de",
    "es-CL": "es_CL",
    "es-ES": "es",
    "et-EE": "et",
    "fr-FR": "fr",
    "it-IT": "it",
    "ja": "ja",
    "ko": "ko",
    "lt-LT": "lt",
    "lv-LV": "lv",
    "nl-NL": "nl",
    "ro-RO": "ro",
    "ru-RU": "ru",
    "sl-SI": "sl",
    "uk": "uk",
    "vi": "vi",
    "zh-CN": "zh_CN",
    "zh-TW": "zh_TW",
}

for onesky_locale, cms_locale in locale_map.items():
    shutil.copy(
        onesky_folder / f"{onesky_locale}.po",
        cms_folder / "cms/locale" / cms_locale / "LC_MESSAGES/cms.po",
    )
