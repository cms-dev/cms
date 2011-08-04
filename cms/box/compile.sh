#!/bin/bash

SCRIPT_DIR="`dirname "$0"`"

if [ "`uname -m`" == "x86_64" ] ; then
	$SCRIPT_DIR/compile64.sh
else
	$SCRIPT_DIR/compile32.sh
fi

