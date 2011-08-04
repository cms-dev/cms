#!/bin/bash

# Detect dir
SCRIPT_DIR="`dirname "$0"`"
cd "$SCRIPT_DIR"

echo > autoconf.h
./mk-syscall-table > syscall-table.h
gcc -static -std=c99 -o mo-box box.c

