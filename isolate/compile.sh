#!/bin/sh -ex

gcc -o isolate isolate.c -O2 -Wall -g -std=c99
sudo chown root:root isolate
sudo chmod 4755 isolate

