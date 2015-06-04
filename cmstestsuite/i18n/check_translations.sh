#!/usr/bin/env bash

export LANG=C
pushd po > /dev/null

for FILE in *.po ; do
    NEWFILE=.`basename $FILE .po`.msgmerge.po
    msgmerge -q --width=79 $FILE cms.pot > $NEWFILE
done

for FILE in cms.pot *.po .*.po ; do
    msgfmt -o /dev/null -vv $FILE 2>&1 | ../cmstestsuite/i18n/parse_msgfmt.py
done

rm -f .*.msgmerge.po
popd > /dev/null
