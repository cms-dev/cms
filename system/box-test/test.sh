#!/bin/bash

. ./conf.sh

export CFLAGS="-static"

redecho() {
	echo -e '\e[1;31m'$@'\e[0m'
}

for i in $PROGLIST ; do
	redecho "==> $i <=="
	rm $i
	make $i
	../mo-box -t 1 -x 1 -w 3 -M $i.log -m 10000 -v -v -v -v -v -a 0 -- ./$i
	echo Exited with code $?
done

redecho STATUS
for i in $PROGLIST ; do
	redecho "==> $i <=="
	grep ^status: $i.log
done

