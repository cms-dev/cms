#!/bin/bash

echo > autoconf.h
./mk-syscall-table > syscall-table.h
gcc -static -std=c99 -o mo-box box.c

