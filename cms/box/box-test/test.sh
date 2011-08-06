#!/bin/bash

. ./conf.sh

export CFLAGS="-static"

redecho() {
	echo -e '\e[1;31m'$@'\e[0m'
}

for i in $PROGLIST ; do
	redecho "==> $i <=="
	rm -f $i
	make $i
	../mo-box -f -t 1 -x 1 -w 3 -M $i.log -m 10000 -v -v -v -v -v -a 1 -p output.txt -- ./$i
	echo Exited with code $?
done

echo
redecho STATUS
for i in $PROGLIST ; do
	redecho "==> $i <=="
	grep ^status: $i.log
done

