#!/bin/sh -ex

gcc -o isolate isolate.c -O2 -Wall -Wno-parentheses -Wno-unused-result -g -std=c99

