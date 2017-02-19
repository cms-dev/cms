#!/usr/bin/env bash

export LANG=C

for FILE in cms/locale/*/LC_MESSAGES/cms.po; do
    LANG=${FILE/cms\/locale\//}
    LANG=${LANG/\/LC_MESSAGES\/cms.po/}
    NEWFILE=.${LANG}.msgmerge.po
    msgmerge -q --width=79 $FILE cms/locale/cms.pot > $NEWFILE
done

for FILE in cms/locale/cms.pot .*.msgmerge.po; do
    msgfmt -o /dev/null -vv ${FILE} 2>&1 | ./cmstestsuite/i18n/parse_msgfmt.py
done

rm -f .*.msgmerge.po
