#!/usr/bin/env bash

export LANG=C
pushd cms/server/po >/dev/null

for FILE in *.po ; do
    NEWFILE=.`basename $FILE .po`.msgmerge.po
    msgmerge -q --width=79 $FILE messages.pot > $NEWFILE
done

for FILE in messages.pot *.po .*.po ; do
    msgfmt -o /dev/null -vv $FILE 2>&1 | ../../../cmstestsuite/i18n/parse_msgfmt.py
done

rm -f .*.msgmerge.po
popd > /dev/null
